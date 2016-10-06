#!/usr/bin/env python
# -*- coding: utf-8 -*-

import functools
import json
import time

import motor.motor_tornado
import tornado
import tornado.httpclient
import tornado.web


DEBUG = True

PORT = 8080

URL = 'https://vast-eyrie-4711.herokuapp.com/?key=%s'
FROM_CACHE = '/from_cache'

# cache expires in 24 hours
CACHE_TIMEOUT = 60 * 60 * 24
MONGODB = 'mongodb://192.168.2.128:27017'

REQUEST_TIMEOUT = 10


def expired(timestamp):
    return time.time() - timestamp > CACHE_TIMEOUT


class FromCacheHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.aborted = False
        self.db = self.settings['db']

    def on_connection_close(self):
        self.aborted = True

    @tornado.web.asynchronous
    def get(self):
        qcs = dict(qc.split('=') for qc in self.request.query.split('&'))
        key = qcs.get('key')
        self.set_header('Content-Type', 'application/json')
        self.do_fetch(key)

    def do_fetch(self, key):
        cached = self.db.cache.find_one({"key": key})
        cached.add_done_callback(functools.partial(self.call_fetch, key))

    def call_fetch(self, key, resp):
        http = tornado.httpclient.AsyncHTTPClient()
        ioloop = tornado.ioloop.IOLoop.current()

        def still_alive(method):
            @functools.wraps(method)
            def decorated(*args, **kwargs):
                if self.aborted:
                    return
                return method(*args, **kwargs)

            return decorated

        @still_alive
        def _do_request():
            cached = resp.result()
            if cached is not None and not expired(cached["timestamp"]):
                send(cached["content"])
                return
            http_future = http.fetch(URL % key, raise_error=False)
            http_future.add_done_callback(handle_future)

        @still_alive
        def handle_future(resp):
            exception = resp.exception()
            if exception:
                return ioloop.call_later(1, lambda: _do_request())
            handle_response(resp.result())

        @still_alive
        def handle_response(result):
            if result.error:
                return ioloop.call_later(1, lambda: _do_request())

            self.db.cache.update({"key": key},
                                 {"$set": {"content": result.body,
                                           "timestamp": time.time()}},
                                 upsert=True)
            send(result.body)

        @still_alive
        def send(body):
            data = tornado.escape.json_decode(body)
            self.write(json.dumps(data))
            self.finish()

        _do_request()


def make_app():
    settings = {
        'xsrf_cookies': True,
        'cookie_secret': "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        'debug': DEBUG,
        'db': motor.motor_tornado.MotorClient(MONGODB).cache,
    }

    return tornado.web.Application([
        (r"/from_cache/?", FromCacheHandler),
    ], **settings)


def run():
    application = make_app()
    application.listen(PORT)
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.current().stop()


if __name__ == "__main__":
    run()
