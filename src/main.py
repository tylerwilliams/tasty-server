import os
import time
import pprint
import urllib
import logging

import tornado.ioloop
import tornado.options
import tornado.web
import tornado.gen
import tornado.httpclient
import simplejson as json

import settings

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

class BaseHandler(tornado.web.RequestHandler):
    def format_response(self, response):
        return json.dumps(response)

    def set_headers(self):
        # CORS
        self.set_header("Access-Control-Allow-Origin","*")
        self.set_header("Access-Control-Allow-Methods","GET,POST,OPTIONS,PUT,DELETE")
        # RESPONSE FORMAT
        self.set_header('Content-Type','application/json; charset=utf-8')

    def write_response(self, response):
        # logger.debug(pprint.pformat(response))
        self.set_headers()
        return self.write(response)

    def format_and_write_response(self, raw_response):
        formatted_response = self.format_response(raw_response)
        self.write_response(formatted_response)

class IndexHandler(BaseHandler):
    def get(self):
        self.redirect("/static/html/index.html")

class BaseTasteHandler(BaseHandler):
    # some catalog helper functions
    # basically an async pyechonest/catalog
    @tornado.gen.engine
    def create_catalog(self, catalog_name, catalog_type, callback):
        params = {
            'api_key': self.application.settings_manager.get('api_key'),
            'format': 'json',
            'type': catalog_type,
            'name': catalog_name,
        }
        req = tornado.httpclient.HTTPRequest(
            url = "http://developer.echonest.com/api/v4/catalog/create",
            method = "POST",
            body = urllib.urlencode(params)
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def profile_catalog(self, catalog_id, catalog_name, callback):
        params = {
            'api_key': self.application.settings_manager.get('api_key'),
            'format': 'json',
        }
        if catalog_id:
            params['id'] = catalog_id
        elif catalog_name:
            params['name'] = catalog_name
        else:
            raise Exception("you must provide one of catalog_id | catalog_name!")
        base_url = "http://developer.echonest.com/api/v4/catalog/profile"
        req = tornado.httpclient.HTTPRequest(
            url = base_url + "?" + format_params(params),
            method = "GET",
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def read_catalog(self, catalog_id, start, results, callback):
        params = {
            'api_key': self.application.settings_manager.get('api_key'),
            'format': 'json',
            'id': catalog_id,
            'start': start,
            'results': results,
        }
        base_url = "http://developer.echonest.com/api/v4/catalog/read"
        req = tornado.httpclient.HTTPRequest(
            url = base_url + "?" + format_params(params),
            method = "GET",
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def update_catalog(self, catalog_id, items, callback):
        params = {
            'api_key': self.application.settings_manager.get('api_key'),
            'format': 'json',
            'id': catalog_id,
            'data': json.dumps(items),
        }
        req = tornado.httpclient.HTTPRequest(
            url = "http://developer.echonest.com/api/v4/catalog/update",
            method = "POST",
            body = urllib.urlencode(params)
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def get_or_create_catalog(self, catalog_name, catalog_type, callback):
        profile_response = yield tornado.gen.Task(self.profile_catalog, None, catalog_name)
        if "catalog" in profile_response['response']:
            callback(profile_response['response']['catalog']['id'])
        else:
            create_response = yield tornado.gen.Task(self.create_catalog, catalog_name, catalog_type)
            callback(create_response['response']['id'])

    @tornado.gen.engine
    def read_full_catalog(self, catalog_id, callback):
        start = 0
        batch_size = 100
        read_response = yield tornado.gen.Task(self.read_catalog, catalog_id, start, batch_size)
        total_num_results = read_response['response']['catalog']['total']
        results = read_response['response']['catalog']['items']
        start += batch_size
        while len(results) < total_num_results:
            read_response = yield tornado.gen.Task(self.read_catalog, catalog_id, start, batch_size)
            results += read_response['response']['catalog']['items']
            start += batch_size
        callback(results)
    
    def format_update_items(self, scrobbles):
        update_items = []
        for s in scrobbles:
            inner_item = {
                'item_id': str(s['timestamp']),
                'artist_name': s['artist_name'],
                'song_name': s['song_name'],
                'item_keyvalues': {
                    'timestamp':s['timestamp'],
                    'source':s['source'],
                },
            }
            if 'release_name' in s and s['release_name']:
                inner_item['release'] = s['release_name']
            if 'duration' in s and s['duration'] != None:
                inner_item['item_keyvalues']['duration'] = s['duration']
            if 'rating' in s and s['rating'] != None:
                inner_item['rating'] = s['rating']
            if 'play_count' in s and s['play_count'] != None:
                inner_item['play_count'] = s['play_count']
            if 'favorite' in s and s['favorite']:
                inner_item['favorite'] = s['favorite']
            if 'skip' in s and s['skip']:
                inner_item['skip_count'] = 1

            update_items.append({
                'action':'update',
                'item':inner_item,
            })
        return update_items

class NewTasteHandler(BaseTasteHandler):
    def _on_finish(self, response):
        self.format_and_write_response(response)

    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, uid):
        # find our catalog
        cat_id = yield tornado.gen.Task(self.get_or_create_catalog, uid, "song")
        tastes = json.loads(self.request.body)
        if not isinstance(tastes, list):
            tastes = [tastes]

        # push our update(s)
        items = self.format_update_items(tastes)
        update_response = yield tornado.gen.Task(self.update_catalog, cat_id, items)
        self.format_and_write_response({'cat_id':cat_id})
        self.finish()

class ListTasteHandler(BaseTasteHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, uid):
        # find our catalog
        cat_id = yield tornado.gen.Task(self.get_or_create_catalog, uid, "song")
        
        # get all results
        results = yield tornado.gen.Task(self.read_full_catalog, cat_id)
        
        # sort results
        results = sorted(results, key=lambda i: i['item_keyvalues']['timestamp'], reverse=True)
        
        nice_response = {
            'taste': results[:100], # just in case
        }
        
        self.format_and_write_response(nice_response)
        self.finish()


class Application(tornado.web.Application):
    def __init__(self, urls, settings_manager):
        _settings = {
            'static_path': os.path.join(os.path.dirname(__file__), "static"),
        }
        self.settings_manager = settings_manager
        self.http_client = tornado.httpclient.AsyncHTTPClient()
        tornado.web.Application.__init__(self, urls, **_settings)

urls = (
    (r"/api/1/(?P<uid>[^\/]+)/tastes/new",      NewTasteHandler),
    (r"/api/1/(?P<uid>[^\/]+)/tastes",          ListTasteHandler),
    (r"/",                                      IndexHandler),
)

def get_app(settings_manager):
    settings_manager = settings_manager or settings.SettingsManager()
    app = Application(urls, settings_manager)
    return app
