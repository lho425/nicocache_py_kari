# -*- coding: utf-8 -
import BaseHTTPServer
import SocketServer

from .. import core
from ..core import iowrapper

import logging as _logging

logger = _logging.getLogger(__name__)
logger.debug("load %s", __name__)

class MultiThreadHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    daemon_threads = True

class ForkingHTTPServerHTTPServer(SocketServer.ForkingMixIn, BaseHTTPServer.HTTPServer):
    pass
    
    
def run_server(port, handler_function):
    return _run_server(port, handler_function, HTTPServerClass=BaseHTTPServer.HTTPServer)
    
def run_multithreading_server(port, handler_function):
    return _run_server(port, handler_function, HTTPServerClass=MultiThreadHTTPServer)

def run_forking_server(port, handler_function):
    return _run_server(port, handler_function, HTTPServerClass=ForkingHTTPServerHTTPServer)


def _run_server(port, handler_function, HTTPServerClass=BaseHTTPServer.HTTPServer):
    class _RequestHandler(SocketServer.StreamRequestHandler):
        def handle(self):
            
            client_file = iowrapper.SocketWrapper(self.connection)
            info = core.common.Object()
            info.client_address = core.common.Address(self.client_address)
            info.this_server_address = core.common.Address(
                            (self.server.server_name, int(self.server.server_port)))
            #self.server is BaseHTTPServer.HTTPServer.
            #where defined self.server and does it have .server_port?
            handler_function(client_file, info)


    http_server = HTTPServerClass(('', port), _RequestHandler)
    http_server.serve_forever()



    