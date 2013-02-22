import pprint
import logging
import functools

import tornado.web
import simplejson as json

import user

logger = logging.getLogger(__name__)

def format_params(param_dict):
    param_list = []
    for key,val in param_dict.iteritems():
        if isinstance(val, list):
            param_list.extend( [(key,subval) for subval in val] )
        elif val is not None:
            if isinstance(val, unicode):
                val = val.encode('utf-8')
            param_list.append( (key,val) )
    return "&".join("%s=%s" % (k,v) for (k,v) in param_list)

def oauth1(method):
    """Decorate methods with this to require that the request be oauth 1.0 signed
        * the request must also have a uid in the url for us to validate the user
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        # they must have passed a uid
        if not "uid" in kwargs:
            raise tornado.web.HTTPError(404)
        # it must correspond to a real user
        api_account = user.get_account_by_id(self.db, int(kwargs['uid']))
        if not api_account:
            raise tornado.web.HTTPError(404)
        setattr(self, 'api_account', api_account)
        # oauth credentials must match w/ user
        self.validate_oauth()
        # do the thing
        return method(self, *args, **kwargs)
    return wrapper

class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db_conn

    def safe_render(self, template, **kwargs):
        if not 'success_message' in kwargs:
            kwargs['success_message'] = None
        if not 'warning_message' in kwargs:
            kwargs['warning_message'] = None
        if not 'error_message' in kwargs:
            kwargs['error_message'] = None
        if not 'info_message' in kwargs:
            kwargs['info_message'] = None            
        self.render(template, **kwargs)

class BaseAPIHandler(BaseHandler):
    def format_response(self, response):
        return json.dumps(response)

    def set_headers(self):
        # CORS
#        # maybe later
#        self.set_header("Access-Control-Allow-Origin", "*")
#        self.set_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS,PUT,DELETE")
        # RESPONSE FORMAT
        self.set_header('Content-Type','application/json; charset=utf-8')

    def write_response(self, response):
        # logger.debug(pprint.pformat(response))
        self.set_headers()
        return self.write(response)

    def format_and_write_response(self, raw_response):
        formatted_response = self.format_response(raw_response)
        self.write_response(formatted_response)

    def validate_oauth(self):
        assert hasattr(self, 'api_account')
        try:
            user.validate_oauth_request(self)
        except user.OauthInvalidParamError, e:
            raise tornado.web.HTTPError(401, e.msg)
        except user.OauthUnauthorized, e:
            raise tornado.web.HTTPError(403, e.msg)

class BaseWebHandler(BaseHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            return None
        return tornado.escape.json_decode(user_json)
