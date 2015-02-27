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
from nicocache import NicoCachingReader, NicoCache

import logging as _logging
_logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

import nicocache

logger_for_test = _logging.getLogger("test")
# logger_for_test.addHandler(_logging.NullHandler())
logger_for_test.setLevel(_logging.ERROR)
# logger_for_test.setLevel(_logging.DEBUG)
verbosity = 1
root_test_dir_path = "./_testdir"


class util:

    @staticmethod
    def make_cachefile(path):
        with open(path, "w"):
            pass


class NicoCacheTestCase(unittest.TestCase):

    def make_testdir(self):
        self.rm_testdir()
        os.mkdir(os.path.join(root_test_dir_path, self.__class__.__name__))

    def makedir(self, dirname):
        os.makedirs(
            os.path.join(root_test_dir_path, self.__class__.__name__, dirname))

    def make_cachefile(self, filename):
        util.make_cachefile(
            os.path.join(root_test_dir_path, self.__class__.__name__, filename))

    def rm_testdir(self):
        shutil.rmtree(
            os.path.join(root_test_dir_path, self.__class__.__name__), ignore_errors=True)

    def get_real_path(self, path):
        return os.path.join(root_test_dir_path, self.__class__.__name__,  path)

    def get_testdir_path(self):
        return os.path.join(root_test_dir_path, self.__class__.__name__)


class Test_get_file_len(NicoCacheTestCase):

    def setUp(self):
        self.make_testdir()

    def tearDown(self):
        self.rm_testdir()

    def test(self):
        self.make_testdir()
        self.make_cachefile("test.txt")
        f = open(self.get_real_path("test.txt"), "w")
        f.write("a" * 10)
        f.close()

        with open(self.get_real_path("test.txt")) as f:
            f.seek(5)
            length = nicocache.get_file_len(f)
            self.assertEqual(length, 10, "ファイルの長さが正しく測れていない")
            self.assertEqual(f.tell(), 5, "ファイルポインタの位置が戻ってない")


class Test_get_pathlist(unittest.TestCase):

    def setUp(self):

        os.makedirs("./_testdir/Test_get_pathlist/subdir1")
        os.makedirs("./_testdir/Test_get_pathlist/subdir2")

        with open("./_testdir/Test_get_pathlist/file0", "w"),\
                open("./_testdir/Test_get_pathlist/subdir1/file1", "w"),\
                open("./_testdir/Test_get_pathlist/subdir1/file2", "w"),\
                open("./_testdir/Test_get_pathlist/subdir2/file3", "w"),\
                open("./_testdir/Test_get_pathlist/subdir2/file4", "w"):
            pass

    def tearDown(self):
        shutil.rmtree("./_testdir/Test_get_pathlist", ignore_errors=True)

    def test_non_recursive(self):

        pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_pathlist", recursive=False)

        self.assertEqual(len(pathlist), 1)

        dirpath, dirlist, filelist = pathlist[0]
        self.assertEqual(dirpath, "./_testdir/Test_get_pathlist")

        self.assertEqual(dirlist, ["subdir1", "subdir2"])
        self.assertEqual(filelist, ["file0"])

    def test_recursive(self):

        pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_pathlist", recursive=True)

        self.assertEqual(len(pathlist), 3)

        dirpath, dirlist, filelist = pathlist[0]
        self.assertEqual(dirpath, "./_testdir/Test_get_pathlist")
        self.assertEqual(dirlist, ["subdir1", "subdir2"])
        self.assertEqual(filelist, ["file0"])

        dirpath, dirlist, filelist = pathlist[1]
        self.assertEqual(dirpath, "./_testdir/Test_get_pathlist/subdir1")
        self.assertEqual(dirlist, [])
        self.assertEqual(filelist, ["file1", "file2"])

        dirpath, dirlist, filelist = pathlist[2]
        self.assertEqual(dirpath, "./_testdir/Test_get_pathlist/subdir2")
        self.assertEqual(dirlist, [])
        self.assertEqual(filelist, ["file3", "file4"])


class Test_make_video_cache_filename(unittest.TestCase):

    def test_notitle(self):
        filename = nicocache.make_video_cache_filename(
            "sm114514", "mp4", tmp=True, low=True)
        self.assertEqual(filename, "tmp_sm114514low.mp4")

    def test_title(self):
        filename = nicocache.make_video_cache_filename(
            "sm114514", "mp4", tmp=True, low=True, title="真夏の夜の夢.mp893")
        self.assertEqual(filename, "tmp_sm114514low_真夏の夜の夢.mp893.mp4")


class Test_get_video_cache_filepath(unittest.TestCase):

    def setUp(self):

        os.makedirs("./_testdir/Test_get_video_cache_filepath/subdir1")
        os.makedirs("./_testdir/Test_get_video_cache_filepath/subdir2")

    @staticmethod
    def make_cachefile(filename):
        util.make_cachefile(
            "./_testdir/Test_get_video_cache_filepath/" + filename)

    def tearDown(self):
        shutil.rmtree(
            "./_testdir/Test_get_video_cache_filepath", ignore_errors=True)

    def test_not_exist_file(self):
        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_video_cache_filepath", True)

        r = nicocache.get_video_cache_filepath("sm1", self.pathlist,
                                               tmp=False, low=False)
        self.assertIsNone(r)

    def test_exist_file__not_contains_title(self):
        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_video_cache_filepath", True)

        r = nicocache.get_video_cache_filepath("sm10", self.pathlist,
                                               tmp=False, low=False)
        self.assertEqual(
            r, "./_testdir/Test_get_video_cache_filepath/" + "sm10.mp4")

    def test_exist_file__contains_title(self):
        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_video_cache_filepath/", True)

        r = nicocache.get_video_cache_filepath(
            "sm11", self.pathlist, tmp=False, low=False)
        self.assertEqual(
            r, "./_testdir/Test_get_video_cache_filepath/" + "sm11_タイトル.mp4")

    def test_subdir_tmp_low(self):
        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.make_cachefile("subdir1/tmp_so20low_タイトル.mp4")
        self.pathlist = nicocache.get_pathlist(
            "./_testdir/Test_get_video_cache_filepath/", True)

        r = nicocache.get_video_cache_filepath(
            "so20", self.pathlist, tmp=True, low=True)
        self.assertEqual(
            r, "./_testdir/Test_get_video_cache_filepath/" + "subdir1/tmp_so20low_タイトル.mp4")


class Test_parse_video_cache_filename(unittest.TestCase):

    def test__title_tmp_low(self):
        r = nicocache.parse_video_cache_filename(
            "tmp_sm114514low_真夏の夜の夢.mp893.mp4")
        self.assertIsNotNone(r)

        (video_type, video_num, title,
         filename_extension, is_tmp, is_low) = r
        self.assertEqual(video_type, "sm", "video_type not correct")
        self.assertEqual(video_num, "114514", "video_num not correct")
        self.assertEqual(title, "真夏の夜の夢.mp893", "title not correct")
        self.assertEqual(
            filename_extension, "mp4", "filename_extension not correct")
        self.assertEqual(is_tmp, True, "is_tmp not correct")
        self.assertEqual(is_low, True, "is_tmp not correct")

    def test__notitle_tmp_low(self):
        r = nicocache.parse_video_cache_filename("tmp_sm114514low.mp4")
        self.assertIsNotNone(r)

        (video_type, video_num, title,
         filename_extension, is_tmp, is_low) = r
        self.assertEqual(video_type, "sm", "video_type not correct")
        self.assertEqual(video_num, "114514", "video_num not correct")
        self.assertEqual(title, "", "title not correct")
        self.assertEqual(
            filename_extension, "mp4", "filename_extension not correct")
        self.assertEqual(is_tmp, True, "is_tmp not correct")
        self.assertEqual(is_low, True, "is_tmp not correct")

    def test__title(self):
        r = nicocache.parse_video_cache_filename("sm114514_真夏の夜の夢.mp893.mp4")
        self.assertIsNotNone(r)

        (video_type, video_num, title,
         filename_extension, is_tmp, is_low) = r
        self.assertEqual(video_type, "sm", "video_type not correct")
        self.assertEqual(video_num, "114514", "video_num not correct")
        self.assertEqual(title, "真夏の夜の夢.mp893", "title not correct")
        self.assertEqual(
            filename_extension, "mp4", "filename_extension not correct")
        self.assertEqual(is_tmp, False, "is_tmp not correct")
        self.assertEqual(is_low, False, "is_tmp not correct")

    def test__notitle(self):
        r = nicocache.parse_video_cache_filename("sm114514.mp4")
        self.assertIsNotNone(r)

        (video_type, video_num, title,
         filename_extension, is_tmp, is_low) = r
        self.assertEqual(video_type, "sm", "video_type not correct")
        self.assertEqual(video_num, "114514", "video_num not correct")
        self.assertEqual(title, "", "title not correct")
        self.assertEqual(
            filename_extension, "mp4", "filename_extension not correct")
        self.assertEqual(is_tmp, False, "is_tmp not correct")
        self.assertEqual(is_low, False, "is_tmp not correct")


class TestCachingReader(NicoCacheTestCase):

    def setUp(self):
        self.cachefile_len = 100
        self.origfile_len = 100

        self.make_testdir()
        # self.make_cachefile("cachefile.txt")

        with open(self.get_real_path("cachefile.txt"), "wb") as cachefile:

            cachefile.write("a" * 100)
            self.originalfile = StringIO.StringIO("b" * 100)
            cachefile.seek(0, 0)
            self.originalfile.seek(0, 0)

            self.complete_data = ''.join(["a" * 100, "b" * 100])

    def tearDown(self):
        self.rm_testdir()

    def test_read_alldata(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = nicocache.\
            CachingReader(cachefile,
                          self.originalfile,
                          length=(self.cachefile_len + self.origfile_len),
                          complete_cache=False,
                          logger=logger_for_test)

        data = caching_reader.read(-1)

        self.assertEqual(data, self.complete_data)
        caching_reader.close()

        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        self.assertEqual(self.complete_data, cachefile.read())

    def test_read_from_only_cachefile(self):

        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")

        caching_reader = nicocache.\
            CachingReader(cachefile,
                          self.originalfile,
                          length=200,
                          complete_cache=False,
                          logger=logger_for_test)

        data = caching_reader.read(90)

        self.assertEqual(len(data), 90)
        self.assertEqual(data, "a" * 90)

        caching_reader.close()

    def test_read_from_both_cachefile_and_origfile(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = nicocache.\
            CachingReader(cachefile,
                          self.originalfile,
                          length=200,
                          complete_cache=False,
                          logger=logger_for_test)

        caching_reader.read(90)  # 捨てる

        data = caching_reader.read(20)

        self.assertEqual(len(data), 20)
        self.assertEqual(data, "a" * 10 + "b" * 10)

        caching_reader.close()

        with open(self.get_real_path("cachefile.txt")) as cachefile:
            self.assertEqual(cachefile.read(), "a" * 100 + "b" * 10)

    def test_complete_cache_true(self):
        cachefile = open(self.get_real_path("cachefile.txt"), "r+b")
        caching_reader = nicocache.\
            CachingReader(cachefile,
                          self.originalfile,
                          length=(self.cachefile_len + self.origfile_len),
                          complete_cache=True,  # <=ここをテストしたい
                          logger=logger_for_test)
        caching_reader.close()
        with open(self.get_real_path("cachefile.txt")) as cachefile:
            self.assertEqual(self.complete_data, cachefile.read())


class TestCacheFilePathListTable(unittest.TestCase):

    def setUp(self):
        self.cachepathtable = nicocache.CacheFilePathListTable(
            "./_testdir", recursive=True)

    def test__add_cachefilename(self):
        self.cachepathtable.insert(
            "sm36", "mp4", tmp=True, low=True, title="普通だな")
        fpath = self.cachepathtable.get_video_cache_filepath(
            "sm36", tmp=True, low=True)

        self.assertIsNotNone(fpath)
        fname = os.path.basename(fpath)
        self.assertEqual(fname, "tmp_sm36low_普通だな.mp4", fname)


class TestNicoCacheFileSystem(NicoCacheTestCase):

    def setUp(self):
        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.make_cachefile("subdir1/tmp_so20low_タイトル.mp4")

        self.nicocache_filesystem = nicocache.NicoCacheFileSystem(
            cachedirpath=self.get_testdir_path(),
            recursive=True)

    def tearDown(self):
        self.rm_testdir()

    def test__get_video_cache_filepath__topdir(self):
        filepath = self.nicocache_filesystem.\
            get_video_cache_filepath("sm10")

        self.assertEqual(os.path.basename(filepath), "sm10.mp4")

    def test__create_new_file(self):
        self.nicocache_filesystem.create_new_file(
            "sm36", "mp4", tmp=True, low=True, title="普通だな")
        filepath = self.nicocache_filesystem.\
            get_video_cache_filepath("sm36", tmp=True, low=True)

        self.assertEqual(os.path.basename(filepath), "tmp_sm36low_普通だな.mp4")

        self.assertTrue(os.path.exists(filepath))

    def test__rename(self):
        oldfilepath = self.nicocache_filesystem.\
            get_video_cache_filepath("sm10")

        self.nicocache_filesystem.rename("sm10", tmp=False, low=False,
                                         new_tmp=True, new_low=True, new_title="新しいタイトル")
        filepath = self.nicocache_filesystem.\
            get_video_cache_filepath("sm10", tmp=True, low=True)

        self.assertEqual(
            os.path.basename(filepath), "tmp_sm10low_新しいタイトル.mp4")

        self.assertTrue(os.path.exists(filepath))

        self.assertFalse(os.path.exists(oldfilepath))

    def test__create_new_file__already_exist_error(self):
        self.nicocache_filesystem.create_new_file(
            "sm36", "mp4", tmp=True, low=True, title="普通だな")

        with self.assertRaises(nicocache.NicoCacheFileSystem.AlreadyExistsError):
            self.nicocache_filesystem.create_new_file(
                "sm36", "mp4", tmp=True, low=True, title="普通だな")

    def test_search_cache_file(self):
        self.make_cachefile("subdir2/tmp_sm98765_うんこ.mp4")
        nicocache_filesystem = self.nicocache_filesystem
        self.assertIsNone(nicocache_filesystem.get_video_cache_filepath(
            "sm98765", tmp=True, low=False))
        self.assertTrue(
            nicocache_filesystem.search_cache_file(video_id="sm98765",
                                                   filename_extension="mp4",
                                                   tmp=True, low=False,
                                                   title="うんこ"))
        nicocache_filesystem.get_video_cache_filepath(
            "sm98765", tmp=True, low=False)
        self.assertIsNotNone(
            nicocache_filesystem.get_video_cache_filepath("sm98765", tmp=True, low=False))


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


class TestNicoCachingReader_staticmethod(NicoCacheTestCase):

    def setUp(self):

        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_cachefile("sm10.mp4")
        self.make_cachefile("sm11_タイトル.mp4")
        self.make_cachefile("sm12_タイトル.mp4")
        self.make_cachefile("subdir1/tmp_so20low_タイトル.mp4")

        with open(self.get_real_path("sm8_ニコキャッシュpyテストsm8.mp4"), "wb") as f:
            f.write("a" * 100 + "b" * 200)

        nicocache_filesystem = nicocache.NicoCacheFileSystem(
            self.get_testdir_path(), recursive=True)
        self.video_cache_getter = nicocache.VideoCacheGetter(
            nicocache_filesystem)

        self._original_create_sockfile = proxtheta.utility.client.create_sockfile
        proxtheta.utility.client.create_sockfile = create_sockfile

        self._original_getthumbinfo = nicocache.getthumbinfo
        nicocache.getthumbinfo = getthumbinfo__mock

    def tearDown(self):
        proxtheta.utility.client.create_sockfile = self._original_create_sockfile
        nicocache.getthumbinfo = self._original_getthumbinfo

        shutil.rmtree(
            os.path.join(root_test_dir_path, self.__class__.__name__), ignore_errors=True)

    def test__create_response_with_complete_localcache(self):
        proxtheta.utility.client.create_sockfile = None  # local only

        video_id = "sm8"
        video_cache = self.video_cache_getter.get(video_id, low=False)
        #thumbinfo = nicocache.ThumbInfo(video_id)

        self.assertTrue(video_cache.is_complete())

        respack = nicocache.NicoCachingReader.\
            create_response_with_complete_localcache(video_cache)

        data = respack.body_file.read(110)
        self.assertEqual(data, "a" * 100 + "b" * 10)

        self.assertTrue(
            os.path.exists(self.get_real_path("sm8_ニコキャッシュpyテストsm8.mp4")))

        respack.close_body_file()

        respack.close()

    def test__create_response_with_tmp_localcache_and_server(self):
        proxtheta.utility.client.create_sockfile = create_sockfile_force_economy
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=9.0low", ""), "HTTP/1.1"))
        req.headers["Host"] = host

        video_id = "sm9"

        video_cache = self.video_cache_getter.get(video_id, low=True)
        video_cache.set_title("ニコキャッシュpyテストsm9")
        video_cache.set_filename_extension("mp4")
        respack = nicocache.get_partial_http_resource(("smile-cln57.nicovideo.jp", 80),
                                                      req,
                                                      first_byte_pos=0,
                                                      server_sockfile=None,
                                                      nonproxy_camouflage=False)

        nicocache.NicoCachingReader.\
            create_response_with_tmp_localcache_and_server(video_cache,
                                                           respack,
                                                           complete_video_size=100,
                                                           complete_cache=False)

        data = respack.body_file.read(60)
        self.assertEqual(data, "a" * 50 + "b" * 10)

        self.assertTrue(
            os.path.exists(self.get_real_path("tmp_sm9low_ニコキャッシュpyテストsm9.mp4")))

        respack.close_body_file()

        with open(self.get_real_path("tmp_sm9low_ニコキャッシュpyテストsm9.mp4")) as f:
            self.assertEqual(f.read(), "a" * 50 + "b" * 10)
        respack.server_sockfile.close()


class TestVideoCache_cachefile_already_exsists_in_filesystem_case(NicoCacheTestCase):

    """!!!ザルすぎるので誰かちゃんとしたの作って"""

    def setUp(self):
        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_cachefile("tmp_sm56789_アカサタナ.avi.mp4")
        self.make_cachefile("subdir2/tmp_sm12345_あいうえお.avi.mp4")

        nicocachefs = nicocache.NicoCacheFileSystem(
            self.get_testdir_path(), recursive=True)
        self.video_cache_getter = nicocache.VideoCacheGetter(nicocachefs)

    def tearDown(self):
        self.rm_testdir()

    def test_already_exsists_in_subdir_case(self):

        # ファイルシステムを監視はしないので、ここでファイルを作っても上手くいかない
        # self.make_cachefile("subdir2/tmp_sm12345_あいうえお.avi.mp4")

        video_cache = self.video_cache_getter.get("sm12345", low=False)

        self.assertTrue(video_cache.exsists_in_filesystem())
        self.assertEqual(video_cache.get_title(), "あいうえお.avi")

        with self.assertRaises(NotImplementedError):
            video_cache.set_title("いろはにほへと")

    def test_already_exsists_in_rootdir_case(self):

        video_cache = self.video_cache_getter.get("sm56789", low=False)

        self.assertTrue(video_cache.exsists_in_filesystem())
        self.assertEqual(video_cache.get_title(), "アカサタナ.avi")

        video_cache.set_title("いろはにほへと")
        self.assertEqual(video_cache.get_title(), "いろはにほへと")

        video_cache.change_to_complete_cache()

        self.assertTrue(
            os.path.exists(self.get_real_path("sm56789_いろはにほへと.mp4")))


class TestVideoCache_cachefile_not_already_exsists_in_filesystem_case(NicoCacheTestCase):

    """!!!ザルすぎるので誰かちゃんとしたの作って"""

    def setUp(self):
        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        # self.make_cachefile("tmp_sm56789_アカサタナ.avi.mp4")
        # self.make_cachefile("subdir2/tmp_sm12345_あいうえお.avi.mp4")

        nicocachefs = nicocache.NicoCacheFileSystem(
            self.get_testdir_path(), recursive=True)
        self.video_cache_getter = nicocache.VideoCacheGetter(nicocachefs)

    def tearDown(self):
        self.rm_testdir()

    def test_create_new_cachefile_in_rootdir_case(self):

        video_cache = self.video_cache_getter.get("sm56789", low=False)

        self.assertTrue(video_cache.is_tmp())

        self.assertFalse(video_cache.exsists_in_filesystem())
        self.assertEqual(video_cache.get_title(), "")

        video_cache.set_title("いろはにほへと")
        self.assertEqual(video_cache.get_title(), "いろはにほへと")

        if not video_cache.exsists_in_filesystem():
            video_cache.set_filename_extension("mp4")
        else:
            raise RuntimeError("must not come here!")

        with video_cache.get_cachefile():
            pass
        self.assertTrue(
            os.path.exists(self.get_real_path("tmp_sm56789_いろはにほへと.mp4")))

        self.assertTrue(video_cache.exsists_in_filesystem())

        video_cache.change_to_complete_cache()

        self.assertTrue(
            os.path.exists(self.get_real_path("sm56789_いろはにほへと.mp4")))


class TestNicoCachingReader(NicoCacheTestCase):

    def setUp(self):
        self.cachefile_len = 100
        self.origfile_len = 100

        self.make_testdir()
        # self.make_cachefile("cachefile.txt")

        with open(self.get_real_path("tmp_sm12345_テスト.mp4"), "wb") as cachefile:
            cachefile.write("a" * 100)

        self.originalfile = StringIO.StringIO("b" * 100)
        self.originalfile.seek(0, 0)

        self.complete_data = ''.join(["a" * 100, "b" * 100])

        nicocache_filesystem = nicocache.NicoCacheFileSystem(
            self.get_testdir_path(), recursive=True)
        self.video_cache = nicocache.VideoCache(
            nicocache_filesystem, "sm12345", low=False)

    def tearDown(self):
        self.rm_testdir()

    def test_read_from_only_cachefile(self):
        caching_reader = nicocache.\
            NicoCachingReader(self.video_cache,
                              self.originalfile,
                              length=200,
                              complete_cache=False,
                              logger=logger_for_test)

        data = caching_reader.read(90)

        self.assertEqual(len(data), 90)
        self.assertEqual(data, "a" * 90)

        caching_reader.close()

    def test_complete_cache_true(self):

        caching_reader = nicocache.\
            NicoCachingReader(self.video_cache,
                              self.originalfile,
                              length=(self.cachefile_len + self.origfile_len),
                              complete_cache=True,
                              logger=logger_for_test)
        caching_reader.close()
        with open(self.get_real_path("sm12345_テスト.mp4")) as cachefile:
            self.assertEqual(self.complete_data, cachefile.read())


class TestNicoCache_handle_video_request(NicoCacheTestCase):

    def setUp(self):
        self.make_testdir()

        with open(self.get_real_path("sm8_ニコキャッシュpyテストsm8.mp4"), "wb") as f:
            f.write("a" * 100 + "b" * 200)

        nicocache_filesystem = nicocache.NicoCacheFileSystem(
            self.get_testdir_path(), recursive=True)

        self.video_cache_getter = nicocache.VideoCacheGetter(
            nicocache_filesystem)

        self._original_create_sockfile = proxtheta.utility.client.create_sockfile
        proxtheta.utility.client.create_sockfile = create_sockfile

        self._original_getthumbinfo = nicocache.getthumbinfo
        nicocache.getthumbinfo = getthumbinfo__mock

        self.nicocache = nicocache.NicoCache(
            video_cache_getter=self.video_cache_getter)

    def tearDown(self):
        self.rm_testdir()

    def test(self):
        host = "smile-com42.nicovideo.jp"
        req = httpmes.HTTPRequest(
            ("GET", ("http", host, None, "/smile", "v=9.0", ""), "HTTP/1.1"))
        req.headers["Host"] = host
        respack = self.nicocache.handle_video_request(
            req, server_sockfile=None, info=None)

        data = respack.body_file.read(110)

        self.assertEqual(data, "a" * 100 + "b" * 10)

        respack.close()


if __name__ == '__main__':
    unittest.main(verbosity=verbosity)
