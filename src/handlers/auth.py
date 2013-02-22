import tornado
import tornado.web
import tornado.auth
import tornado.escape

import simplejson as json

import base
import user

class BaseAuthHandler(base.BaseWebHandler):
    # override for specific auth service
    def has_auth_token(self):
        raise NotImplementedError()
    # override for specific auth service
    def get_cb_uri(self):
        raise NotImplementedError()

    def render_register(self, service, login, email=None, info_message=None, error_message=None, next=None):
        self.safe_render('auth/register.html', service=service, 
            login=login, 
            email=email, 
            info_message=info_message,
            error_message=error_message,
            next=next
        )

    def render_login(self, error=None, success=None, next=None):
        self.safe_render('auth/login.html', error_message=error, success_message=success, next=next)

    def set_user_cookie(self, user_object):
        self.set_secure_cookie("user", tornado.escape.json_encode(user_object._asdict()))

    @tornado.web.asynchronous
    def get(self):
        if self.has_auth_token():
            self.get_authenticated_user(self._on_auth)
            return
        self.authenticate_redirect(callback_uri = self.get_cb_uri(),
                                    ax_attrs = ["name", "email", "language", "username"])

    @tornado.web.asynchronous
    def post(self):
        cb_uri = self.get_cb_uri()
        if self.get_argument("next", None):
            cb_uri += "?next=%s" % self.get_argument("next", None)
        self.authenticate_redirect(callback_uri=cb_uri)

    def init_user(self, oauth_user):
        service = self.get_service_name()
        email = self.get_email(oauth_user) # twitter cb doesn't have email, probably ok
        login = self.get_login(oauth_user)
        user_account = user.get_account_by_login(self.db, login, service)
        if not user_account:
            no_email_msg = "It looks like we don't have an email address for you yet. You probably want to set one to enable all features!"
            self.render_register(service = service,
                email = email,
                login = login,
                info_message = no_email_msg if not email else None,
                next=self.get_argument("next", "/account")
            )
        else:
            self.set_user_cookie(user_account)
            self.redirect(self.get_argument("next", "/account"))

    def _on_auth(self, oauth_user):
        if not oauth_user:
            self.render_login(error="%s auth failed" % self.get_service_name())
        else:
            self.init_user(oauth_user)

class GAuthHandler(BaseAuthHandler, tornado.auth.GoogleMixin):
    def get_service_name(self):
        return 'google'

    def has_auth_token(self):
        return self.get_argument("openid.mode", False)

    def get_cb_uri(self):
        return '/login/google'

    def get_email(self, oauth_user):
        return oauth_user['email']

    def get_login(self, oauth_user):
        return oauth_user['email']

class TAuthHandler(BaseAuthHandler, tornado.auth.TwitterMixin):
    def get_service_name(self):
        return 'twitter'

    def has_auth_token(self):
        return self.get_argument("oauth_token", False)

    def get_cb_uri(self):
        return '/login/twitter'

    def get_email(self, oauth_user):
        return None

    def get_login(self, oauth_user):
        return "@"+oauth_user['screen_name']

# class FAuthHandler(BaseAuthHandler, tornado.auth.FacebookMixin):
#     def get_service_specific_name(self):
#         return 'facebook'
#
#     def has_service_specific_auth_token(self):
#         return self.get_argument("session", False)
#
#     def get_cb_uri(self):
#         return '/login/facebook'
#
#     def get_email(self, oauth_user):
#         return None
#
#     def get_login(self, oauth_user):
#         return oauth_user['screen_name']

class AuthHandler(BaseAuthHandler):
    def get(self):
        self.render_login(next=self.get_argument("next", "/account"))

class RegistrationHandler(BaseAuthHandler):
    def get(self):
        self.redirect("/login")

    def post(self):
        login = self.get_argument('login')
        service = self.get_argument('service')
        email = self.get_argument('email', None)
        user_object = user.create_account(self.db, login, service, email)
        self.set_user_cookie(user_object)
        self.redirect(self.get_argument("next", "/account"))

class AccountHandler(base.BaseWebHandler):
    def render_account(self, error=None, success=None):
        account = user.Account(**self.get_current_user())
        self.safe_render('auth/account.html', account=account, error_message=error, success_message=success)

    def get(self):
        self.render_account()

    def post(self):
        # TODO: allow modifying things
        raise tornado.web.HTTPError(404)

class LogoutHandler(base.BaseWebHandler):
    def render_logout(self, error=None, success=None):
        self.safe_render('auth/logout.html', error_message=error, success_message=success)

    def get(self):
        user = self.get_current_user()
        if user:
            # kill cookie or change session hash
            self.clear_cookie("user")
            logout_message = "The user '%(login)s' was successfully logged out" % user
            self.render_logout(success=logout_message)
        else:
            self.render_logout(error="You were not logged in!")

