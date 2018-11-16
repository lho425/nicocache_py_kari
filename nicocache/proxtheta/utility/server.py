# -*- coding: utf-8 -
import socket
import functools

from ..core import httpmes
from ..core.common import ResponsePack

from . import common


streaming_bufsize = 8192


def streaming(srcf, destf, size=-1, bufsize=None):
    if bufsize is None:
        bufsize = streaming_bufsize

    return common.copy_file(srcf, destf, size, bufsize)


def trancefer_chunked(srcf, destf):
    """trancefer chunked data from srcf and copy to destf
    without any processing."""
    while True:
        size_str = srcf.readline()
        size = int(size_str, 16)  # fixme!!! can not handle chunk-extension
        destf.write(size_str)
        if size == 0:
            destf.write(srcf.readline())  # fixme!!! cannot handle trailer!
            break
        else:
            streaming(srcf, destf, size)
            destf.write(srcf.readline())

    destf.flush()

    return


def remove_scheme_and_authority(req):
    req.host = ""
    req.port = None
    req.scheme = ""
    return


def transfer_resbody_to_client(res, body_file, client_file, req=None):
    """req is optional but if given, may do efficient transfer."""

    if httpmes.get_transfer_length(res, req) == "unknown":
        raise RuntimeError("unknown http transfer length")

    if res.is_chunked():
        trancefer_chunked(body_file, client_file)

    elif res.is_connection_close():
        streaming(body_file, client_file)  # reply body
    else:
        # reply body
        streaming(
            body_file, client_file, httpmes.get_transfer_length(res, req))
    return


def is_localhost(addr_str):  # todo!!! handle ipv6 localhost "::1"

    return addr_str.startswith("127")


def is_request_to_this_server(req_host, req_port, listening_port):
    """
    (req_host: str, req_port: int or None, listening_port: int)
    if req_host is "localhost" or "127.*.*.*", judging request to this host.
    if name resolved req_host is "127.*.*.*", judging request to this host.
    if req_host is None or "" then, judging request to this host (based on http header spec).

    if req_port is listening_port, judging request to this host.
    if req_port is None, judging request to this host(based on http header spec).

    *** http header spec ***
    `GET /index.html HTTP/1.1'
    When given such header to your http server, req_host may be "" and req_port may be None
    according to httpmes.HTTPRequest.
    So, you can immediately do "is_request_to_this_server(req.host, req.port, listening_port)"
    """

    return (not req_host or is_localhost(req_host)) and (req_port is None or req_port == listening_port)


# !!!ここから下は全体的に例外安全じゃないから直す
class ResponseServer(object):
    # 継承し、can_serveとserveをオーバーライドする
    # もしくは__init__の引数に関数をわたす

    # 1プロセス:1インスタンスなので注意
    # クライアントごとにインスタンスが作られるわけではない!

    @staticmethod
    def accept(req, info):
        return True

    @staticmethod
    def serve(req, server_sockfile, info):
        return ResponsePack(res=None, server_sockfile=server_sockfile)

    def __init__(self, accept=None, serve=None):
        if accept:
            self.accept = accept
        if serve:
            self.serve = serve

    def __call__(self, req, server_sockfile, info):
        if self.accept(req, info):
            return self.serve(req, server_sockfile, info)
        else:
            # no resource to serve
            return ResponsePack(res=None, server_sockfile=server_sockfile)


class ResponseServers(object):

    def __init__(self, response_servers=[]):

        self._response_servers = response_servers

    def __call__(self, req, server_sockfile, info):
        respack = None
        for response_server in self._response_servers:
            respack = response_server(req, server_sockfile, info)
            if respack is None:
                # must disconnect
                return None
            if respack.res is not None:
                # serve resource
                return respack
            if respack.res is None:
                # can not serve. next turn
                server_sockfile = respack.server_sockfile
                continue

        # no resource to serve
        return ResponsePack(res=None, server_sockfile=server_sockfile)

# decorator


def response_server_with_recognizer(recognizer):
    def deco(func):
        @functools.wraps(func)
        def wrapper(req, server_sockfile, info):
            if not recognizer(req, info):
                return ResponsePack(res=None, server_sockfile=server_sockfile)
            return func(req, server_sockfile, info)
        return wrapper
    return deco
