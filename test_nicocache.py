# -*- coding: utf-8 -
import unittest


import os
import StringIO
import shutil
from proxtheta import utility
from proxtheta.core import httpmes
import proxtheta.core.common
import proxtheta
from proxtheta.core import iowrapper
import proxtheta.utility
from nicocache import NicoCache

import logging as _logging
import libnicocache
from libnicocache import test_libnicocache
_logging.basicConfig(
    format="%(levelname)s:%(name)s: %(message)s")

import nicocache

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


NicoCacheTestCase = test_libnicocache.NicoCacheTestCase


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

    def __init__(self, (host, port), close=True, force_economy=False):
        self._before_read = True

        self.address = proxtheta.core.common.Address((host, port))
        self._force_economy = force_economy

        self._host = host

        self._file_from_client = StringIO.StringIO()
        self._file_to_client = StringIO.StringIO()
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
            content = "a" * 50 + "b" * 50
        else:
            content = "a" * 100 + "b" * 100

        try:
            if self._force_economy and not req.query.endswith("low"):
                res = httpmes.HTTPResponse(
                    ("HTTP/1.1", 403, "Forbidden"))
                content = "Forbidden"
                return

            if "Range" in req.headers:
                res = httpmes.HTTPResponse(
                    ("HTTP/1.1", 206, "Partial Content"))

                first_pos = int(req.headers["Range"][6:][:-1])
                # Range: bytes=12-

                httpmes.set_body(res, content[first_pos:])

                res.headers["Content-Range"] = ("bytes %d-%d/%d" %
                                                (first_pos,
                                                 len(content) - 1,
                                                 len(content)))
                res.headers["Content-Type"] = "video/mp4"

            else:
                first_pos = 0
                res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))

                httpmes.set_body(res, content)
        finally:
            self._file_to_client.write(str(res))

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


def create_sockfile((host, port)):
    """モックを返す"""
    return SocketWrapperMock((host, port))


def create_sockfile_force_economy((host, port), force_economy=True):
    """モックを返す"""
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
        server_sockfile.write(str(req))

        res = httpmes.HTTPResponse.create(server_sockfile, load_body=1)
        server_sockfile.close()

        self.assertEqual(res.body, "a" * 100 + "b" * 100)


class TestVideoCacheOperator(NicoCacheTestCase):

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

        video_cache_manager = nicocache.VideoCacheManager(
            libnicocache.pathutil.FileSystemWrapper, libnicocache.VideoCache)

        self.video_cache_operator = nicocache.VideoCacheOperator(
            video_cache_manager, rootdir=self.testdir_path, logger=logger_for_test)

    def test__save_cache(self):
        info_list = self.video_cache_operator.save_cache(
            video_num="9", subdir="save", title="てすと", filename_extension="mp4",
            video_id="so9")


class TestVideoCacheOperator_caching(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_file("tmp_sm10low_てすと.mp4")
        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        with open(self.get_real_path("sm8_ニコキャッシュpyテストsm8.mp4"), "wb") as f:
            f.write("a" * 100 + "b" * 200)

        with open(self.get_real_path("tmp_sm10_ニコキャッシュpyテストsm10.mp4"), "wb") as f:
            f.write("a" * 100)

        video_cache_manager = nicocache.VideoCacheManager(
            libnicocache.pathutil.FileSystemWrapper, libnicocache.VideoCache)

        self._original_create_sockfile = proxtheta.utility.client.create_sockfile
        proxtheta.utility.client.create_sockfile = create_sockfile

        self.video_cache_operator = nicocache.VideoCacheOperator(
            video_cache_manager, rootdir=self.testdir_path, logger=logger_for_test)

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

        respack = self.video_cache_operator.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read()

        self.assertEqual(data, "a" * 100 + "b" * 200)

    def test_create_response_with_new_localcache(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=9.0low", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_operator.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read(60)

        self.assertEqual(data, "a" * 50 + "b" * 10)

        respack.close()

    def test_create_response_with_tmp_localcache(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=10.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        def http_resource_getter_func(req, server_sockfile):
            return proxtheta.utility.client.get_http_resource(
                (host, 80), req, server_sockfile)

        respack = self.video_cache_operator.make_http_video_resource(
            req, http_resource_getter_func, None)

        data = respack.body_file.read()

        self.assertEqual(data, "a" * 100 + "b" * 100)

        respack.close()


if __name__ == '__main__':
    unittest.main(verbosity=verbosity)
