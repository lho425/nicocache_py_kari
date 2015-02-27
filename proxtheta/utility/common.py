# -*- coding: utf-8 -
import logging as _logging
import gzip
import zlib
import StringIO

from .. import core
from ..core import httpmes
from ..core.utility import close_if_not_None

logger = _logging.getLogger(__name__)

safe_close = core.utility.safe_close


def copy_file(srcf, distf, size=-1, bufsize=8192):

    if size < 0:
        while 1:
            data = srcf.read(bufsize)
            if data:
                distf.write(data)
            else:
                return
    else:

        count = size // bufsize
        remainder = size % bufsize
        for _ in range(count):
            distf.write(srcf.read(bufsize))

        distf.write(srcf.read(remainder))
        distf.flush()
        return


def copy_chunked_body_file(srcf):
    """extract chunked data from srcf and copy to distf"""
    distf = StringIO.StringIO()
    while 1:
        size_str = srcf.readline()
        size = int(size_str, 16)  # fixme!!! can not handle chunk-extension
        if size == 0:
            srcf.readline()  # fixme!!! チャンク後ヘッダーの処理
            break
        else:
            copy_file(srcf, distf, size)
            srcf.readline()

    distf.seek(0, 0)

    return distf.read()


def load_chunked_body(res, body_resource):
    """body_resource is str or fileobj"""
    if isinstance(body_resource, str):
        body_file = StringIO.StringIO(body_resource)
    else:
        body_file = body_resource
    body = copy_chunked_body_file(body_file)
    del res.headers["Transfer-Encoding"]
    res.body = body
    res.set_content_length()
    body_file.close()
    return res


def unzip_http_body(res, body_file, hint_req=None):
    """unzip and load body to res.body.if not zipped, only loading body."""

    content = None
    # see rfc2616 3.5, 14.11
    content_encoding = res.headers.get("Content-Encoding", "")
    try:
        if content_encoding == "gzip" or content_encoding == "x-gzip":
            with gzip.GzipFile(fileobj=body_file) as f:
                content = f.read()
            del res.headers["Content-Encoding"]

        elif content_encoding == "deflate":
            ziped_content = body_file.read(res.get_content_length())
            content = zlib.decompress(ziped_content)
            del res.headers["Content-Encoding"]

        elif content_encoding == "" or content_encoding == "identity":
            content = body_file.read(res.get_content_length())
            del res.headers["Content-Encoding"]

        else:
            content = body_file.read(
                int(httpmes.get_transfer_length(res, hint_req)))

    except:
        body_file.close()
        raise

    body_file.close()
    body_file = None

    res.body = content
    res.set_content_length()

    return res


class EmptyResponseError(Exception):

    def __init__(self, (host, port), sentdata=None):
        self._hostport = (host, port)
        self._sentdata = sentdata

    def __str__(self):
        if self._sentdata is None:
            sentdatainfo = ""
        else:
            sentdatainfo = ("sent data is beyond:\n" + str(self._sentdata))
        return ("no response from " +
                str(self._hostport) + "\n" +
                sentdatainfo)


def is_same_host_and_port((host1, port1), (host2, port2)):
    """will not do name resolution because not all system do DNS cache."""
    return (host1, port1) == (host2, port2)


class Holder(object):

    def __init__(self, fileobj):
        """if name is not None, you can access content like hldr.name
        it's same as hder.get()
        for example,
        hldr = Holder(myobj, "myobj")
        hldr.myobj.func()
        """
        self._fileobj = fileobj

#     def __getattr__(self, name):
#         if name == self.__dict__["_content_name"]:
#             return self.get()
#         else:
#             return object.__getattribute__(self, name)
#
#     def __setattr__(self, name, value):
#         if name == self.__dict__["_content_name"]:
#             self.set(value)
#         else:
#             object.__setattr__(self, name, value)

    def get(self):
        return self._fileobj

    def set(self, fileobj):
        if fileobj is not self._fileobj:
            close_if_not_None(self._fileobj)

        self._fileobj = fileobj

    obj = property(get, set)

    def release(self):

        fileobj = self._fileobj
        self._fileobj = None
        return fileobj

    def safe_close(self):
        safe_close(self._fileobj)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):

        self.safe_close()


class ExceptionSafeHolder(Holder):

    """close will be call when with suite is exited due to an exception.
    Of course, holder holds None object close will not be called."""

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            safe_close(self._fileobj)

if __name__ == "__main__":  # test
    with Holder(open("/dev/null", "w"), "devnull") as hldr:
        hldr.devnull.write("aaa")
        hldr.release().close()
        hldr.devnull.write("aaa")
        raise RuntimeError()
