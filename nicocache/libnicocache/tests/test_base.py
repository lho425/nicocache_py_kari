# -*- coding: utf-8 -

import unittest
import os
import shutil
import logging as _logging
import io
import time

from ..base import VideoCacheInfo, VideoCacheFile, CacheAlreadyExistsError
from .. import pathutil
from ..filecachetool import CachingReader

verbosity = 1
root_test_dir_path = "./_testdir"

logger_for_test = _logging.getLogger("test")
logger_for_test.setLevel(_logging.ERROR)


class TestVideoCacheInfo(unittest.TestCase):

    def test(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")
        self.assertEqual(info.video_id, "sm12345")
        self.assertEqual(info.tmp, True)
        self.assertEqual(info.low, True)
        self.assertEqual(info.title, "title56789.avi")
        self.assertEqual(info.filename_extension, "mp4")
        self.assertEqual(info.subdir, "subdir1/subdir2")

    def test_create(self):
        info = VideoCacheInfo.create(
            rootdir="./cache/",
            video_id="sm12345",
            tmp=True,
            low=True,
            title="title56789.avi",
            filename_extension="mp4",
            subdir="subdir1/subdir2")

        self.assertEqual(
            os.path.normpath(info.make_cache_file_path()),
            os.path.normpath("./cache/subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"))

    def test_no_title(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")

        self.assertEqual(info.video_id, "sm12345")
        self.assertEqual(info.tmp, True)
        self.assertEqual(info.low, True)
        self.assertEqual(info.title, "")
        self.assertEqual(info.filename_extension, "mp4")
        self.assertEqual(info.subdir, "subdir1/subdir2")

    def test_no_filename_extension(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")

        self.assertEqual(info.video_id, "sm12345")
        self.assertEqual(info.tmp, True)
        self.assertEqual(info.low, True)
        self.assertEqual(info.title, "")
        self.assertEqual(info.filename_extension, "")
        self.assertEqual(info.subdir, "subdir1/subdir2")

    def test_cache_in_top_dir(self):
        cache_file_name = "tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")

        self.assertEqual(info.video_id, "sm12345")
        self.assertEqual(info.tmp, True)
        self.assertEqual(info.low, True)
        self.assertEqual(info.title, "title56789.avi")
        self.assertEqual(info.filename_extension, "mp4")
        # infoのsubdir,rootdirのpathは自動的に正規化されるので、注意!
        self.assertEqual(info.subdir, os.path.normpath(""))

    def test__make_cache_file_path(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")
        cachefilepath = info.make_cache_file_path()

        self.assertEqual(
            os.path.normpath(cachefilepath),
            os.path.normpath(os.path.join("./cache/", cache_file_name)))

    def test__match(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")
        query_info = VideoCacheInfo.make_query(
            video_id="sm12345", rootdir="./cache/")

        self.assertTrue(query_info.match(info))

    def test__match__not_match(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")
        query_info = VideoCacheInfo.make_query(
            video_id="sm12345", low=False, rootdir="./cache/")

        self.assertFalse(query_info.match(info))

    def test__replace(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")

        new_info = info.replace(subdir="././././save")

        self.assertEqual(new_info, VideoCacheInfo.create_from_relpath(
            "save/tmp_sm12345low_title56789.avi.mp4", rootdir="./cache/"), )


class NicoCacheTestCase(unittest.TestCase):

    @property
    def testdir_path(self):
        return self.get_testdir_path()

    def make_cache_file_path(self, filename):
        return os.path.join(root_test_dir_path, self.__class__.__name__, filename)

    def make_testdir(self):
        self.rm_testdir()
        os.makedirs(os.path.join(root_test_dir_path, self.__class__.__name__))

    def makedir(self, dirname):
        os.makedirs(
            os.path.join(root_test_dir_path, self.__class__.__name__, dirname))

    def make_file(self, filename):
        with open(os.path.join(root_test_dir_path, self.__class__.__name__, filename), "w"):
            pass

    def rm_testdir(self):
        shutil.rmtree(
            os.path.join(root_test_dir_path, self.__class__.__name__), ignore_errors=True)

    def get_real_path(self, path):
        return os.path.join(root_test_dir_path, self.__class__.__name__, path)

    def get_testdir_path(self):
        return os.path.join(root_test_dir_path, self.__class__.__name__)


class TestVideoCacheFile(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_file("tmp_sm10low_てすと.mp4")
        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        self.filesystem_wrapper = pathutil.FileSystemWrapper()


#     def test__get_video_cache_filepath__topdir(self):
#         filepath = self.video_cache_manager.\
#             get_video_cache_filepath("sm10")
#
#         self.assertEqual(os.path.basename(filepath), "sm10.mp4")

    def test__create(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm12345low_タイトル.mp4", rootdir=self.get_testdir_path())
        filepath = video_cache_info.make_cache_file_path()

        video_cache = VideoCacheFile(self.filesystem_wrapper, video_cache_info)

        video_cache.create()

        self.assertTrue(os.path.exists(filepath))

    def test__update_cache_info(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm10low_てすと.mp4", rootdir=self.get_testdir_path())

        new_video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm12345low_タイトル.mp4", rootdir=self.get_testdir_path())

        video_cache = VideoCacheFile(self.filesystem_wrapper, video_cache_info)

        video_cache.update_cache_info(new_video_cache_info)

        filepath = new_video_cache_info.make_cache_file_path()
        self.assertTrue(os.path.exists(filepath))

        oldfilepath = video_cache_info.make_cache_file_path()
        self.assertFalse(os.path.exists(oldfilepath))

    def test__create_new_file__already_exist_error(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm10low_てすと.mp4", rootdir=self.get_testdir_path())
        video_cache = VideoCacheFile(self.filesystem_wrapper, video_cache_info)

        with self.assertRaises(CacheAlreadyExistsError):
            video_cache.create()

    def test__remove_cache(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "subdir1/tmp_so20low_タイトル.avi.mp4",
            rootdir=self.get_testdir_path())
        video_cache = VideoCacheFile(self.filesystem_wrapper, video_cache_info)

        self.assertTrue(video_cache.exists())

        video_cache.remove()

        self.assertFalse(video_cache.exists())

    def test__touch(self):

        video_cache_info = VideoCacheInfo.create_from_relpath(
            "subdir1/tmp_so20low_タイトル.avi.mp4",
            rootdir=self.get_testdir_path())

        video_cache = VideoCacheFile(self.filesystem_wrapper, video_cache_info)

        mtime0 = video_cache.get_mtime()

        time.sleep(0.005)
        video_cache.touch()

        mtime1 = video_cache.get_mtime()

        self.assertTrue(mtime1 > mtime0)


class TestCachingReader(NicoCacheTestCase):

    def setUp(self):
        self.cachefile_len = 100
        self.origfile_len = 100

        self.make_testdir()
        # self.make_file("cachefile.txt")

        with open(self.get_real_path("cachefile.txt"), "wb") as cachefile:

            cachefile.write(b"a" * 100)
            self.originalfile = io.BytesIO(b"b" * 100)
            cachefile.seek(0, 0)
            self.originalfile.seek(0, 0)

            self.complete_data = b''.join([b"a" * 100, b"b" * 100])

    def tearDown(self):
        self.rm_testdir()

    def test_read_alldata(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = CachingReader(cachefile,
                                       self.originalfile,
                                       length=(
                                           self.cachefile_len + self.origfile_len),
                                       complete_cache=False,
                                       logger=logger_for_test)

        data = caching_reader.read(-1)

        self.assertEqual(data, self.complete_data)
        caching_reader.close()

        with open(self.get_real_path("cachefile.txt"), "r+b") as cachefile:
            self.assertEqual(self.complete_data, cachefile.read())

    def test_read_from_only_cachefile(self):

        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")

        caching_reader = CachingReader(cachefile,
                                       self.originalfile,
                                       length=200,
                                       complete_cache=False,
                                       logger=logger_for_test)

        data = caching_reader.read(90)

        self.assertEqual(len(data), 90)
        self.assertEqual(data, b"a" * 90)

        caching_reader.close()

    def test_read_from_both_cachefile_and_origfile(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = CachingReader(cachefile,
                                       self.originalfile,
                                       length=200,
                                       complete_cache=False,
                                       logger=logger_for_test)

        caching_reader.read(90)  # 捨てる

        data = caching_reader.read(20)

        self.assertEqual(len(data), 20)
        self.assertEqual(data, b"a" * 10 + b"b" * 10)

        caching_reader.close()

        with open(self.get_real_path("cachefile.txt"), "rb") as cachefile:
            self.assertEqual(cachefile.read(), b"a" * 100 + b"b" * 10)

    def test_complete_cache_true(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = CachingReader(cachefile,
                                       self.originalfile,
                                       length=(
                                           self.cachefile_len + self.origfile_len),
                                       complete_cache=True,  # <=ここをテストしたい
                                       logger=logger_for_test)
        caching_reader.close()
        with open(self.get_real_path("cachefile.txt"), "rb") as cachefile:
            self.assertEqual(self.complete_data, cachefile.read())

# def test():
#     if os.path.exists(root_test_dir_path):
#         shutil.rmtree(root_test_dir_path)
#     os.mkdir(root_test_dir_path)
#     unittest.main()
# if __name__ == "__main__":
#     test()
