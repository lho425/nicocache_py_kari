# -*- coding: utf-8 -
import unittest


import os
import io
import shutil
from proxtheta import utility
from proxtheta.core import httpmes
import proxtheta.core.common
import proxtheta
from proxtheta.core import iowrapper
import proxtheta.utility
from .. import pathutil, VideoCacheFileManager
from .. import _parse_range_str

from . import test_base
from .. import base
from ..base import VideoCacheFile

import logging as _logging
from .. import VideoCacheManager, VideoCache
from ..base import VideoCacheInfo
_logging.basicConfig(
    format="%(levelname)s:%(name)s: %(message)s")


logger_for_test = _logging.getLogger("test")
# logger_for_test.addHandler(_logging.NullHandler())
logger_for_test.setLevel(_logging.ERROR)
# logger_for_test.setLevel(_logging.INFO)
# logger_for_test.setLevel(_logging.DEBUG)
verbosity = 1
root_test_dir_path = "./_testdir"


class util:

    @staticmethod
    def make_file(path):
        with open(path, "w"):
            pass


NicoCacheTestCase = test_base.NicoCacheTestCase


# class Test_get_pathlist(unittest.TestCase):
#
#     def setUp(self):
#
#         os.makedirs("./_testdir/Test_get_pathlist/subdir1")
#         os.makedirs("./_testdir/Test_get_pathlist/subdir2")
#
#         with open("./_testdir/Test_get_pathlist/file0", "w"),\
#                 open("./_testdir/Test_get_pathlist/subdir1/file1", "w"),\
#                 open("./_testdir/Test_get_pathlist/subdir1/file2", "w"),\
#                 open("./_testdir/Test_get_pathlist/subdir2/file3", "w"),\
#                 open("./_testdir/Test_get_pathlist/subdir2/file4", "w"):
#             pass
#
#     def tearDown(self):
#         shutil.rmtree("./_testdir/Test_get_pathlist", ignore_errors=True)
#
#     def test_non_recursive(self):
#
#         pathlist = nicocache.get_pathlist(
#             "./_testdir/Test_get_pathlist", recursive=False)
#
#         self.assertEqual(len(pathlist), 1)
#
#         dirpath, dirlist, filelist = pathlist[0]
#         self.assertEqual(dirpath, "./_testdir/Test_get_pathlist")
#
#         self.assertEqual(dirlist, ["subdir1", "subdir2"])
#         self.assertEqual(filelist, ["file0"])
#
#     def test_recursive(self):
#
#         pathlist = nicocache.get_pathlist(
#             "./_testdir/Test_get_pathlist", recursive=True)
#
#         self.assertEqual(len(pathlist), 3)
#
#         dirpath, dirlist, filelist = pathlist[0]
#         self.assertEqual(dirpath, "./_testdir/Test_get_pathlist")
#         self.assertEqual(dirlist, ["subdir1", "subdir2"])
#         self.assertEqual(filelist, ["file0"])
#
#         dirpath, dirlist, filelist = pathlist[1]
#         self.assertEqual(dirpath, "./_testdir/Test_get_pathlist/subdir1")
#         self.assertEqual(dirlist, [])
#         self.assertEqual(filelist, ["file1", "file2"])
#
#         dirpath, dirlist, filelist = pathlist[2]
#         self.assertEqual(dirpath, "./_testdir/Test_get_pathlist/subdir2")
#         self.assertEqual(dirlist, [])
#         self.assertEqual(filelist, ["file3", "file4"])


# class TestCacheFilePathListTable(unittest.TestCase):
#
#     def setUp(self):
#         self.cachepathtable = nicocache.CacheFilePathListTable(
#             "./_testdir", recursive=True)
#
#     def test__add_cachefilename(self):
#         self.cachepathtable.insert(
#             "sm36", "mp4", tmp=True, low=True, title="普通だな")
#         fpath = self.cachepathtable.get_video_cache_filepath(
#             "sm36", tmp=True, low=True)
#
#         self.assertIsNotNone(fpath)
#         fname = os.path.basename(fpath)
#         self.assertEqual(fname, "tmp_sm36low_普通だな.mp4", fname)


class SocketWrapperMock(iowrapper.FileWrapper):

    def __init__(self, xxx_todo_changeme, close=True, force_economy=False):
        (host, port) = xxx_todo_changeme
        self._before_read = True

        self.address = proxtheta.core.common.Address((host, port))
        self._force_economy = force_economy

        self._host = host

        self._file_from_client = io.BytesIO()
        self._file_to_client = io.BytesIO()
        iowrapper.FileWrapper.__init__(self, self._file_to_client, close=close)

    def write(self, data):
        return self._file_from_client.write(data)

    def _before_read_hook(self):
        self._file_from_client.seek(0, 0)
        req = httpmes.HTTPRequest.create(self._file_from_client, load_body=1)
        if req is None:
            self._file_from_client.seek(0, 0)
            raise RuntimeError(
                "HTTP1.1 request is EOF!" + self._file_from_client.read())

        if not "Host" in req.headers:
            raise RuntimeError("invalid HTTP1.1 request " + str(req))

        if not (self._host.startswith("smile-") and self._host.endswith(".nicovideo.jp")):
            raise RuntimeError("BAD request" + str(req))

        if req.query.endswith("low"):
            content = b"a" * 50 + b"b" * 50
        else:
            content = b"a" * 100 + b"b" * 100

        try:
            if self._force_economy and not req.query.endswith("low"):
                res = httpmes.HTTPResponse(
                    ("HTTP/1.1", 403, "Forbidden"))
                content = "Forbidden"
                return

            if "Range" in req.headers:
                res = httpmes.HTTPResponse(
                    ("HTTP/1.1", 206, "Partial Content"))
                first_pos, last_pos = _parse_range_str(req.headers["Range"])[0]
                end_pos = last_pos + 1 if last_pos is not None else None
                content_ = content[first_pos:end_pos]
                httpmes.set_body(res, content_)

                res.headers["Content-Range"] = ("bytes %d-%d/%d" %
                                                (first_pos,
                                                 # last can be None
                                                 first_pos + len(content_) - 1,
                                                 len(content)))
                res.headers["Content-Type"] = "video/mp4"

            else:
                first_pos = 0
                res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))

                httpmes.set_body(res, content)
        finally:
            self._file_to_client.write(bytes(res))

            self._file_to_client.seek(0, 0)

    def read(self, size=-1):
        if self._before_read:
            self._before_read_hook()
            self._before_read = False
        return iowrapper.FileWrapper.read(self, size=size)

    def readline(self, size=-1):
        if self._before_read:
            self._before_read_hook()
            self._before_read = False
        return iowrapper.FileWrapper.readline(self, size=size)


def create_sockfile(xxx_todo_changeme1, ssl=None):
    """モックを返す"""
    (host, port) = xxx_todo_changeme1
    return SocketWrapperMock((host, port))


def create_sockfile_force_economy(xxx_todo_changeme2, force_economy=True):
    """モックを返す"""
    (host, port) = xxx_todo_changeme2
    return SocketWrapperMock((host, port), force_economy=True)


def getthumbinfo__mock(video_id):
    xmltext = """\
<?xml version="1.0" encoding="UTF-8"?>
<nicovideo_thumb_response status="ok">
  <thumb>
    <video_id>%s</video_id>
    <title>ニコキャッシュpyテスト%s</title>
    <movie_type>mp4</movie_type>
    <size_high>200</size_high>
    <size_low>100</size_low>
  </thumb>
</nicovideo_thumb_response>
""" % (video_id, video_id)

    return xmltext


class TestSocketWrapperMock(unittest.TestCase):

    def test(self):

        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=0.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host
        server_sockfile = create_sockfile((host, 80))
        server_sockfile.write(bytes(req))

        res = httpmes.HTTPResponse.create(server_sockfile, load_body=1)
        server_sockfile.close()

        self.assertEqual(res.body, b"a" * 100 + b"b" * 100)


class TestVideoCacheFileManager(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.makedir("save")

        self.make_file("tmp_sm9low")
        self.make_file("tmp_sm10low_てすと.mp4")
        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        self.video_cache_file_manager = VideoCacheFileManager(
            pathutil.FileSystemWrapper, base.VideoCacheFile)

    def test(self):
        video_cache1 = self.video_cache_file_manager.get(
            VideoCacheInfo.create(rootdir=self.testdir_path, video_num="9"))

        video_cache2 = self.video_cache_file_manager.get(
            VideoCacheInfo.create(rootdir=self.testdir_path, video_num="9"))

        self.assertTrue(video_cache1 is video_cache2)


# class TestVideoCacheOperator(NicoCacheTestCase):
#
#     def setUp(self):
#         self.rm_testdir()
#
#         self.make_testdir()
#         self.makedir("subdir1")
#         self.makedir("subdir2")
#
#         self.makedir("save")
#
#         self.make_file("tmp_sm9low")
#         self.make_file("tmp_sm10low_てすと.mp4")
#         self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")
#
#         self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")
#
#         video_cache_file_manager = VideoCacheFileManager(
#             pathutil.FileSystemWrapper, VideoCacheFile)
#
#         self.video_cache_manager = VideoCacheOperator(
#             video_cache_file_manager, rootdir=self.testdir_path, logger=logger_for_test)
#
#     def test__save_cache(self):
#         info_list = self.video_cache_manager.save_cache(
#             video_num="9", subdir="save", title="てすと", filename_extension="mp4",
#             video_id="so9")
#         video_cache_info = self.video_cache_manager.get_video_cache_info(
#             video_num="9", low=True)
#
#         self.assertEqual(video_cache_info.subdir, "save")


class TestVideoCacheManager_make_http_video_resource(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        with open(self.get_real_path("subdir1/sm8_ニコキャッシュpyテストsm8.mp4"), "wb") as f:
            f.write(b"a" * 100 + b"b" * 200)

        with open(self.get_real_path("subdir1/tmp_sm10_ニコキャッシュpyテストsm10.mp4"), "wb") as f:
            f.write(b"a" * 100)
        filesystem_wrapper = pathutil.FileSystemWrapper()
        video_cache_file_manager = VideoCacheFileManager(
            filesystem_wrapper, VideoCacheFile)

        self._original_create_sockfile = proxtheta.utility.client.create_sockfile
        proxtheta.utility.client.create_sockfile = create_sockfile

        self.video_cache_manager = VideoCacheManager(
            self.testdir_path, VideoCache, logger_for_test)

#         self._original_getthumbinfo = nicocache.getthumbinfo
#         nicocache.getthumbinfo = getthumbinfo__mock

    def tearDown(self):
        proxtheta.utility.client.create_sockfile = self._original_create_sockfile

    def test_create_response_with_complete_localcache(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=8.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        def http_resource_getter_func(req, server_sockfile):
            raise RuntimeError("never call this func")
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read()

        self.assertEqual(data, b"a" * 100 + b"b" * 200)

        respack.close()

    def test_create_response_with_complete_localcache_with_range(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=8.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host
        req.headers["Range"] = "bytes=90-109"

        def http_resource_getter_func(req, server_sockfile):
            raise RuntimeError("never call this func")
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        self.assertEqual(respack.res.status_code, 206)
        self.assertEqual(
            respack.res.headers.get("Content-Range"), "bytes 90-109/300")

        data = respack.body_file.read()

        self.assertEqual(data, b"a" * 10 + b"b" * 10)

        respack.close()

    def test_create_response_with_new_localcache(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=9.0low", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read(60)

        self.assertEqual(data, b"a" * 50 + b"b" * 10)

        respack.close()

    def test_create_response_with_tmp_localcache(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=10.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read()

        self.assertEqual(data, b"a" * 100 + b"b" * 100)
        self.assertEqual(respack.res.status_code, 200)
        self.assertIsNone(respack.res.headers.get("Content-Range", None))
        respack.close()

    def test_create_response_with_tmp_localcache_with_range(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=10.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host
        req.headers["Range"] = "bytes=90-109"

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        self.assertEqual(respack.res.status_code, 206)
        self.assertEqual(
            respack.res.headers.get("Content-Range"), "bytes 90-109/200")

        data = respack.body_file.read()

        self.assertEqual(data, b"a" * 10 + b"b" * 10)
        respack.close()

    def test_create_response_with_tmp_localcache_with_outofcache_range(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=10.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        # cached size is 100
        # this range must be directly download from server
        req.headers["Range"] = "bytes=110-119"

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_manager.make_http_video_resource(
            req, http_resource_getter_func, None)

        self.assertEqual(respack.res.status_code, 206)
        self.assertEqual(
            respack.res.headers.get("Content-Range"), "bytes 110-119/200")

        data = respack.body_file.read()

        self.assertEqual(data, b"b" * 10)
        respack.close()


class TestVideoCacheManager(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        with open(self.get_real_path("subdir1/sm8_ニコキャッシュpyテストsm8.mp4"), "wb") as f:
            f.write(b"a" * 100 + b"b" * 200)

        with open(self.get_real_path("subdir1/tmp_sm10_ニコキャッシュpyテストsm10.mp4"), "wb") as f:
            f.write(b"a" * 100)
        filesystem_wrapper = pathutil.FileSystemWrapper()
        video_cache_file_manager = VideoCacheFileManager(
            filesystem_wrapper, VideoCacheFile)

        self.video_cache_manager = VideoCacheManager(
            self.testdir_path, VideoCache, logger_for_test)

    def test__get_video_cache_list(self):
        video_cache_info = VideoCacheInfo.make_query(
            video_id="so20", rootdir=self.get_testdir_path())
        video_cache_list = self.video_cache_manager.get_video_cache_list(
            video_cache_info)

        # ある(video_num, low)に対するキャッシュファイルは1つしかないないように振る舞うので
        # 個数は1となる
        self.assertEqual(len(video_cache_list), 1)

        for video_cache in video_cache_list:
            self.assertEqual(video_cache.info.video_id, "so20")


if __name__ == '__main__':
    unittest.main(verbosity=verbosity)
