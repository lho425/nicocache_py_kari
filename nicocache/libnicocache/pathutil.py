# -*- coding: utf-8 -
import os
import logging as _logging

logger = _logging.getLogger(__name__)


class FileSystemWrapper(object):

    def __init__(self, walk=os.walk):
        self._walk = walk

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


class DirCahingWalker:

    def __init__(self, top, topdown=True, onerror=None, followlinks=False):
        self._top_dir = os.path.normpath(top)

        self._real_walk = os.walk
        self._topdown = topdown
        self._onerror = onerror
        self._followlinks = followlinks

        logger.info("make file list cache")
        # [(dirpath, dirnames, filenames), ...]
        self._pathlist = list(
            self._real_walk(self._top_dir, topdown, onerror, followlinks))

        self._dir_mtime = {}

        for (dirpath, _, _) in self._pathlist:
            self._dir_mtime[dirpath] = self._getmtime(dirpath)

        logger.info("finish making file list cache")

    def _getmtime(self, path):
        try:
            return os.path.getmtime(os.path.realpath(path))
        except OSError as e:
            if e.errno == 2:
                # symlink is broken.

                # cygwinでuncパスへのリンクをしている場合もここにきてしまう
                # \\SMB\dirへのリンクが
                # //SMB/dirになってしまい
                # 正規化されて/SMB/dirになってしまう
                return os.path.getmtime(path)
            else:
                raise

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        if os.path.normpath(top) != self._top_dir:
            # todo!!! 他の引数も__init__で渡されたのと等しいかチェックすべし
            raise NotImplementedError(
                "top must be top of given on DirCahingWalker.__init__()")

        pathlist = []
        for (dirpath, dirnames, filenames) in self._pathlist:
            if not os.path.exists(dirpath):
                continue

            if self._getmtime(dirpath) != self._dir_mtime[dirpath]:
                logger.info("directory changed: %s", dirpath)
                old_dirnames_set = set(dirnames)
                (dirpath, dirnames, filenames) = next(self._real_walk(
                    dirpath, self._topdown, self._onerror, self._followlinks))
                self._dir_mtime[dirpath] = self._getmtime(dirpath)
                pathlist.append((dirpath, dirnames, filenames))

                new_dirnames_set = set(dirnames)
                added_dirnames_set = new_dirnames_set - old_dirnames_set

                for dirname in added_dirnames_set:
                    for (dirpath, dirnames, filenames)in self._real_walk(
                            os.path.join(dirpath, dirname), self._topdown,
                            self._onerror, self._followlinks):

                        self._dir_mtime[dirpath] = self._getmtime(dirpath)
                        pathlist.append((dirpath, dirnames, filenames))

                continue

            pathlist.append((dirpath, dirnames, filenames))

        self._pathlist = pathlist
        return self._pathlist

    def rename_file(self, oldpath, newpath):
        # todo!!!排他処理
        oldpath_dirname = os.path.normpath(os.path.dirname(oldpath))
        oldpath_basename = os.path.basename(oldpath)

        newpath_dirname = os.path.normpath(os.path.dirname(newpath))
        newpath_basename = os.path.basename(newpath)

        # oldpath_basenameが所属しているfilenamesからoldpath_basenameを消す
        # dirpath == newpath_dirname となったときにfilenamesにnewpath_basenameを加える
        for (dirpath, dirnames, filenames) in self._pathlist:
            # todo!!! 遅くなるようなら、self._pathlistにあるpathは常に正規化されているようにする
            if oldpath_dirname == os.path.normpath(dirpath):
                filenames.remove(oldpath_basename)
                self._dir_mtime[oldpath_dirname] = self._getmtime(
                    oldpath_dirname)

            if newpath_dirname == os.path.normpath(dirpath):
                filenames.append(newpath_basename)
                self._dir_mtime[newpath_dirname] = self._getmtime(
                    newpath_dirname)

            # わかりにくいけど、これで書き換えられている
            # self._pathlistの要素やself._pathlist[i] (type: tuple)
            # の要素を書き換えているわけではないので
            # listを作りなおしてself._pathlistに代入する必要はない

    def remove_file(self, path):
        # todo!!!排他処理
        path_dirname = os.path.normpath(os.path.dirname(path))
        path_basename = os.path.basename(path)

        for (dirpath, dirnames, filenames) in self._pathlist:
            # todo!!! 遅くなるようなら、self._pathlistにあるpathは常に正規化されているようにする
            if path_dirname == os.path.normpath(dirpath):
                filenames.remove(path_basename)
                self._dir_mtime[path_dirname] = self._getmtime(path_dirname)

            # わかりにくいけど、これで書き換えられている
            # self._pathlistの要素やself._pathlist[i] (type: tuple)
            # の要素を書き換えているわけではないので
            # listを作りなおしてself._pathlistに代入する必要はない

    def append_file(self, path):
        """重複はしない"""
        # todo!!!排他処理
        path_dirname = os.path.normpath(os.path.dirname(path))
        path_basename = os.path.basename(path)

        for (dirpath, dirnames, filenames) in self._pathlist:
            # todo!!! 遅くなるようなら、self._pathlistにあるpathは常に正規化されているようにする
            if path_dirname == os.path.normpath(dirpath):
                if path_basename not in filenames:
                    filenames.append(path_basename)
                self._dir_mtime[path_dirname] = self._getmtime(path_dirname)

            # わかりにくいけど、これで書き換えられている
            # self._pathlistの要素やself._pathlist[i] (type: tuple)
            # の要素を書き換えているわけではないので
            # listを作りなおしてself._pathlistに代入する必要はない


class DirCachingFileSystemWrapper(FileSystemWrapper):

    def __init__(self, top_dir):
        self._caching_walker = DirCahingWalker(top_dir, followlinks=True)

        FileSystemWrapper.__init__(self, self._caching_walker.walk)

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return self._caching_walker.walk(top, topdown, onerror, followlinks)

    def open(self, path, mode="rb"):
        fileobj = FileSystemWrapper.open(self, path, mode=mode)
        if mode.startswith("w"):
            self._caching_walker.append_file(path)
        return fileobj

    def rename(self, oldpath, newpath):

        if os.path.isdir(oldpath):
            raise NotImplementedError(
                "renaming or removing directory is not implemented")

        FileSystemWrapper.rename(self, oldpath, newpath)
        # if os.rename failed(raised), dir entry of walker will not be updated.

        self._caching_walker.rename_file(oldpath, newpath)

    def remove(self, path):
        if os.path.isdir(path):
            raise NotImplementedError(
                "renaming or removing directory is not implemented")

        FileSystemWrapper.remove(self, path)

        self._caching_walker.remove_file(path)
