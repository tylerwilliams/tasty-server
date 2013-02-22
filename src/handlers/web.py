import base
import tornado
import tornado.web

import simplejson as json

import user

class IndexHandler(base.BaseWebHandler):
    def get(self):
        self.safe_render('index.html')


class APIPageHandler(base.BaseWebHandler):
    def get(self):
        self.safe_render('api.html')
        
class TastePageHandler(base.BaseWebHandler):
    @tornado.web.authenticated
    def get(self):
        self.safe_render('tastes.html')

class AppLoginPageHandler(base.BaseWebHandler):
    @tornado.web.authenticated
    def get(self):
        account = user.Account(**self.get_current_user())
        self.set_header('Content-Type','application/json; charset=utf-8')
        self.write(json.dumps(account._asdict()))