# -*- coding: utf-8 -
import unittest

from collections import namedtuple
import os
import re
import shutil

from . import pathutil


root_cache_dir = "cache"


def _if_not_None_else(newvalue, basevalue):
    return newvalue if newvalue is not None else basevalue

_VideoCacheInfo = namedtuple("VideoCacheInfo",
                             ["video_id",
                              "tmp",
                              "low",
                              "filename_extension",
                              "title",
                              "subdir",
                              "rootdir"])


class VideoCacheInfo(_VideoCacheInfo):
    # キャッシュのファイル名=メタデータに関するアルゴリズムはすべてこのクラスにまとめてあるので、
    # VideoCacheInfo=MyVideoCacheInfoな感じで一回モンキーパッチを当てれば置き換えられる

    pattern = re.compile("(tmp_)?(\w\w[0-9]+)(low)?(_.*)?")

    def __new__(cls, video_id=None, tmp=None, low=None,
                filename_extension=None, title=None, subdir=None, rootdir=None):
        # ここのapiはまだ安定してない
        return _VideoCacheInfo.__new__(cls, video_id, tmp, low, filename_extension, title, subdir, rootdir)

    @classmethod
    def make_query(cls, rootdir, video_id=None, tmp=None, low=None,
                   filename_extension=None, title=None, subdir=None):
        return cls(video_id, tmp, low, filename_extension, title, subdir, rootdir)

    def replace(self, **kwargs):
        return self._replace(**kwargs)

    @classmethod
    def create_from_filename(cls, filename, rootdir, subdir=""):
        tmp = False
        low = False
        title = ""

        # 拡張子を分離
        filename, filename_extension = os.path.splitext(filename)
        filename_extension = filename_extension[1:]  # 拡張子に.が含まれてしまうため
        m = cls.pattern.match(filename)
        if not m:
            raise RuntimeError("VideoCacheInfo parse error")

        if m.group(1):
            tmp = True

        video_id = m.group(2)

        if m.group(3):
            low = True

        if m.group(4):
            title = m.group(4)[1:]  # _(アンダーバー)もタイトルにマッチしてしまうので[1:]とする

        return cls(video_id, tmp, low, filename_extension, title, subdir=subdir, rootdir=rootdir)

    @classmethod
    def create_from_relpath(cls, relpath, rootdir):
        """relpathはrootdirを基点にした相対パス
        relpathはsubdir1/subdir2/tmp_sm12345low_title.mp4 という形式"""

        # subdir を分離
        subdir = os.path.dirname(relpath)

        filename = os.path.basename(relpath)

        return cls.create_from_filename(filename, rootdir, subdir)

    def make_cache_file_path(self):
        dirpath = os.path.join(
            self.rootdir, self.subdir)

        tmpstr = ""
        lowstr = ""
        title_str = ""
        filename_extension_str = ""

        if self.tmp:
            tmpstr = "tmp_"

        if self.low:
            lowstr = "low"

        if self.title:
            title_str = "_" + self.title

        if self.filename_extension:
            filename_extension_str = "." + self.filename_extension

        # tmp_sm12345low_title.mp4"
        filename = ''.join(
            (tmpstr, self.video_id, lowstr, title_str, filename_extension_str))

        return os.path.join(dirpath, filename)

    def match(self, video_cache_info):
        """selfとvideo_cache_infoの持つパラメタを比較し、すべて一致していたらTureを返す.
        ただし、selfのパラメタの値がNoneだった場合、そのパラメタの比較はスキップされる.
        つまり、selfのパラメタの値がすべてNoneｓだった場合、任意のvideo_cache_infoにマッチする.
        if VideoCacheInfo.make_query(...).match(video_cache_info):
        みたいな感じで使う."""
        # 正規表現のpattern.match("abcde")みたいなapiを模倣している.
        # a は条件にマッチする
        # a.matches(query)
        # の方が英文としては自然な感じがするが
        # query.match(a)の方がapiとしては自然な感じがする(あくまで主観)
        # 混乱を招くようならlet's discuss
        self_asdict = self._asdict()
        for key in self_asdict:
            if self_asdict[key] is None:
                continue
            if getattr(video_cache_info, key) != self_asdict[key]:
                return False

        return True


class VideoCacheManager(object):

    """video_cache_infoと実際のファイルシステム上のキャッシュファイルを
    結びつけた上でCRUDを行うクラス.
    なるべくキャッシュがファイルであることを隠蔽することを目的としている.
    プログラマはvideo_cache_info.make_cache_file_path()
    を呼んで直接ファイルを操作するのではなく、
    出来る限りVideoCacheManagerを経由しなくてはならない."""
    # キャッシュがファイルであることを完全に隠蔽すると
    # ログを残すときにpathを表示されたかったり、
    # VideoCacheManagerにないファイル操作をしたいときに
    # 困ってしまうので、完全に隠蔽できない

    # [キャッシュへのwrite, read,close以外のCRUDはすべてVideoCacheManagerを経由させる]

    # 設計としてはVideoCacheInfo と VideoCacheManagerは
    # ORマッパーのEntity と EntityManager に当たる
    # が、管理するのがファイルシステム上のファイルなので、話がややこしくなってる
    # 本家nlのCacheクラスやjava.nio.File, python3.4のpathlibみたいに、
    # オブジェクトそのものにCRUD操作を実装する設計にするか非常に迷った
    # というか今も若干迷う
    # まあ、欲しくなったら本家nlのCacheクラスみたいなの作ってラップできるけどね

    # もしオブジェクトそのものにCRUD操作を実装する設計にすると
    # 例えば、初版のnicocache py(仮)のように
    # VideoCache と VideoCacheGetterに分けるとすると
    # ２つのクラスが別々にファイルシステム(実際にはFileSystemWrapperオブジェクト)
    # にアクセスすることになり、ファイルシステムであることを隠蔽する度合いが低くなる
    # ファイルシステムであることの隠蔽は、なるべく1つのクラスで行いたい

    # また、将来VideoCacheManagerでVideoCacheInfoをキャッシュしたくなった場合
    # FileSystemWrapperへの委譲を一ヶ所で隠蔽してないと不可能になってしまう

    # よって、キャッシュへのwrite, read,close以外のCRUDはすべてVideoCacheManagerを経由させる

    class AlreadyExistsError(Exception):

        def __init__(self, mes):
            Exception.__init__(self, mes)

    class NoSuchCacheError(Exception):

        def __init__(self, mes):
            Exception.__init__(self, mes)

    def __init__(self, filesystem_wrapper):
        self._filesystem_wrapper = filesystem_wrapper

    def exists(self, video_cache_info):
        return os.path.exists(video_cache_info.make_cache_file_path())

    def create_new_cache(self, video_cache_info):
        """キャッシュが既に存在していた場合例外を投げます"""
        cache_file_path = video_cache_info.make_cache_file_path()
        if self.exists(video_cache_info):
            raise self.AlreadyExistsError(video_cache_info)

        with self._filesystem_wrapper.open(cache_file_path, "w"):
            pass

    def get_cache_list(self, video_cache_info_query, recursive=True):
        video_cache_info_list = []
        rootdir = video_cache_info_query.rootdir
        walk_iterator = self._filesystem_wrapper.walk(
            rootdir, followlinks=True)
        if not recursive:
            walk_iterator = [next(walk_iterator)]

        for dirpath, _, filenames in walk_iterator:
            subdirpath = dirpath[len(rootdir):]  # rootdirの部分だけ取り除く
            for filename in filenames:
                # classがわからないので(VideoCacheInfoクラスを決め打ちしたくない)
                # インスタンスからクラスメソッドを呼んでいる
                a_video_cache_info = video_cache_info_query.\
                    create_from_filename(
                        filename, subdir=subdirpath, rootdir=rootdir)
                if video_cache_info_query.match(a_video_cache_info):
                    video_cache_info_list.append(a_video_cache_info)

        return video_cache_info_list

    def open_cache_file(self, video_cache_info, readonly=False):
        """存在していないキャッシュをopenしようとした場合例外を投げます"""
        cache_file_path = video_cache_info.make_cache_file_path()

        if readonly:
            mode = "rb"
        else:
            mode = "r+b"
        if not self.exists(video_cache_info):
            raise self.NoSuchCacheError(video_cache_info)
        return self._filesystem_wrapper.open(cache_file_path, mode)

    def update_cache_info(self, video_cache_info, new_video_cache_info):
        if not self.exists(video_cache_info):
            raise self.NoSuchCacheError(video_cache_info)
        oldpath = video_cache_info.make_cache_file_path()
        newpath = new_video_cache_info.make_cache_file_path()

        self._filesystem_wrapper.rename(oldpath, newpath)

    def remove_cache(self, video_cache_info):
        if not self.exists(video_cache_info):
            raise self.NoSuchCacheError(video_cache_info)
        self._filesystem_wrapper.remove(
            video_cache_info.make_cache_file_path())

    def get_mtime(self, video_cache_info):
        if not self.exists(video_cache_info):
            raise self.NoSuchCacheError(video_cache_info)
        return self._filesystem_wrapper.getmtime(
            video_cache_info.make_cache_file_path())

    def touch(self, video_cache_info):
        if not self.exists(video_cache_info):
            raise self.NoSuchCacheError(video_cache_info)
        self._filesystem_wrapper.touch(
            video_cache_info.make_cache_file_path())

############### unittest #####################
verbosity = 1
root_test_dir_path = "./_testdir"


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
        self.assertEqual(info.subdir, "")

    def test__make_cache_file_path(self):
        cache_file_name = "subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
        info = VideoCacheInfo.create_from_relpath(
            cache_file_name, rootdir="./cache/")
        cachefilepath = VideoCacheInfo.make_cache_file_path(info)

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


class NicoCacheTestCase(unittest.TestCase):

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

#     def get_real_path(self, path):
# return os.path.join(root_test_dir_path, self.__class__.__name__,  path)

    def get_testdir_path(self):
        return os.path.join(root_test_dir_path, self.__class__.__name__)


class TestVideoCacheManager(NicoCacheTestCase):

    def setUp(self):
        self.rm_testdir()

        self.make_testdir()
        self.makedir("subdir1")
        self.makedir("subdir2")

        self.make_file("tmp_sm10low_てすと.mp4")
        self.make_file("subdir1/tmp_so20low_タイトル.avi.mp4")

        self.make_file("subdir2/tmp_so20low_タイトル.avi.mp4")

        self.video_cache_manager = VideoCacheManager(
            pathutil.FileSystemWrapper())


#     def test__get_video_cache_filepath__topdir(self):
#         filepath = self.video_cache_manager.\
#             get_video_cache_filepath("sm10")
#
#         self.assertEqual(os.path.basename(filepath), "sm10.mp4")

    def test__create_new_cache(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm12345low_タイトル.mp4", rootdir=self.get_testdir_path())
        filepath = video_cache_info.make_cache_file_path()

        self.video_cache_manager.create_new_cache(video_cache_info)

        self.assertTrue(os.path.exists(filepath))

    def test__update_cache_info(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm10low_てすと.mp4", rootdir=self.get_testdir_path())
        oldfilepath = video_cache_info.make_cache_file_path()

        new_video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm12345low_タイトル.mp4", rootdir=self.get_testdir_path())
        filepath = new_video_cache_info.make_cache_file_path()

        self.video_cache_manager.update_cache_info(
            video_cache_info, new_video_cache_info)

        self.assertTrue(os.path.exists(filepath))

        self.assertFalse(os.path.exists(oldfilepath))

    def test__create_new_file__already_exist_error(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "tmp_sm10low_てすと.mp4", rootdir=self.get_testdir_path())

        with self.assertRaises(self.video_cache_manager.AlreadyExistsError):
            self.video_cache_manager.create_new_cache(video_cache_info)

    def test__get_cache_list(self):
        video_cache_info = VideoCacheInfo.make_query(
            video_id="so20", rootdir=self.get_testdir_path())
        video_cache_info_list = self.video_cache_manager.get_cache_list(
            video_cache_info)
        self.assertEqual(len(video_cache_info_list), 2)

        for video_cache_info in video_cache_info_list:
            self.assertEqual(video_cache_info.video_id, "so20")

    def test__remove_cache(self):
        video_cache_info = VideoCacheInfo.create_from_relpath(
            "subdir1/tmp_so20low_タイトル.avi.mp4",
            rootdir=self.get_testdir_path())
        self.video_cache_manager.remove_cache(video_cache_info)

        video_cache_info = VideoCacheInfo.create_from_relpath(
            "subdir2/tmp_so20low_タイトル.avi.mp4",
            rootdir=self.get_testdir_path())
        self.video_cache_manager.remove_cache(video_cache_info)

        query_info = VideoCacheInfo.make_query(
            video_id="so20", rootdir=self.get_testdir_path())

        self.assertEqual(
            len(self.video_cache_manager.get_cache_list(query_info)), 0)

    def test__touch(self):

        video_cache_info = VideoCacheInfo.create_from_relpath(
            "subdir1/tmp_so20low_タイトル.avi.mp4",
            rootdir=self.get_testdir_path())

        mtime0 = self.video_cache_manager.get_mtime(video_cache_info)

        self.video_cache_manager.touch(video_cache_info)

        mtime1 = self.video_cache_manager.get_mtime(video_cache_info)

        self.assertTrue(mtime1 > mtime0)


# def test():
#     if os.path.exists(root_test_dir_path):
#         shutil.rmtree(root_test_dir_path)
#     os.mkdir(root_test_dir_path)
#     unittest.main()
# if __name__ == "__main__":
#     test()
