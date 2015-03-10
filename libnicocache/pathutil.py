# -*- coding: utf-8 -
import os


class FileSystemWrapper(object):

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return os.walk(top, topdown, onerror, followlinks)

    def rename(self, oldpath, newpath):
        os.rename(oldpath, newpath)

    def remove(self, path):
        os.remove(path)

    def open(self, path, mode="rb"):
        return open(path, mode)

    def getmtime(self, path):
        return os.path.getmtime(path)

    def touch(self, path):
        os.utime(path, None)
