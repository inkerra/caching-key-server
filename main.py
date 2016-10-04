#!/usr/bin/env python
# -*- coding: utf-8 -*-

import BaseHTTPServer
import os
import time
import urllib2
from urlparse import urlparse


URL = 'https://vast-eyrie-4711.herokuapp.com/?key=%s'
FROM_CACHE = '/from_cache'
CACHE_FILE_TMPT = '%s.cached'
# 24 hours timeout:
CACHE_TIMEOUT = 60 * 60 * 24
REQUEST_TIMEOUT = 1


class CacheHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _get_cached_value(self, key):
        data = None
        cache_filename = CACHE_FILE_TMPT % key

        def expired(filename):
            return time.time() - os.path.getctime(filename) > CACHE_TIMEOUT

        if os.path.exists(cache_filename) and not expired(cache_filename):
            with open(cache_filename, 'r') as f:
                data = f.read()

        while not data:
            try:
                resp = urllib2.urlopen(URL % key, timeout=REQUEST_TIMEOUT)
            except IOError as e:
                # ignore timeout error
                print 'Timeout: trying again...'
            except urllib2.HTTPError as e:
                if e.code == 404:
                    self.send_error(404)
                    return
            except urllib2.URLError as e:
                self.send_error(502)
                return
            else:
                data = resp.read()
                with open(cache_filename, 'w') as f:
                    f.write(data)

        self.send_response(200)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parse_res = urlparse(self.path)
        if parse_res.path == FROM_CACHE:
            qcs = dict(qc.split('=') for qc in parse_res.query.split('&'))
            key = qcs.get('key')
            self._get_cached_value(key)
        else:
            self.send_error(404)


def run():
    server_address = ('', 8080)
    try:
        serv = BaseHTTPServer.HTTPServer(server_address, CacheHandler)
        serv.serve_forever()
    except KeyboardInterrupt:
        print 'Shutting down the server...'
        serv.socket.close()


if __name__ == "__main__":
    run()
