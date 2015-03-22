# -*- coding: utf-8 -


import functools
import socket
import errno
import logging as _logging

from . import common, client, server
from .common import EmptyResponseError, Holder, ExceptionSafeHolder
from .server import is_request_to_this_server
from ..core.common import ResponsePack
from ..core import httpmes
from ..core.utility import close_if_not_None
import StringIO
import traceback

logger = _logging.getLogger(__name__)


def convert_upstream_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.debug("@convert_upstream_error: "
                             "catch exception: \n%s",
                             traceback.format_exc())
                raise

        except (socket.gaierror, EmptyResponseError) as e:
            return ResponsePack(httpmes.HTTP11Error((502, "Bad Gateway")))

        except socket.timeout as e:
            return ResponsePack(httpmes.HTTP11Error((504, "Gateway Timeout")))

        except socket.error as e:
            if e.errno == errno.ETIMEDOUT:
                return ResponsePack(
                    httpmes.HTTP11Error(
                        (504, "Gateway Timeout")))
            else:
                raise

    return wrapper


ResponseServer = server.ResponseServer
ResponseServers = server.ResponseServers


class RequestFilter(object):

    # 継承し、acceptとfilteringをオーバーライドする
    # もしくは__init__の引数に関数をわたす

    # 1プロセス:1インスタンスなので注意
    # クライアントごとにインスタンスが作られるわけではない!

    @staticmethod
    def accept(req, info):
        return True

    @staticmethod
    def filtering(req, info):
        return req

    def __init__(self, accept=None, filtering=None):
        if accept:
            self.accept = accept
        if filtering:
            self.filtering = filtering

    def __call__(self, req, info):
        if self.accept(req, info):
            req = self.filtering(req, info)

        return req


class ResponseFilter(object):
    # 継承し、acceptとload_bodyとfilteringをオーバーライドする
    # もしくは__init__の引数に関数をわたす
    # 圧縮されていても解凍してからfilteringに渡すので心配する必要はない
    # chunkedなコンテンツも同様
    # ヘッダのみににフィルタを掛けたい場合load_bodyがFalseを返すようにすればよい
    # 解凍出来ないコンテンツはそのままfilteringに渡す

    # 1プロセス:1インスタンスなので注意
    # クライアントごとにインスタンスが作られるわけではない!

    @staticmethod
    def accept(res, req, info):

        return True

    @staticmethod
    def load_body(res, req, info):
        return res.headers.get("Content-Type", "text").startswith("text")

    @staticmethod
    def filtering(res, req, info):
        return res

    def __init__(self, accept=None, load_body=None, filtering=None):
        if accept:
            self.accept = accept
        if filtering:
            self.filtering = filtering

    def __call__(self, res, body_file, req, info):
        # めずらしく我ながら汚いコードに
        # やりたいこと

        #                   |圧縮されている    chunked
        # bodyがロードされている     |
        # bodyがロードされていない  |

        # もしbodyを読まなくていいなら、もしくはプレーンテキストとしてbodyが既にロードされているなら
        #     即フィルタリングする
        # else
        #    bodyが既にロードされているなら、stringioに入れ直す
        #    chunkedならまずchunkedを解消する
        #    次に圧縮を解消する
        #    フィルタリングする
        with Holder(body_file) as body_file_hldr:
            if not self.accept(res, req, info):
                return res, body_file_hldr.release()

            if ((not self.load_body(res, req, info)) or
                    not (res.is_chunked() and
                         res.headers.get("Content-Encoding", "") != "") and
                    res.body is not None):
                # not have to load body
                # or
                # response body already loaded as plain text
                res = self.filtering(res, req, info)
                return res, body_file_hldr.release()

            if body_file_hldr.obj is None:
                # response body already loaded
                # but i want to use only body_file_hldr...
                body_file_hldr.obj = StringIO.StringIO(res.body)
                res.body = None

            assert body_file_hldr.obj is not None

            if res.is_chunked():
                res = common.load_chunked_body(
                    res, body_file_hldr.release())
                body_file_hldr.obj = StringIO.StringIO(res.body)
                res.body = None

            assert body_file_hldr.obj is not None

            res = common.unzip_http_body(
                res, body_file_hldr.release(), req)

            if "Content-Encoding" in res.headers:
                # body is unknown encoding. not unziped
                assert body_file_hldr.obj is None
                logger.warning("unkkown Content-Encoding: %s."
                               "response filtering skipped.", res.headers["Content-Encoding"])
                return res, None

            res = self.filtering(res, req, info)
            assert body_file_hldr.obj is None
            return res, None


class FilteringResponseServers(object):

    def __init__(self,
                 request_filters=[],
                 response_servers=[],
                 response_filters=[]):
        """
        request_filters: list of RequestFilter
        response_servers: list of ResponseServers
        response_filter: list of ResponseFilter

        if filtering or response_server return None,
        __call__() will immediately return None.

        args are list of above three functions."""

        self._response_server = ResponseServers(
            response_servers)

        self._request_filters = request_filters
        self._response_filters = response_filters

    def __call__(self, req, server_sockfile, info):
        with Holder(server_sockfile)\
                as server_sockfile_hldr:

            for request_filter in self._request_filters:
                req = request_filter(req, info)
                if req is None:
                    return None

            respack = self._response_server(
                req, server_sockfile_hldr.release(), info)

            if respack is None:
                return None
            if respack.res is None:
                return respack

            res = respack.res
            server_sockfile_hldr.set(respack.server_sockfile)
            with Holder(respack.body_file) as body_file_hldr:

                for response_filter in self._response_filters:
                    res, body_file = \
                        response_filter(
                            respack.res, body_file_hldr.release(), req, info)
                    body_file_hldr.set(body_file)

                    if res is None:
                        return None

                respack.res = res
                respack.body_file = body_file_hldr.release()
                respack.server_sockfile = server_sockfile_hldr.release()

            assert body_file_hldr.obj is None
            assert server_sockfile_hldr.obj is None

            return respack
