# -*- coding: utf-8 -

import unittest

from ...core.httpmes import create_http11_response

from ..common import (copy_file, extract_chunked_body_file,
                      load_chunked_body, load_body, unzip_http_body)

from .helper import *

class Test_copy_file(unittest.TestCase):

    def test_with_size(self):

        f1 = BytesIO(b"隣の客はよく柿食う客だ")

        f2 = BytesIO()

        copy_file(f1, f2, size=len(f1.getvalue()))

        self.assertEqual(f1.getvalue(), f2.getvalue())

    def test_without_size(self):

        f1 = BytesIO(b"隣の客はよく柿食う客だ")

        f2 = BytesIO()

        copy_file(f1, f2, size=-1)

        self.assertEqual(f1.getvalue(), f2.getvalue())




class Test_extract_chunked_body_file(unittest.TestCase):

    def test(self):
        chunked = create_chunked_body_file([b"あいうえおあああ"] * 10)
        extracted = extract_chunked_body_file(chunked)
        self.assertEqual(b"あいうえおあああ" * 10, extracted)


class Test_load_chunked_body(unittest.TestCase):

    def test(self):

        res = create_http11_response(200, "OK",
                                     headers={"Transfer-Encoding": "chunked"}, body=None)

        body_file = create_chunked_body_file([b"あいうえおあああ"] * 10)

        res = load_chunked_body(res, body_file)

        self.assertEqual(b"あいうえおあああ" * 10, res.body)
        self.assertEqual(len(b"あいうえおあああ" * 10), res.get_content_length())


class Test_load_body(unittest.TestCase):

    def test_normal_file(self):

        res = create_http11_response(200, "OK",
                                     body=None)

        body_file = BytesIO(b"あいうえおあああ" * 10)
        res.set_content_length(len(body_file.getvalue()))

        res = load_body(res, body_file)

        self.assertEqual(b"あいうえおあああ" * 10, res.body)
        self.assertEqual(len(b"あいうえおあああ" * 10), res.get_content_length())

    def test_chunked(self):

        res = create_http11_response(200, "OK",
                                     headers={"Transfer-Encoding": "chunked"}, body=None)

        body_file = create_chunked_body_file([b"あいうえおあああ"] * 10)

        res = load_body(res, body_file)

        self.assertEqual(b"あいうえおあああ" * 10, res.body)
        self.assertEqual(len(b"あいうえおあああ" * 10), res.get_content_length())




class Test_unzip_http_body(unittest.TestCase):

    def test_gzip(self):

        res = create_gzip_response(b"あいうえおあああ" * 10)

        res = unzip_http_body(res)

        self.assertEqual(b"あいうえおあああ" * 10, res.body)
        self.assertEqual(len(b"あいうえおあああ" * 10), res.get_content_length())

    def test_zzip(self):
        res = create_zzip_response(b"あいうえおあああ" * 10)

        res = unzip_http_body(res)

        self.assertEqual(b"あいうえおあああ" * 10, res.body)
        self.assertEqual(len(b"あいうえおあああ" * 10), res.get_content_length())


class Test_is_same_host_and_port(unittest.TestCase):
    pass
