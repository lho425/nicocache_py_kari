from ...core.httpmes import create_http11_response
from io import BytesIO
from gzip import GzipFile
import zlib


def create_chunked_body_file(bytes_seq):
    """bytes_seq: [elem]
    elem: bytes or [bytes, chunk_extension, chunk_extension, ...]"""
    

    bio = BytesIO()

    for elem in bytes_seq:
        chunk_extensions = ()
        if isinstance(elem, bytes):
            bytes_data = elem
        else:
            bytes_data = elem[0]
            chunk_extensions = elem[1:]
            
        bio.write(b"%x" % (len(bytes_data)))
        for ext in chunk_extensions:
            bio.write(b";")
            bio.write(ext)
        bio.write(b"\r\n")
        bio.write(bytes_data)
        bio.write(b"\r\n")

    bio.write(b"0\r\n")
    bio.seek(0)

    return bio

def create_gzip_response(a_bytes):
    bio = BytesIO()
    gf = GzipFile(fileobj=bio, mode="wb")
    gf.write(a_bytes)
    gf.close()
    bio.seek(0, 0)

    res = create_http11_response(200, "OK",
                                 headers={"Content-Encoding": "gzip"}, body=bio.getvalue())

    return res


def create_zzip_response(a_bytes):
    res = create_http11_response(200, "OK",
                                 headers={"Content-Encoding": "deflate"}, body=zlib.compress(a_bytes))

    return res
