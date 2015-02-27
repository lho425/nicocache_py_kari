# -*- coding: utf-8 -
import logging as _logging
import socket
#from . import utility

# 原則close()を呼んだらラップしているfile object もcloseする
# 別のラッパーをラップしてる場合、別のラッパーも上の挙動をするようにする
# しかし、close()を呼んでもfile objectをclose()したくない時はFileWrapperの__init_でclose=falseを渡す
import sys
import common


class FileWrapper(object):
    logger = _logging.getLogger(__name__ + ".FileWrapper")

    _delegating_methods = ["flush", "write", "writelines",
                           "readlines", "__iter__", "next"]

    def __init__(self, file, close=True):
        """
        This is  file object or socket delegator.
        if close==True, self.close() will call file.flush() and file.close()
        else, self.close() will call only file.flush()
        """


# delegate to file
#         for attr_name in self._delegating_methods:
#             setattr(self, attr_name, getattr(file, attr_name))

        self._file = file
        self._close = close
        self._closed = False

    def write(self, data):
        return self._file.write(data)

    def writelines(self, sequence_of_strings):
        return self._file.writelines(sequence_of_strings)

    def flush(self):
        return self._file.flush()

    def readlines(self):
        return self._file.readlines()

    def seek(self, pos, mode=0):
        return self._file.seek(pos, mode)

    def tell(self):
        return self._file.tell()

    def __iter__(self):
        return self._file.__iter__()

    def next(self):
        return self._file.next()

    def close(self):
        try:
            self.logger.debug("close() called")
            self.logger.debug("already closed=%s", self.closed)
            self.flush()
            if self._close:
                self.logger.debug("call wrapped file close()")
        finally:
            if self._close:
                try:
                    self._file.close()
                except:
                    pass
            self._closed = True

    def __del__(self):
        if not self._closed:
            try:
                sys.stderr.write(
                    "FileWrapper was closed by GC! Resource leaking!\n")
                sys.stderr.write(object.__repr__(self) + "\n")
            except:
                pass

            try:
                self.close()
            except:
                pass

    def _getclosed(self):
        return self._closed
    closed = property(_getclosed, doc=socket._fileobject.closed.__doc__)

    def read(self, size=-1):
        self.flush()
        return self._file.read(size)

    def readline(self, size=-1):
        self.flush()
        return self._file.readline(size)

    def make_unclosable_dup(self):
        """unclosable means close=False. see doc of __init__"""
        return FileWrapper(self, close=False)


# todo!!! addressのフォーマットがipv4とipv6で違う事をドキュメントで述べ�?
# socket.getaddrinfoのドキュメントにかいてある
class SocketWrapper(FileWrapper):

    def __init__(self, sock, address=None):
        """Give connected socket. Do not touch sock after make SocketWrapper"""
#         if not isinstance(sock, socket.socket):
#             raise TypeError("Give socket.socket object. But given " + str(sock.__class__) + " object.")

        if address is None:
            address = sock.getpeername()

        self.address = common.Address(address)
        # fixme!!! socket._fileobject and sock._sock are dipending
        # implimention!
        FileWrapper.__init__(
            self, socket._fileobject(sock._sock, "rw", True), close=True)

    def __del__(self):
        if not self._closed:
            try:
                sys.stderr.write(
                    "SocketWrapper was closed by GC! Resource leaking!\n")
                sys.stderr.write(
                    self.__class__.__name__ + ", " + str(self.address) + "\n")
            except:
                pass

            try:
                self.close()
            except:
                pass

    def close(self):
        self.logger.debug("%s: SocketWrapper.close() called", self.address)
        return FileWrapper.close(self)


def create_sockfile((host, port)):
    address = (host, port)
    return SocketWrapper(socket.create_connection(address), address)
