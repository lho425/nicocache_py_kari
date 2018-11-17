import unittest

from ..server import (streaming, trancefer_chunked, transfer_resbody_to_client)

from .helper import *

from ...core import httpmes

from io import BytesIO


class Test_streaming(unittest.TestCase):

    def test_size_not_given(self):

        data = b"abcdc" * 10
        src = BytesIO(data)
        dest = BytesIO()

        streaming(src, dest)

        self.assertEqual(data, dest.getvalue())

    def test_size_given(self):

        data = b"abcdc" * 10
        src = BytesIO(data)
        dest = BytesIO()

        streaming(src, dest, size=10)

        self.assertEqual(data[0:10], dest.getvalue())


class Test_trancefer_chunked(unittest.TestCase):

    def test(self):

        srcf = create_chunked_body_file([b"abc", b"def", b"ghi"])

        destf = BytesIO()

        trancefer_chunked(srcf, destf)

        self.assertEqual(srcf.getvalue(), destf.getvalue())

    @unittest.expectedFailure
    def test_with_chunk_extension(self):

        srcf = create_chunked_body_file(
            [(b"abc", 'ext1', 'ext2="val"'), b"def", b"ghi"])

        destf = BytesIO()

        trancefer_chunked(srcf, destf)

        self.assertEqual(srcf.getvalue(), destf.getvalue())


class Test_transfer_resbody_to_client(unittest.TestCase):

    def test_transfer_304(self):

        res = create_http11_response(304, "not modified")

        body_file = BytesIO(b"no body expected on 304")

        client_file = BytesIO()

        transfer_resbody_to_client(res, body_file, client_file)

        self.assertEqual(b"", client_file.getvalue())

    def test_CONNECT(self):

        res = create_http11_response(200, "OK")

        body_file = BytesIO()

        client_file = BytesIO()

        with self.assertRaises(RuntimeError):
            transfer_resbody_to_client(res, body_file, client_file)

    def test_CONNECT_with_req(self):

        req = httpmes.create_http11_request(
            method="CONNECT", uri="testhost.test:8888")

        res = create_http11_response(200, "OK")

        body_file = BytesIO()

        client_file = BytesIO()

        with self.assertRaises(RuntimeError):
            transfer_resbody_to_client(res, body_file, client_file, req)
