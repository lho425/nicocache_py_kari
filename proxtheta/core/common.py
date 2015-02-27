# -*- coding: utf-8 -

from . import utility
import traceback
from collections import namedtuple


class Object(object):
    pass


AddressTuple = namedtuple("AddressTuple", "host port")


class Address(AddressTuple):

    def __new__(self, addr):
        """addr: (host, port)"""
        return AddressTuple.__new__(self, *addr)

    def __str__(self):
        return str((self.host, self.port))


class ResponsePack(object):

    """
    res: httpmes.HTTPResponse or None(default=None),
    body_file: str or file or None(default=None),
    server_sockfile: SocketWrapper ( reuse server_sockfile
        (In other words socket) for next request handling if possible. default=None)
    """

    def __init__(self, res, body_file=None, server_sockfile=None):
        self.res = res
        self.body_file = body_file
        self.server_sockfile = server_sockfile
        return

    def close_body_file(self):
        utility.close_if_not_None(self.body_file)

    def close_all(self):
        """close body_file and server_sockfile safely
        can raise exception"""

        exception_list = []
        try:
            utility.close_if_not_None(self.body_file)
        except Exception as e:
            e.nested_stacktrace = traceback.format_exc()
            exception_list.append(e)

        try:
            utility.close_if_not_None(self.server_sockfile)
        except Exception as e:
            e.nested_stacktrace = traceback.format_exc()
            exception_list.append(e)

        if len(exception_list) == 1:
            raise exception_list[0]

        if len(exception_list) == 2:
            exception_list[1].args += (exception_list[0],)
            raise exception_list[1]

    def close(self):
        """maybe used for exception handling"""
        self.close_all()
