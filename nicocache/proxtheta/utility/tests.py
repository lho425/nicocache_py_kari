# -*- coding: utf-8 -

import unittest
from . import proxy
from ..core import httpmes
from ..core.common import ResponsePack
from ..core.iowrapper import FileWrapper
import os
from . import server
import StringIO
from gzip import GzipFile


class TestFilteringResponseServers(unittest.TestCase):

    def mock_response_server(self, req, fileobj, *_, **__):
        fileobj.close()
        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))
        res.headers["Connection"] = "close"
        return ResponsePack(res, body_file=FileWrapper(StringIO.StringIO("test")))

    def mock_response_server_chunked(self, req, fileobj, *_, **__):
        fileobj.close()
        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))
        res.headers["Transfer-Encoding"] = "chunked"
        res.headers["UNK-Encoding"] = "chunked"
        s = "2\r\nte\r\n2\r\nst\r\n0\r\n"

        return ResponsePack(res, body_file=FileWrapper(StringIO.StringIO(s)))

    def mock_response_server_gzip(self, req, fileobj, *_, **__):
        fileobj.close()
        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))
        res.headers["Content-Encoding"] = "gzip"
        res.headers["Connection"] = "close"
        sio = StringIO.StringIO()
        gf = GzipFile(fileobj=sio, mode="wb")
        gf.write("test")
        gf.close()
        sio.seek(0, 0)

        return ResponsePack(res, body_file=FileWrapper(StringIO.StringIO(sio.read())))

    def my_res_filter(self, res, *_, **__):
        res.body = res.body * 3
        return res

    def test(self):
        req = httpmes.HTTPRequest(
            ("GET",
             ("http", "linuxjm.sourceforge.jp", None,
              "/html/LDP_man-pages/man2/socket.2.html", "", ""),
             "HTTP/1.1"))
        req.headers["Host"] = req.host
        fress = proxy.FilteringResponseServers(
            response_servers=[
                server.ResponseServer(serve=self.mock_response_server)],  # changed
            response_filters=[proxy.ResponseFilter(filtering=self.my_res_filter)])
        r = fress(req, FileWrapper(open(os.devnull, "w")), None)
        r.close()
        self.assertEquals(r.res.body, "test" * 3)

    def test_chunked(self):
        req = httpmes.HTTPRequest(
            ("GET",
             ("http", "linuxjm.sourceforge.jp", None,
              "/html/LDP_man-pages/man2/socket.2.html", "", ""),
             "HTTP/1.1"))
        req.headers["Host"] = req.host
        fress = proxy.FilteringResponseServers(
            response_servers=[
                server.ResponseServer(serve=self.mock_response_server_chunked)],  # changed
            response_filters=[proxy.ResponseFilter(filtering=self.my_res_filter)])
        r = fress(req, FileWrapper(open(os.devnull, "w")), None)
        r.close()
        self.assertEquals(r.res.body, "test" * 3)

    def test_gunzip(self):
        req = httpmes.HTTPRequest(
            ("GET",
             ("http", "linuxjm.sourceforge.jp", None,
              "/html/LDP_man-pages/man2/socket.2.html", "", ""),
             "HTTP/1.1"))
        req.headers["Host"] = req.host
        fress = proxy.FilteringResponseServers(
            response_servers=[
                server.ResponseServer(serve=self.mock_response_server_gzip)],  # changed
            response_filters=[proxy.ResponseFilter(filtering=self.my_res_filter)])
        r = fress(req, FileWrapper(open(os.devnull, "w")), None)
        r.close()
        self.assertEquals(r.res.body, "test" * 3)

if __name__ == "__main__":
    unittest.main()
