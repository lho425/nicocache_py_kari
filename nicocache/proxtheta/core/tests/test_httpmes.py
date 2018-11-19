# -*- coding: utf-8 -
import unittest

from .. import httpmes


class TestHTTPHeaders(unittest.TestCase):
    @unittest.expectedFailure
    def test_add_header(self):
        headers = httpmes.get_empty_http_header()
        headers.add_header("test", "1")
        headers.add_header("test", "2")

        self.assertEqual(["1", "2"], headers.get_all("test"))


class TestHTTPRequest(unittest.TestCase):

    def test(self):
        req = httpmes.create_http11_request(uri="http://test.com:99"
                                            "/aaa/bbb?param1=aaa&param2=bbb&param1=ccc",
                                            headers={"Connection": "close"})
        self.assertEqual(req.host, "test.com")
        self.assertEqual(req.port, 99)
        self.assertEqual(req.query, "param1=aaa&param2=bbb&param1=ccc")
        self.assertEqual(req.headers["Connection"], "close")
        self.assertEqual(req.headers["Host"], "test.com:99")
        self.assertEqual(req.headers.get_all("Connection"), ["close"])


class TestHTTPRequestFromString(unittest.TestCase):

    def test(self):

        req_str = """\
GET http://test.com:99/aaa/bbb?param1=aaa&param2=bbb&param1=ccc HTTP/1.1\r
Connection: close\r
Myheader: aaa\r
Myheader: bbb\r
\r
hello
"""

        req = httpmes.HTTPRequest.create(req_str)
        self.assertEqual(req.host, "test.com")
        self.assertEqual(req.port, 99)
        self.assertEqual(req.query, "param1=aaa&param2=bbb&param1=ccc")
        self.assertEqual(req.headers["Connection"], "close")
        # req.headers.get_all("Connection")
        self.assertEqual(req.headers.getheaders("Connection"), ["close"])


class TestHTTPRequestFromTuple(unittest.TestCase):

    def test(self):

        req = httpmes.HTTPRequest(("GET", ("http", "test.com", 99, "/", "param1=aaa&param2=bbb&param1=ccc", ""),
                                   "HTTP/1.1"), headers={"Connection": "close"})

        self.assertEqual(req.host, "test.com")
        self.assertEqual(req.port, 99)
        self.assertEqual(req.query, "param1=aaa&param2=bbb&param1=ccc")
        self.assertEqual(req.headers["Connection"], "close")
        # req.headers.get_all("Connection")
        self.assertEqual(req.headers.getheaders("Connection"), ["close"])


class TestHTTPResponse(unittest.TestCase):

    def test_set_body(self):

        res = httpmes.create_http11_response(
            200, "OK", {"Test": "test", "Content-Encoding": "gzip"})

        res.set_body(b"abc")

        self.assertEqual(b"abc", res.body)
        self.assertEqual(3, res.get_content_length())
        self.assertEqual("test", res.headers["Test"])
        self.assertEqual("gzip", res.headers["Content-Encoding"])

    def test_set_body_to_text(self):

        res = httpmes.create_http11_response(
            200, "OK", {"Test": "test", "Content-Encoding": "gzip"})

        res.set_body("あいう")

        self.assertEqual("あいう".encode("utf-8"), res.body)
        self.assertEqual("text/plain; charset=utf-8",
                         res.headers["Content-Type"])
        self.assertEqual("test", res.headers["Test"])
        self.assertEqual("gzip", res.headers["Content-Encoding"])
