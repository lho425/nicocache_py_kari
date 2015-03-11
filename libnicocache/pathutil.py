# -*- coding: utf-8 -
import os
import logging as _logging

logger = _logging.getLogger(__name__)


class DirCahingWalker:
    pass


class FileSystemWrapper(object):

    def __init__(self, walk=os.walk):
        self._walk = walk

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return self._walk(top, topdown, onerror, followlinks)

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


class DirCachingFileSystemWrapper(FileSystemWrapper):

    def __init__(self):
        self._caching_walker = DirCahingWalker()

        FileSystemWrapper.__init__(self, self._caching_walker.walk)

    def rename(self, oldpath, newpath):

        # todo!!!排他処理
        # ミューテックスを使う
        # walker側には排他処理を付けない
        # walkerを外部から注入したくなった場合は、クラスを渡すようにする

        os.rename(oldpath, newpath)
        # if os.rename failed(raised), dir entry of walker will not be updated.

        self._caching_walker.rename(oldpath, newpath)

    def remove(self, path):

        # todo!!!排他処理
        # ミューテックスを使う
        # walker側には排他処理を付けない
        # walkerを外部から注入したくなった場合は、クラスを渡すようにする

        os.remove(path)
        # if os.remove failed(raised), dir entry of walker will not be updated.

        self._caching_walker.remove(path)
