# -*- coding: utf-8 -

from collections import namedtuple
import os
import re
import shutil

from . import pathutil


root_cache_dir = "cache"


def _if_not_None_else(newvalue, basevalue):
    return newvalue if newvalue is not None else basevalue


class NicoVideoTypeTable:

    """動画ファイルのURL(http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688lowとか)
    にはsmとかnmとかsoとか含まれない
    なのでhttp://www.nicovideo.jp/watch/sm12345みたいなアクセスがあったときに、
    番号と動画タイプの組をキャッシュしておく用のクラス"""
    # todo!!! スレッドセーフ"

    def __init__(self):
        self._table = {}

    def add_videoid(self, video_id):
        """video_idはsm12345とかnm67890みたいなの"""
        self.add_videotype_and_videonum(video_id[0:2], video_id[2:])

    def add_videotype_and_videonum(self, video_type, video_num):
        self._table[video_num] = video_type

    def get_videotype(self, video_num):
        if video_num in self._table:
            return self._table[video_num]
        return None


_VideoCacheInfo = namedtuple("VideoCacheInfo",
                             ["video_type",
                              "video_num",
                              "tmp",
                              "low",
                              "filename_extension",
                              "title",
                              "subdir",
                              "rootdir"])


class VideoCacheInfoParameterError(Exception):
    pass


class VideoCacheInfo(_VideoCacheInfo):
    # キャッシュのファイル名=メタデータに関するアルゴリズムはすべてこのクラスにまとめてあるので、
    # VideoCacheInfo=MyVideoCacheInfoな感じで一回モンキーパッチを当てれば置き換えられる

    pattern = re.compile("(?P<tmp>tmp_)?"
                         "(?P<video_type>\w\w)"
                         "(?P<video_num>[0-9]+)"
                         "(?P<low>low)?"
                         "(?P<_title>_.*)?")

    @property
    def video_id(self):
        return self.video_type + self.video_num

    def __new__(cls, video_type, video_num, tmp=None, low=None,
                filename_extension=None, title=None, subdir=None, rootdir=None):
        # ここのapiはまだ安定してない
        return _VideoCacheInfo.__new__(
            cls, video_type, video_num, tmp, low,
            filename_extension, title, subdir, rootdir)

    @classmethod
    def create(cls, rootdir, video_type=None, video_num=None, video_id=None, tmp=False, low=False,
               filename_extension="", title="", subdir=""):
        if video_id is not None:
            video_type = video_id[:2]
            video_num = video_id[2:]
        if (video_type is None and video_num is None):
            bad_video_cache_info = VideoCacheInfo(video_type, video_num, tmp, low,
                                                  filename_extension, title, subdir, rootdir)
            raise VideoCacheInfoParameterError(
                "(video_type, video_num) or video_id must be given.\n"
                " video_id=%s, %s" %
                (video_id, repr(bad_video_cache_info)))

        return cls(
            video_type, video_num,
            tmp, low, filename_extension,
            title, subdir=subdir, rootdir=rootdir)

    @classmethod
    def create_for_update(
            cls, rootdir=None, video_type=None, video_num=None,
            video_id=None, tmp=None, low=None,
            filename_extension=None, title=None,
            subdir=None):

        if video_id is not None:
            video_type = video_id[:2]
            video_num = video_id[2:]

        return cls(video_type, video_num, tmp, low,
                   filename_extension, title, subdir, rootdir)

    @classmethod
    def make_query(cls, rootdir, video_type=None, video_num=None, video_id=None, tmp=None, low=None,
                   filename_extension=None, title=None, subdir=None):
        if video_id is not None:
            video_type = video_id[:2]
            video_num = video_id[2:]
        return cls(video_type, video_num, tmp, low, filename_extension, title, subdir, rootdir)

    def replace(self, **kwargs):
        return self._replace(**kwargs)

    def update(self, new_video_cache_info):
        new_info_asdict = new_video_cache_info._asdict()
        for key in new_info_asdict:
            if new_info_asdict[key] is None:
                del new_info_asdict[key]

        return self.replace(**new_info_asdict)

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

        if m.group("tmp"):
            tmp = True

        video_type = m.group("video_type")
        video_num = m.group("video_num")

        if m.group("low"):
            low = True

        if m.group("_title"):
            title = m.group("_title")[1:]  # _(アンダーバー)もタイトルにマッチしてしまうので[1:]とする

        return cls(
            video_type, video_num,
            tmp, low, filename_extension,
            title, subdir=subdir, rootdir=rootdir)

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


class CacheAlreadyExistsError(Exception):

    def __init__(self, mes):
        Exception.__init__(self, mes)


class NoSuchCacheError(Exception):

    def __init__(self, mes):
        Exception.__init__(self, mes)


class VideoCache:

    @classmethod
    def get_cache_list(
            cls, filesystem_wrapper, video_cache_info_query, recursive=True):

        video_cache_list = []
        rootdir = video_cache_info_query.rootdir
        walk_iterator = filesystem_wrapper.walk(
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
                    video_cache = cls(filesystem_wrapper, a_video_cache_info)
                    video_cache_list.append(video_cache)

        return video_cache_list

    def __init__(self, filesystem_wrapper, video_cache_info):
        self._filesystem_wrapper = filesystem_wrapper
        self._video_cache_info = video_cache_info

    @property
    def info(self):
        return self._video_cache_info

    def exists(self):
        return os.path.exists(self._video_cache_info.make_cache_file_path())

    def create(self):
        """キャッシュが既に存在していた場合例外を投げます"""
        cache_file_path = self._video_cache_info.make_cache_file_path()
        if self.exists():
            raise CacheAlreadyExistsError(self._video_cache_info)

        with self._filesystem_wrapper.open(cache_file_path, mode="wb"):
            pass

    def open(self, readonly=False):
        cache_file_path = self._video_cache_info.make_cache_file_path()

        if readonly:
            mode = "rb"
        else:
            mode = "r+b"

        return self._filesystem_wrapper.open(cache_file_path, mode)

    def update_cache_info(self, new_video_cache_info):

        new_video_cache_info = self._video_cache_info.update(
            new_video_cache_info)
        oldpath = self._video_cache_info.make_cache_file_path()
        newpath = new_video_cache_info.make_cache_file_path()

        self._filesystem_wrapper.rename(oldpath, newpath)

        self._video_cache_info = new_video_cache_info

    def get_size(self):
        return os.path.getsize(self._video_cache_info.make_cache_file_path())

    def remove(self):
        if not self.exists():
            raise NoSuchCacheError(self._video_cache_info)
        self._filesystem_wrapper.remove(
            self._video_cache_info.make_cache_file_path())

    def get_mtime(self):
        if not self.exists():
            raise NoSuchCacheError(self._video_cache_info)
        return self._filesystem_wrapper.getmtime(
            self._video_cache_info.make_cache_file_path())

    def touch(self):
        """unixのtouchコマンドと違い、touchで新規作成できないので注意"""

        if not self.exists():
            raise NoSuchCacheError(self._video_cache_info)
        self._filesystem_wrapper.touch(
            self._video_cache_info.make_cache_file_path())

    def change_to_complete_cache(self):

        new_video_cache_info = self._video_cache_info.replace(tmp=False)
        self.update_cache_info(new_video_cache_info)
