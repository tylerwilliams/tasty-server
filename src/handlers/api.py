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

import base

logger = logging.getLogger(__name__)

class BaseTasteHandler(base.BaseAPIHandler):
    # some catalog helper functions
    # basically an async pyechonest/catalog
    def get_base_params(self):
        return {
            'api_key': self.application.settings_manager.get('api_key'),
            'format': 'json',
        }
    
    @tornado.gen.engine
    def create_catalog(self, catalog_name, catalog_type, callback):
        params = self.get_base_params()
        params.update({
            'type': catalog_type,
            'name': catalog_name,
        })
        req = tornado.httpclient.HTTPRequest(
            url = "http://developer.echonest.com/api/v4/catalog/create",
            method = "POST",
            body = urllib.urlencode(params)
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def profile_catalog(self, catalog_id, catalog_name, callback):
        params = self.get_base_params()
        if catalog_id:
            params['id'] = catalog_id
        elif catalog_name:
            params['name'] = catalog_name
        else:
            raise Exception("you must provide one of catalog_id | catalog_name!")
        base_url = "http://developer.echonest.com/api/v4/catalog/profile"
        req = tornado.httpclient.HTTPRequest(
            url = base_url + "?" + base.format_params(params),
            method = "GET",
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def read_catalog(self, catalog_id, start, results, callback):
        params = self.get_base_params()
        params.update({
            'id': catalog_id,
            'start': start,
            'results': results,
        })
        base_url = "http://developer.echonest.com/api/v4/catalog/read"
        req = tornado.httpclient.HTTPRequest(
            url = base_url + "?" + base.format_params(params),
            method = "GET",
        )
        response = yield tornado.gen.Task(self.application.http_client.fetch, req)
        callback(json.loads(response.buffer.read()))

    @tornado.gen.engine
    def update_catalog(self, catalog_id, items, callback):
        params = self.get_base_params()
        params.update({
            'id': catalog_id,
            'data': json.dumps(items),
        })
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

    # hum, this is a lot of decorators, baw HELP!
    @tornado.web.asynchronous
    @base.oauth1
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
    @base.oauth1
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
