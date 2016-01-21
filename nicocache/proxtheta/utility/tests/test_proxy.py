# -*- coding: utf-8 -

import unittest
from .helper import *

from .. import proxy
from ..proxy import (
    convert_upstream_error, RequestFilter, ResponseFilter, FilteringResponseServers)

from ...core import httpmes
from ...core.common import ResponsePack
from ...core.iowrapper import FileWrapper
from ...core import httpmes
from ..common import EmptyResponseError
from ..server import ResponseServer

import os
import socket
import errno
import StringIO
from gzip import GzipFile
from io import BytesIO


class TestGzipFile(unittest.TestCase):

    def test_unzip_invalid(self):

        bio = BytesIO(b"test")
        bio.seek(0)
        with self.assertRaises(IOError):
            with GzipFile(fileobj=bio) as f:
                f.read()


class Test_convert_upstream_error(unittest.TestCase):

    def test_raise_EmptyResponseError(self):
        def func():
            raise EmptyResponseError(("test", 80))

        r = convert_upstream_error(func)()

        self.assertEqual(502, r.res.status_code)

    def test_raise_gaierror(self):
        def func():
            raise socket.gaierror

        r = convert_upstream_error(func)()

        self.assertEqual(502, r.res.status_code)

    def test_raise_timeout(self):
        def func():
            raise socket.timeout

        r = convert_upstream_error(func)()

        self.assertEqual(504, r.res.status_code)

    def test_raise_ETIMEDOUT(self):
        def func():
            raise socket.error(errno.ETIMEDOUT, "")

        r = convert_upstream_error(func)()

        self.assertEqual(504, r.res.status_code)

    def test_raise_non_upstream_error(self):
        def func():
            raise socket.error

        with self.assertRaises(socket.error):
            r = convert_upstream_error(func)()


class TestRequestFilter(unittest.TestCase):

    def _make_filtered_get_request(self, accept, filtering, headers):

        reqfilter = RequestFilter(accept, filtering)

        req = httpmes.create_http11_request(uri="test://test", headers=headers)

        req = reqfilter(req, None)

        return req

    def test(self):

        def accept(req, info):
            return True

        def filtering(req, info):
            req.headers["Test"] = "test"
            return req

        req = self._make_filtered_get_request(
            accept, filtering, headers={"Test": "0"})

        self.assertEqual("test", req.headers["Test"])

    def test_not_filtered(self):

        def accept(req, info):
            return False

        def filtering(req, info):
            req.headers["Test"] = "test"
            return req

        req = self._make_filtered_get_request(
            accept, filtering, headers={"Test": "0"})

        self.assertEqual("0", req.headers["Test"])


class TestResponseFilter(unittest.TestCase):

    def _aplly_filter(self, accept, filtering, res):
        resfilter = ResponseFilter(accept, load_body=None, filtering=filtering)

        res, body_file = resfilter(res, body_file=None, req=None, info=None)

        return res, body_file

    def test(self):

        def accept(res, req, info):
            return True

        def filtering(res, req, info):
            res.set_body("filtered")
            return res

        res = httpmes.create_http11_response(200, "OK", body="original")

        res, body_file = self._aplly_filter(accept, filtering, res)

        self.assertEqual("filtered", res.body)

    def test_gziped(self):

        def accept(res, req, info):
            return True

        def filtering(res, req, info):
            res.set_body("filtered")
            return res

        res = create_gzip_response("original")
        assert res.headers["Content-Encoding"] == "gzip"

        res, body_file = self._aplly_filter(accept, filtering, res)

        self.assertEquals(None, res.headers.get("Content-Encoding"))
        self.assertEquals("filtered", res.body)

    def test_invalid_gziped(self):

        def accept(res, req, info):
            return True

        def filtering(res, req, info):
            res.set_body("filtered")
            return res

        res = create_gzip_response("original")

        # make corrupt gzip file
        res.set_body("0")

        with self.assertRaises(IOError):
            res, body_file = self._aplly_filter(accept, filtering, res)

        # must not be changed on unzip error
        self.assertEqual("0", res.body)

    def test_not_filtering(self):

        def accept(res, req, info):
            return False

        def filtering(res, req, info):
            res.set_body("filtered")
            return res

        res = httpmes.create_http11_response(200, "OK", body="original")

        res, body_file = self._aplly_filter(accept, filtering, res)

        self.assertEqual("original", res.body)


class TestFilteringResponseServers(unittest.TestCase):

    def mock_response_server(self, req, *_, **__):
        res = create_http11_response(
            200, "OK", {"connection": "close"}, body="test")
        return ResponsePack(res)

    def mock_response_server_chunked(self, req, *_, **__):
        body_file = create_chunked_body_file(["te", "s", "t"])
        res = create_http11_response(
            200, "OK", {"Transfer-Encoding": "chunked"})

        return ResponsePack(res, body_file)

    def mock_response_server_gzip(self, req, *_, **__):
        res = create_gzip_response("test")

        return ResponsePack(res)

    def my_res_filter(self, res, *_, **__):

        res.headers["Test"] = "test"
        res.set_body(res.body * 3)
        return res

    def _test_with_mock_response_server(self, mock_response_server):
        req = httpmes.create_http11_request(uri="http://test/index.html")
        fress = FilteringResponseServers(
            response_servers=[
                ResponseServer(serve=mock_response_server)],
            response_filters=[ResponseFilter(filtering=self.my_res_filter)])
        r = fress(req, server_sockfile=None, info=None)
        r.close()
        self.assertEquals("test", r.res.headers["Test"])
        self.assertEquals("test" * 3, r.res.body)

    def test(self):

        self._test_with_mock_response_server(self.mock_response_server)

    def test_chunked(self):

        self._test_with_mock_response_server(self.mock_response_server_chunked)

    def test_gziped(self):
        self._test_with_mock_response_server(self.mock_response_server_gzip)
