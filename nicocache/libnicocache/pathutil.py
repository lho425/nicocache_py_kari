# -*- coding: utf-8 -
import os
import logging as _logging
import locale

logger = _logging.getLogger(__name__)


def _convert_unicode(string):
    if isinstance(string, unicode):
        return string
    else:
        return string.decode(locale.getpreferredencoding())


def make_unicode_walk(walk):
    def unicode_walk(top, topdown=True, onerror=None, followlinks=False):
        for (dirpath, dirnames, filenames) in walk(
                top, topdown, onerror, followlinks):

            dirpath = _convert_unicode(dirpath)
            dirnames = [_convert_unicode(dirname) for dirname in dirnames]
            filenames = [_convert_unicode(filename) for filename in filenames]

            yield (dirpath, dirnames, filenames)

    return unicode_walk


class FileSystemWrapper(object):

    def __init__(self, walk=os.walk):
        self._walk = make_unicode_walk(walk)

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return self._walk(top, topdown, onerror, followlinks)

    def rename(self, oldpath, newpath):
        return os.rename(oldpath, newpath)

    def remove(self, path):
        return os.remove(path)

    def open(self, path, mode="rb"):
        return open(path, mode)

    def getmtime(self, path):
        return os.path.getmtime(path)

    def touch(self, path):
        os.utime(path, None)
