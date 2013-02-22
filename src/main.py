import os
import re
import time
import pprint
import urllib
import logging
import functools

import tornado.ioloop
import tornado.options
import tornado.web
import tornado.gen
import tornado.database
import tornado.httpclient
import simplejson as json
import oursql

import settings
import handlers

logger = logging.getLogger(__name__)

def pformat_query(*args):
    query = args[0]
    args = args[1]
    query = query.replace("?", "%s")
    query = query % args
    return re.sub("\s+", " ", query).strip()

class TimedCursor(oursql.DictCursor):
    def execute(self, *args, **kwargs):
        start_tic = time.time()
        r = super(TimedCursor, self).execute(*args, **kwargs)
        stop_tic = time.time()
        if logger.isEnabledFor(logging.DEBUG):
            query_string = pformat_query(*args)
            logger.debug('cursor.execute("%s") took %2.2f ms', query_string, (stop_tic - start_tic) * 1000)
        return r

class Application(tornado.web.Application):
    def __init__(self, urls, settings_manager):
        self.settings_manager = settings_manager

        _settings = {
            'static_path': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
            'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
            'debug':'yes',
            # how to make a cookie_secret: import base64, uuid; base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
            'cookie_secret': self.settings_manager.get('cookie_secret'),
            'xsrf_cookies': True,
            'login_url': '/login',
            'twitter_consumer_key': self.settings_manager.get('twitter_consumer_key'),
            'twitter_consumer_secret': self.settings_manager.get('twitter_consumer_secret'),
        }

        self.db_conn = oursql.connect(host = self.settings_manager.get('db_host'),
                                      port = int(self.settings_manager.get('db_port')),
                                      db = self.settings_manager.get('db_name'),
                                      user = self.settings_manager.get('db_user'),
                                      passwd = self.settings_manager.get('db_pass'),
                                      default_cursor = TimedCursor,
                                     )
        self.http_client = tornado.httpclient.AsyncHTTPClient()
        tornado.web.Application.__init__(self, urls, **_settings)

urls = (
    # API
    (r"/api/1/(?P<uid>[^\/]+)/tastes/new",              handlers.api.NewTasteHandler),
    (r"/api/1/(?P<uid>[^\/]+)/tastes",                  handlers.api.ListTasteHandler),

    # static files
    (r"/static/(.*)",                                   tornado.web.StaticFileHandler, {"path": os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")}),

    # login / logout / account
    (r"/login/google",                                  handlers.auth.GAuthHandler),
    (r"/login/twitter",                                 handlers.auth.TAuthHandler),
    # (r"/login/facebook",                                handlers.auth.FAuthHandler),
    (r"/login",                                         handlers.auth.AuthHandler),
    (r"/register",                                      handlers.auth.RegistrationHandler),
    (r"/logout",                                        handlers.auth.LogoutHandler),
    (r"/account",                                       handlers.auth.AccountHandler),
    (r"/applogin",                                      handlers.web.AppLoginPageHandler),

    # website pages
    (r"/api",                                           handlers.web.APIPageHandler),
    (r"/tastes",                                        handlers.web.TastePageHandler),
    (r"/",                                              handlers.web.IndexHandler),
)

def get_app(settings_manager):
    settings_manager = settings_manager or settings.SettingsManager()
    app = Application(urls, settings_manager)
    return app
