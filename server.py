#!/usr/bin/env python
# -*- coding: utf-8 -*-

import functools
import json
import logging
import time

import motor.motor_tornado
import tornado
import tornado.httpclient
import tornado.web


###############################################################################
# Settings
###############################################################################

DEBUG = True

PORT = 8080

URL = 'https://vast-eyrie-4711.herokuapp.com/?key=%s'
FROM_CACHE = '/from_cache'

# cache expires in 24 hours
CACHE_TIMEOUT = 60 * 60 * 24

# If the fetching request is failed somehow
# then those requests which are waiting for the result
# from the cache will never get it.
# Delete the key to reset them (to make one of them fetching).
# fetching request expires in 5 minutes
FETCH_TIMEOUT = 5 * 60

MONGODB = 'mongodb://192.168.2.128:27017'

REQUEST_TIMEOUT = 10
DB_REQUEST_DELAY = 20

###############################################################################


logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
(KEY, CONTENT, TIMESTAMP) = ("key", "content", "timestamp")


def expired(timestamp, timeout=CACHE_TIMEOUT):
    return time.time() - timestamp > timeout


class FromCacheHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.aborted = False
        self.fetching = False
        self.key = None
        self.db = self.settings['db']
        self.http = tornado.httpclient.AsyncHTTPClient()
        self.ioloop = tornado.ioloop.IOLoop.current()

    def on_connection_close(self):
        self.aborted = True

    @tornado.web.asynchronous
    def get(self):
        qcs = dict(qc.split('=') for qc in self.request.query.split('&'))
        self.key = qcs.get('key')
        self.set_header('Content-Type', 'application/json')
        self.do_fetch()

    def do_fetch(self):
        logging.debug('Request to db.cache to find key=%s', self.key)
        cached = self.db.cache.find_one({KEY: self.key})
        cached.add_done_callback(self.call_fetch)

    def validate_cache(self):
        if not self.cache:
            return

        logging.debug('Validating: %s', self.cache)

        timestamp = self.cache[TIMESTAMP]
        if CONTENT not in self.cache and expired(timestamp, FETCH_TIMEOUT) \
                or expired(timestamp):
            logging.info('Expired %s, removing...', self.cache)
            self.db.cache.remove({KEY: self.key})
            self.cache = None
            self.fetching = False

    def still_alive(slf):
        def still_alive(method):
            @functools.wraps(method)
            def decorated(*args, **kwargs):
                if slf.aborted and not slf.fetching:
                    logging.warning('Aborted')
                    return
                return method(*args, **kwargs)
            return decorated
        return still_alive

    def call_fetch(self, resp):
        self.cache = resp.result()
        still_alive = self.still_alive()

        @still_alive
        def _do_request():
            self.validate_cache()

            if self.cache is None:
                now = time.time()
                ins = {KEY: self.key, TIMESTAMP: now}
                logging.info('Inserting: %s', ins)
                self.cache = ins
                self.db.cache.insert(ins, callback=http_fetch)
                return

            if CONTENT in self.cache:
                send(self.cache[CONTENT])
            else:
                self.ioloop.add_timeout(time.time() + DB_REQUEST_DELAY,
                                        self.do_fetch)

        def http_fetch(result, error):
            if error and not self.fetching:
                # duplicating request, just ignore it
                logging.info('Ignoring duplicating request...')
                return
            if not self.fetching:
                logging.debug('Mark request as fetching...')
            logging.info('Fetching...')
            self.fetching = True
            http_future = self.http.fetch(URL % self.key, raise_error=False)
            http_future.add_done_callback(handle_future)

        @still_alive
        def handle_future(resp):
            exception = resp.exception()
            if exception:
                return self.ioloop.call_later(1, lambda: _do_request())
            handle_response(resp.result())

        @still_alive
        def handle_response(result):
            if result.error:
                return self.ioloop.call_later(1, lambda: _do_request())

            upd = {CONTENT: result.body, TIMESTAMP: time.time()}
            logging.info('Update key=%s with: %s', self.key, upd)
            self.db.cache.update({KEY: self.key}, {"$set": upd}, upsert=True)
            self.cache.update(upd)
            send(result.body)

        @still_alive
        def send(body):
            logging.info('Result: %s', body)
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
    settings['db'].cache.create_index("key", unique=True)

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
