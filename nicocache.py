# -*- coding: utf-8 -

#     Copyright (C) 2015  LHO425
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging as _logging
import xml.etree.cElementTree as ElementTree
import StringIO
import re
import mimetypes
from proxtheta.utility.proxy import convert_upstream_error
from proxtheta.core.common import ResponsePack
from copy import copy, deepcopy
from proxtheta.utility.server import is_request_to_this_server
#_logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")


import urllib2

from proxtheta.core import httpmes
from proxtheta import utility, core
import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server
from proxtheta.utility.common import safe_close
import time
import importlib
import pkgutil
logger = _logging.getLogger("nicocache.py")
# logger.setLevel(_logging.DEBUG)
logger.info("nicocache.py")

# proxtheta.utility.client.logger.setLevel(_logging.DEBUG)
# proxtheta.logger.setLevel(_logging.DEBUG)

if 0:
    """Type Define"""
    logger = _logging.Logger()


def getthumbinfo(video_id):
    """
    http://ext.nicovideo.jp/api/getthumbinfo api wrapper
    returns xml (str)
    """
    return urllib2.urlopen(
        "http://ext.nicovideo.jp/api/getthumbinfo/" + video_id).read()


def getthumbinfo_etree(video_id):
    return ElementTree.fromstring(getthumbinfo(video_id))


def get_file_len(afile):
    """afile is fileobj, not path str"""
    orig_file_pointer = afile.tell()
    afile.seek(0, 2)
    length = afile.tell()
    afile.seek(orig_file_pointer, 0)
    return length


# os.walkはとても遅い
# C言語で実装された速いwalkの実装があるかもしれない
# どのwalkの実装を使うかを後からプラグイン等で変えられるように外に出しておく
walk = os.walk


def get_pathlist(dirpath, recursive=False):
    """pathlistとは [(dirpath, dirlist, filelist),...]である
    dirlistはdirpath直下にあるディレクトリのリストで、filelistはdirpath直下にあるファイルのリストである"""
    if recursive:
        return list(walk(dirpath, followlinks=True))
    else:
        for lst in walk(dirpath, followlinks=True):
            return [lst]


def get_dirpathlist(dirpath, recursive=True):
    """recursive == True の場合dirpathを再帰的に検索し
    [dirpath, subdirpath1, subdirpath2 ...]
    なるリストを返す
    recursive == Falseなら
    [dirpath]
    を返す"""

    if not recursive:
        return [dirpath]

    pathlist = get_pathlist(dirpath, recursive=True)
    return get_dirpathlist_from_pathlist(pathlist)


def get_dirpathlist_from_pathlist(pathlist):
    dirpathlist = []

    # tplは(dirpath, dirlist, filelist)なるタプル
    for tpl in pathlist:
        dirpathlist.append(tpl[0])

    return dirpathlist


def get_videonum_with_httpreq(req):
    try:
        _, query_value = req.query.split('=')
        video_num = query_value.split('.')[0]
    except ValueError:
        raise RuntimeError(
            "get_videonum_with_httpreq(): error. query: " + req.query)
    return video_num


def get_videoid_with_httpreq(video_type_cacher, req):
    """httpリクエストをヒントにしてvideo idを得る
    video_type_cacherから得られなかった時は推論も行う
    video_type_cacher = None のときは推論のみ行う"""
    # url: http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
    # query: m=24992647.47688low

    try:
        query_name, query_value = req.query.split('=')
        video_num = query_value.split('.')[0]
    except ValueError:
        raise RuntimeError(
            "get_videoid_with_httpreq(): error. query: " + req.query)

    video_type = None
    if video_type_cacher is not None:
        video_type = video_type_cacher.get_videotype(video_num)

    if video_type is None:
        if query_name == "s":
            video_type = "nm"
        else:
            video_type = "sm"

    return video_type + video_num


def make_video_cache_prefix(video_id, tmp=False, low=False):
    # video_cache_prefixは tmp_sm12345low みたいなの
    # tmp_sm12345low.mp4だったり、tmp_sm12345low_タイトル.mp4だったりするので、最後にアンダーバーは入れない
    video_cache_prefix = video_id
    if tmp:
        video_cache_prefix = "tmp_" + video_cache_prefix
    if low:
        video_cache_prefix = video_cache_prefix + "low"

    return video_cache_prefix


def make_video_cache_filename(
        video_id, filename_extension, tmp=False, low=False, title=""):
    """tmp_sm12345low.mp4とかtmp_sm12345low_タイトル.mp4みたいなのを返す
    titleがNoneか""ならtmp_sm12345low.mp4みたいなのを返す
    filename_extensionは'.'で始まらない'mp4'とか'swf'とかの文字列"""
    video_cache_prefix = make_video_cache_prefix(video_id, tmp, low)
    if (title is None) or (title == ""):
        return ''.join((video_cache_prefix, '.', filename_extension))
    else:
        return ''.join(
            (video_cache_prefix, '_', title, '.', filename_extension))


def parse_video_cache_filename(cachefilename):
    """return (video_type, video_num, title, 
    filename_extension, is_tmp, is_low)"""
    tmp = False
    low = False
    title = ""
    m = re.match(
        "(tmp_)?(\w\w)([0-9]+)(low)?(_.*)?[.]([^.]*)", cachefilename)

    if not m:
        return None

    if m.group(1):
        tmp = True

    video_type = m.group(2)
    video_num = m.group(3)

    if m.group(4):
        low = True
    if m.group(5):
        title = m.group(5)[1:]  # _(アンダーバー)もタイトルにマッチしてしまうので[1:]とする
    filename_extension = m.group(6)

    return (video_type, video_num, title, filename_extension, tmp, low)


def get_video_cache_filepath(
        video_id, pathlist, tmp=False, low=False, recursive=True):
    """video_idはsmとかsoで始まるstr
    filename_extensionは'flv'や'mp4'('.'を含めてはいけない)"""

    video_cache_prefix = make_video_cache_prefix(video_id, tmp, low)

    if not recursive:
        pathlist = (pathlist[0],)

    for (dirpath, _, filenames) in pathlist:
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            # video_cache_prefixにはアンダーバーを含んでいないので注意
            if (filename.startswith(''.join((video_cache_prefix, "_"))) or
                    filename.startswith(''.join((video_cache_prefix, ".")))):
                logger.debug(filepath + ": matched!")
                return filepath
            else:
                logger.debug(filepath + ": not matched.")

    return None


mimetypes.add_type("video/flv", ".flv")  # ここに書くのはなぁ


def guess_mimetype(path):
    return mimetypes.guess_type(path)[0]


def guess_filename_extension(mimetype):
    """
    mimetypeから拡張子の推測
    mimetype は  'video/mp4' のような文字列
    return は  "."を含まない拡張子 または None
    """
    extension = mimetypes.guess_extension(mimetype)
    if extension is None:
        return None
    else:
        return extension[1:]  # mimetypes の extension は"."を含むため
    return


class CachingReader(object):

    def __init__(self, cachefile, originalfile, length,
                 complete_cache=False, logger=logger):
        """
        cachefile must be opened read/write able mode.
        if complete_cache: when cacheio.close(), complete cache.
        """
        self._cachefile = cachefile
        self._originalfile = originalfile
        self._complete_cache = complete_cache

        self._logger = logger

        self._read_from_cachefile = True
        self._length = length
        self._left_size = length
        self._closed = False

    def read(self, size=-1):
        # jp!!!返るデータの大きさがsizeであることは(もしくはEOFまで読み込んでいることは)下位のread()関数が保証している(多分)
        if self._left_size == 0:
            self._logger.debug("CachingReader.read(): left size is 0. EOF")
            return ""

        if size < 0:
            self._logger.debug("CachingReader.read(): read all.")
            return self.read(self._left_size)

        else:
            self._logger.debug(
                "CachingReader.read(): start read(). left size is %d byte", self._left_size)
            self._logger.debug(
                "CachingReader.read(): requested size to read is %d byte", size)
            data = ''

            if self._read_from_cachefile:
                data_from_cache = self._cachefile.read(size)
                # jp!!!"このメソッドは、 size バイトに可能な限り近くデータを取得するために、背後の C 関数 fread() を 1 度以上呼び出すかもしれないので注意してください。"
                # とライブラリリファレンスにあるので、len(data_from_cache) == sizeは保証されている
                self._logger.debug(
                    "CachingReader.read(): read %d byte from cache file", len(data_from_cache))
                data = data_from_cache

                if len(data_from_cache) < size:
                    # jp!!!キャッシュのデータでは足りないので、残りは下でオリジナルから読み出す
                    self._read_from_cachefile = False
                    size -= len(data_from_cache)

            if not self._read_from_cachefile:
                data_from_orig = self._originalfile.read(size)
                self._logger.debug(
                    "CachingReader.read(): read %d byte from original file", len(data_from_orig))
                self._cachefile.write(data_from_orig)
                self._logger.debug(
                    "CachingReader.read(): write %d byte to cache file", len(data_from_orig))

                if len(data) > 0:
                    # jp!!!すでにcachefileから読まれたデータがあるとき
                    data = ''.join((data, data_from_orig))
                else:
                    data = data_from_orig

            self._left_size -= len(data)
            self._logger.debug("CachingReader.read(): read %d byte", len(data))
            self._logger.debug(
                "CachingReader.read(): end read(). left size is %d byte", self._left_size)
            return data

    @property
    def closed(self):
        return self._closed

    def close(self):
        if self._complete_cache:
            self._logger.debug(
                "CachingReader.close(): start completing cache. left size is %d byte. seek to end of cache file", self._left_size)
            self._cachefile.seek(0, 2)
            self._left_size = self._length - self._cachefile.tell()
            self._read_from_cachefile = False
            self._logger.debug(
                "CachingReader.close(): left size is %d byte (only original file). start appending to cache file", self._left_size)

            # read(self._left_size) is not good when self._left_size is too
            # large
            while True:
                data = self.read(8192)
                if len(data) < 8192:
                    break
            self._logger.debug(
                "CachingReader.close(): left size is %d byte. end completing cache.", self._left_size)
        self._cachefile.close()
        self._originalfile.close()  # fixme!!!例外安全じゃない
        self._cachefile = None
        self._originalfile = None
        self._closed = True

    def __del__(self):
        if not self._closed:
            try:
                self._logger.error(
                    "CachingReader was closed by GC! Resource leaking!")
                self._logger.error(object.__repr__(self))
            except:
                pass

            try:
                self.close()
            except:
                pass


# def find_cachefile(video_id):
    # jp!!!
    # ローカルのcacheフォルダを再帰的に検査して、キャッシュファイルが見つかればそれの相対パスを返す

# キャッシュファイル検索とキャッシュをブラウザに送る流れ(再帰検索しない)
# video_num(smとかsoとか含まない)が与えられる
#pathes = glob.glob("./cache/??" + video_num + "[!0-9]*")


#??video_numにマッチするファイルのリストを得る(lowでない)
# ローカルに完全な非エコノミーキャッシュファイルがあるなら:
#    openして返す
# else(非エコノミーキャッシュファイルが中途半端なキャッシュなら、もしくはキャッシュがないなら):
#    キャッシュの続きが非エコノミーでとれるなら:
#        NicoCachingReaderを提供
#    エコノミー動画しかとれないなら:
#        ローカルに完全なエコノミーキャッシュファイルがあるなら:
#            openして返す
#        中途半端なキャッシュしかない、もしくはキャッシュがないなら:
#                NicoCachingReaderを提供
#


# 複数キャッシュファイルがあったら:
# warningだして最初のやつを使う

# 動画タイトルが変更されていた場合:
#    動画タイトル変更に対応するオプションがTrueなら:
#        ローカルキャッシュのタイトルも変更

# sm123456.mp4みたいに、タイトルがふくまれないものがあったら:
#    動画タイトル変更に対応するオプションがTrueなら:
#        現在のタイトルを取得、して設定

# NicoCachingReaderでキャッシュ完了したら:
#    tmp_...を...にリネームする


class CacheFilePathListTable(object):

    """いちいちファイル一覧を取得していると遅い人のためにキャッシュ可能のインターフェースを作る
    スレッドセーフ"""
    # todo!!! スレッドセーフ

    def __init__(self, cachedirpath, recursive=False):
        self._cachedirpath = cachedirpath
        self._pathlist = get_pathlist(cachedirpath, recursive)

    @property
    def dirpath(self):
        return self._cachedirpath

    def get_video_cache_filepath(self, video_id,
                                 tmp=False, low=False,
                                 recursive=True):
        return get_video_cache_filepath(
            video_id, self._pathlist, tmp, low, recursive)

    def get_dirpathlist(self):
        return get_dirpathlist_from_pathlist(self._pathlist)

    def insert(self, video_id, filename_extension,
               tmp=False, low=False, title=""):
        """tableの更新
        追加するのは一番上の 階層に、なので注意"""
        if self.get_video_cache_filepath(video_id,
                                         tmp, low,
                                         recursive=False) is not None:
            # すでにトップ階層に存在している場合
            return

        self._pathlist[0][2].insert(0,
                                    make_video_cache_filename(video_id,
                                                              filename_extension,
                                                              tmp, low,
                                                              title))

    def remove(self, video_id, tmp=False, low=False,
               ignore_value_error=True):
        """ignore_value_error=Falseのとき、該当する項目がなければエラーとなります。
        再帰的に検索して削除するわけじゃないから注意"""
        filepath = self.get_video_cache_filepath(
            video_id, tmp, low, recursive=False)
        if filepath is None:
            filename = make_video_cache_filename(
                video_id, "???", tmp, low, "")
            raise ValueError(filename + " not in list")

        filename = os.path.basename(filepath)
        self._pathlist[0][2].remove(filename)


class NicoCacheFileSystem:

    """ファイルシステムとPathListTableの簡易的ラッパー
    nicocache.pyに必要な機能しかない
    ファイル名のリストをキャッシュしつつ実際のファイルシステムと同期する
    スレッドセーフ(PathListTableがスレッドセーフだから)"""

    class AlreadyExistsError(Exception):

        def __init__(self, mes):
            Exception.__init__(self, mes)

    class NoSuchCacheFileError(Exception):

        def __init__(self, mes):
            Exception.__init__(self, mes)

    def __init__(self, cachedirpath, recursive=True):

        self._pathlisttable = CacheFilePathListTable(cachedirpath, recursive)

    @property
    def cachedirpath(self):
        return self._pathlisttable.dirpath

    def create_new_file(
            self, video_id, filename_extension, tmp=False, low=False, title=""):
        """トップの階層にファイルを作る
        既に存在していたら例外投げる"""
        fpath = self.get_video_cache_filepath(video_id, tmp, low)
        if fpath is not None:
            raise self.AlreadyExistsError(fpath)

        filename = make_video_cache_filename(
            video_id, filename_extension, tmp, low, title)
        fpath = os.path.join(self.cachedirpath, filename)
        if os.path.exists(fpath):
            raise self.AlreadyExistsError(fpath)

        with open(fpath, "wb"):
            pass

        self._pathlisttable.insert(
            video_id, filename_extension, tmp, low, title)

    def get_video_cache_filepath(self, video_id,
                                 tmp=False, low=False):
        filepath = self._pathlisttable.get_video_cache_filepath(
            video_id, tmp, low)

        if (filepath is not None) and (not os.path.exists(filepath)):
            self._pathlisttable.remove(
                video_id, tmp, low, ignore_value_error=False)
            filepath = None

        return filepath

    def rename(self, video_id, tmp, low,
               new_tmp=None, new_low=None, new_title=None):
        """トップの階層のファイルのリネーム
        最初の３つの引数はキャッシュファイルの特定に必要
        変更の必要のない項目はNoneを代入してください.
        変更対象のキャッシュファイルが存在しない場合エラー"""

        oldfilepath = self.get_video_cache_filepath(video_id, tmp, low)
        if oldfilepath is None:
            # 変更対象のキャッシュファイルが存在しない場合エラー
            raise self.NoSuchCacheFileError("video_id: " + video_id + ", " +
                                            "tmp: " + str(tmp) + ", " +
                                            "low: " + str(low))

        oldfilename = os.path.basename(oldfilepath)
        _, _, title, filename_extension, _, _ = parse_video_cache_filename(
            oldfilename)

        # テーブルの更新その1
        self._pathlisttable.remove(
            video_id, tmp, low, ignore_value_error=False)

        if new_tmp is None:
            new_tmp = tmp
        if new_low is None:
            new_low = low
        if new_title is None:
            new_title = title

        newfilename = make_video_cache_filename(video_id,
                                                filename_extension,
                                                new_tmp, new_low,
                                                new_title)
        newfilepath = os.path.join(self.cachedirpath, newfilename)

        # ファイルシステム上の更新
        try:
            os.rename(oldfilepath, newfilepath)
        except Exception:
            # トランザクション
            self._pathlisttable.insert(
                video_id, filename_extension, tmp, low, title)
            logger.warning(
                "NicoCacheFileSystem.rename(): os.rename failed. So NicoCacheFileSystem.rename() stopped.")
            raise

        # テーブルの更新その2
        self._pathlisttable.insert(video_id,
                                   filename_extension,
                                   new_tmp, new_low,
                                   new_title)

    def search_cache_file(
            self, video_id, filename_extension, tmp=False, low=False, title=""):
        """
        実際のファイルシステムについて、キャッシュルートディレクトリとサブディレクトリにキャッシュがあるか順に調べる
        時間がかかる
        必ずget_video_cache_filepath()で見つからなかった場合にのみ呼び出すこと
        さもなければ例外を投げる
        """
        if self.get_video_cache_filepath(video_id, tmp, low) is not None:
            raise RuntimeError(
                "NicoCacheFileSystem: search_cache_file() called but get_video_cache_filepath() is not None!")

        filename = make_video_cache_filename(
            video_id, filename_extension, tmp, low, title)
        dirpathlist = self._pathlisttable.get_dirpathlist()
        for dirpath in dirpathlist:
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):
                self._pathlisttable.insert(
                    video_id, filename_extension, tmp, low, title)
                return True

        return False


class NicoVideoTypeTable:

    """動画ファイルのURL(http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688lowとか)
    にはsmとかnmとかsoとか含まれない
    なのでhttp://www.nicovideo.jp/watch/sm12345みたいなアクセスがあったときに、
    番号と動画タイプの組をキャッシュしておく用のクラス"""
    # todo!!! スレッドセーフ"

    def __init__(self):
        self._entry_table = {}

    def add_videoid(self, video_id):
        """video_idはsm12345とかnm67890みたいなの"""
        self.add_videotype_and_videonum(video_id[0:2], video_id[2:])

    def add_videotype_and_videonum(self, video_type, video_num):
        self._entry_table[video_num] = video_type

    def get_videotype(self, video_num):
        if video_num in self._entry_table:
            return self._entry_table[video_num]
        return None


class VideoCache:

    """このクラスで保管する属性データはファイルシステム上のファイル名と、テーブル上のデータと同期しなければならない
    クラス上のメンバ変数に属性データを保存し、変更するときはファイルシステムとテーブルの両方に変更を反映させることにする
    だけど、将来的にpathlisttableがファイルシステム監視できるようになったらどうすんの？
    Answer: ファイルシステム監視の結果がVideoCacheオブジェクトに同期されるのは、VideoCacheオブジェクトが作られるまで、とすればOK"""

    @staticmethod
    def get(nicocache_filesystem, video_id, low=False):
        return VideoCache(nicocache_filesystem, video_id, low)

    @staticmethod
    def fetch(nicocache_filesystem, video_id, low=False):
        """テーブルに存在するキャッシュのpathからVideoCacheを構成する
        テーブル上にvideo_idのキャッシュのpathが無かったらNoneを返す"""

        video_cache = VideoCache(nicocache_filesystem, video_id, low)
        if not video_cache.exsists_in_filesystem():
            return None

        return video_cache

    @staticmethod
    def create(nicocache_filesystem, video_id,
               filename_extension, low=False, title=""):
        """テーブル上に新しくキャッシュpathを作った上でVideoCacheを構成する
        既にテーブル上にvideo_idのキャッシュpathが存在する場合、例外を投げるのめんどくさいのでNoneを返す"""

        video_cache = VideoCache(nicocache_filesystem, video_id, low)
        if video_cache.exsists_in_filesystem():
            return None

        video_cache.set_title(title)
        video_cache.set_filename_extension(filename_extension)

        return video_cache

    def __init__(self, nicocache_filesystem, video_id, low):
        if 0:
            """Arg Type"""
            nicocache_filesystem = NicoCacheFileSystem()

        # 大事なオブジェクト　このクラスの肝
        self._nicocache_filesystem = nicocache_filesystem

        # パラメタ
        self._video_id = video_id
        self._is_low = low

        # 下の方で初期化されてほしい子たち
        # 紛らわしいのでメンバ変数の定義は一ヶ所にまとめておく
        self._title = str()
        self._filename_extension = str()
        self._exsists_in_filesystem = bool()
        self._is_tmp = bool()

        #### 初期化処理 ####
        for tmp in (False, True):
            cachefilepath = self._nicocache_filesystem.get_video_cache_filepath(self._video_id,
                                                                                tmp, low)
            if cachefilepath is not None:
                self._exsists_in_filesystem = True
                self._is_tmp = tmp

                _, _, title, filename_extension, _, _ = parse_video_cache_filename(
                    os.path.basename(cachefilepath))
                self._title = title
                self._filename_extension = filename_extension
                return

        # キャッシュがファイルシステム無かった場合ここへくる
        self._title = ""
        self._filename_extension = "unknown"
        self._exsists_in_filesystem = False
        self._is_tmp = True
        return

    def get_title(self):
        return self._title

    def get_videoid(self):
        """video id はsm123とかnm123とかso123とか"""
        return self._video_id

    def get_videonum(self):
        """video number (str type) はvideo idから先頭のsmとかnmとかsoとかと取り除いたもの、1234みたいなただの数値の文字列"""
        return self._video_id[2:]

    def get_videotype(self):
        """video typeはsmとかnmとかsoとかのこと"""
        return self._video_id[:2]

    def exsists_in_filesystem(self):
        """実際のファイルシステム上に存在するならTrue, ないならFalse"""
        return self._exsists_in_filesystem

    def is_economy(self):
        return self._is_low

    def is_not_economy(self):
        return (not self.is_economy())

    def is_tmp(self):
        return self._is_tmp

    def is_complete(self):
        return (not self._is_tmp)

    def set_title(self, title):
        if not self.exists_in_root_cachedir():
            raise NotImplementedError(
                "rename title of cache file in sub directory is not allowed!")

        if self._title == title:
            return

        if self._exsists_in_filesystem:
            self._ncfs__rename(new_title=title)

        self._title = title

    def set_filename_extension(self, filename_extension):
        if self._exsists_in_filesystem:
            raise NotImplementedError(
                "rename filename_extension of complete cache file is not allowed!")

        self._filename_extension = filename_extension

    def get_cachefilelen(self):
        if not self._exsists_in_filesystem:
            return 0

        return os.path.getsize(self.get_video_cache_filepath())

    def get_cachefilename(self):
        return make_video_cache_filename(self._video_id,
                                         self._filename_extension,
                                         self._is_tmp, self._is_low,
                                         self._title)

    def get_video_cache_filepath(self):
        return self._ncfs__get_video_cache_filepath()

    def get_cachefile(self):
        if not self._exsists_in_filesystem:
            self._ncfs__create_new_file()
            self._exsists_in_filesystem = True

        cachefilepath = self._ncfs__get_video_cache_filepath()

        if self._is_tmp:
            return open(cachefilepath, "r+b")
        else:
            return open(cachefilepath, "rb")

    def change_to_complete_cache(self):
        """ファイルシステム上のキャッシュファイルのファイル名から"tmp_"を取り除く
        NOTICE: get_cachefile()で作ったファイルのclose()は一切行われない。"""
        self._ncfs__rename(
            new_tmp=False, new_low=None, new_title=self._title)
        self._is_tmp = False

    def exists_in_root_cachedir(self):
        """サブディレクトリにあるならFalse"""
        if not self._exsists_in_filesystem:
            # 新規にキャッシュファイルがつくられる場合、必ずrootのキャッシュdir直下にできる、この場合は作成が遅延されている
            return True

        cachedirname = os.path.dirname(self._ncfs__get_video_cache_filepath())

        return cachedirname == self._nicocache_filesystem.cachedirpath

    def _ncfs__rename(self, new_tmp=None, new_low=None, new_title=None):
        self._nicocache_filesystem.rename(self._video_id, self._is_tmp, self._is_low,
                                          new_tmp, new_low, new_title)

    def _ncfs__get_video_cache_filepath(self):
        return self._nicocache_filesystem.get_video_cache_filepath(self._video_id,
                                                                   self._is_tmp, self._is_low)

    def _ncfs__create_new_file(self):
        self._nicocache_filesystem.create_new_file(self._video_id,
                                                   self._filename_extension,
                                                   self._is_tmp, self._is_low,
                                                   self._title)


class VideoCacheGetter:

    def __init__(self, nicocache_filesystem, VideoCacheClass=VideoCache):

        if 0:
            """member type"""
            self._VideoCacheClass = VideoCache

        self._nicocache_filesystem = nicocache_filesystem
        self._VideoCacheClass = VideoCacheClass

    def get(self, video_id, low):
        return self._VideoCacheClass.get(
            self._nicocache_filesystem, video_id, low)

    def fetch(self, video_id, low):
        return self._VideoCacheClass.fetch(
            self._nicocache_filesystem, video_id, low)

    def create(self, video_id, filename_extension, low, title=""):
        return self._VideoCacheClass.create(
            self._nicocache_filesystem, video_id, filename_extension, low, title)

    def search(self, video_id, filename_extension, low, title=""):
        """まずfetch()する
        fetch()で見つからなかったら実際のファイルシステムについて、キャッシュルートディレクトリとサブディレクトリにキャッシュがあるか順に調べる
        見つかればVideoCacheClass()が返る
        見つかんなかったらNoneを返す
        時間がかかるかもしれない
        見つかったキャッシュファイルの拡張子が、引数で指定したfilename_extensionになってることは保証しない"""
        video_cache = self.fetch(video_id, low)
        if video_cache is not None:
            return video_cache

        for tmp in (True, False):
            if self._nicocache_filesystem.search_cache_file(
                    video_id, filename_extension, tmp, low, title):
                return self.fetch(video_id, low)

        return None


def abandon_body(res, body_file):
    if body_file is None:
        return
    if res.is_chunked():
        utility.server.trancefer_chunked(body_file, StringIO.StringIO())
        return
    length = httpmes.get_transfer_length(res)
    if length == "unknown":
        return

    body_file.read(length)


class ThumbInfo(object):

    class NotThumbInfoError(Exception):
        pass

    def __init__(self, video_id):
        thumbinfo_etree = getthumbinfo_etree(video_id)
        try:
            self.video_id = video_id
            self.title = thumbinfo_etree.find(".//title").text.encode("UTF-8")
            self.movie_type = thumbinfo_etree.find(".//movie_type").text
            self.size_high = thumbinfo_etree.find(".//size_high").text
            self.size_low = thumbinfo_etree.find(".//size_low").text
        except AttributeError:
            raise ThumbInfo.NotThumbInfoError(str(thumbinfo_etree))


def get_partial_http_resource((host, port),
                              req,
                              first_byte_pos,
                              last_byte_pos=None,
                              server_sockfile=None,
                              load_body=False,
                              nonproxy_camouflage=True):
    """Rengeヘッダをつけてからリクエストを送る"""
    if last_byte_pos is not None:
        req.headers["Range"] = (
            ''.join(("bytes=", str(first_byte_pos), "-", str(last_byte_pos))))
    else:
        req.headers["Range"] = (''.join(("bytes=", str(first_byte_pos), "-")))
    return proxtheta.utility.client.get_http_resource((host, port), req,
                                                      server_sockfile,
                                                      load_body,
                                                      nonproxy_camouflage)


class NicoCachingReader(CachingReader):
    # ***設計思想***
    # using cache: とかPartial download fromとかのキャッシュに関するログはすべてこのクラスのスコープで行うようにする

    @classmethod
    def create_response_with_complete_localcache(cls, video_cache):
        """ローカルのキャッシュ(video_cache)だけを使用して動画リソース(ResponsePack)を返します
        video_cacheがtmpの場合動作は未定義です
        必ずチェックしてからこの関数に渡してください"""

        if video_cache.is_tmp():
            raise RuntimeError(
                "create_response_with_complete_localcache(): video_cache must complete!")

        logger.info("using cache: %s",
                    video_cache.get_cachefilename())

        res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))
        res.set_content_length(video_cache.get_cachefilelen())
        res.headers["Content-Type"] = "video/mp4"

        return proxtheta.server.ResponsePack(res, video_cache.get_cachefile())

    @classmethod
    def create_with_tmp_localcache_and_server(cls, video_cache,
                                              videofile_from_server,
                                              complete_video_size,
                                              complete_cache=False):
        """ローカルのキャッシュ(video_cache)と
        サーバからの動画ファイル(videofile_from_server)
        を使用してNicoCachingReaderを返します
                video_cacheがtmpでない場合動作は未定義です
                必ずチェックしてからこの関数に渡してください"""
        if not video_cache.is_tmp():
            raise RuntimeError(
                "create_with_tmp_localcache_and_server():"
                " video_cache must　not complete!")

        if video_cache.exsists_in_filesystem():
            logger.info(
                "temporary cache found: %s",
                video_cache.get_cachefilename())
            logger.info(
                "Partial download from %d byte",
                video_cache.get_cachefilelen())
        else:
            logger.info(
                "no cache found: " + video_cache.get_cachefilename())
        return NicoCachingReader(video_cache,
                                 originalfile=videofile_from_server,
                                 length=complete_video_size,
                                 complete_cache=complete_cache,
                                 logger=logger)

    @classmethod
    def create_response_with_tmp_localcache_and_server(cls, video_cache,
                                                       respack,
                                                       complete_video_size,
                                                       complete_cache=False):
        """ローカルのキャッシュ(video_cache)と
        サーバからの動画ファイル(videofile_from_server)
        を使用してNicoCachingReaderを返します
                video_cacheがtmpでない場合動作は未定義です
                respack.res.status_code == 206 and respack.res.is_chunked()　
                が Falseの場合動作は未定義です
                必ずチェックしてからこの関数に渡してください"""

        if respack.res.status_code != 206 or respack.res.is_chunked():
            raise RuntimeError("server response must be 206 and NOT chunked!\n"
                               "%s" % respack.res)

        ncr = cls.create_with_tmp_localcache_and_server(
            video_cache,
            videofile_from_server=respack.body_file,
            complete_video_size=complete_video_size,
            complete_cache=complete_cache)

        respack.body_file = ncr
        respack.res.status_code = 200
        respack.res.reason_phrase = "OK"
        respack.res.headers[
            "Content-Length"] = str(complete_video_size)
        return respack

#     @staticmethod
#     def _get_http_resource_with_complete_localcache(video_cache,
#                                                     server_sockfile=None,
#                                                     logger=logger):
#         """ローカルのキャッシュ(video_cache)だけを使用して動画リソース(ResponsePack)を返します
#         video_cacheがtmpの場合例外を投げます
#         必ずチェックしてからこの関数に渡してください"""
#
#         if video_cache.is_tmp():
#             raise RuntimeError(
#                 "_get_http_resource_with_complete_localcache(): video_cache must complete!")
#
#         safe_close(server_sockfile)
#
#         logger.info("using cache: " + video_cache.get_cachefilename())
#
#         res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))
#         res.set_content_length(video_cache.get_cachefilelen())
#
#         return proxtheta.server.ResponsePack(res, video_cache.get_cachefile())
#
#     @staticmethod
#     def _get_http_resource_with_tmp_localcache_and_server(video_cache, complete_video_size, xxx_todo_changneme,
#                                                             req,
#                                                             server_sockfile=None,
#                                                             nonproxy_camouflage=False,
#                                                             complete_cache=False, logger=logger):
#         """ローカルのキャッシュ(video_cache)と(host, port)で与えられたサーバを使用して動画リソース(ResponsePack)を返します
#         video_cacheがtmpでない場合例外を投げます
#         必ずチェックしてからこの関数に渡してください"""
#         (host, port) = xxx_todo_changneme
#         try:
#             if not video_cache.is_tmp():
#                 raise RuntimeError(
#                     "_get_http_resource_with_tmp_localcache_and_server(): video_cache must　not complete!")
#
#             del req.headers["Accept-Encoding"]
# http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
#             if req.query.endswith("low"):
#                 req.query = req.query[:-3]
#
# http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688
#             if video_cache.is_economy():
#                 req.query = req.query + "low"
#
#             respack = get_partial_http_resource((host, port), req,
#                                                 first_byte_pos=video_cache.get_cachefilelen(),
#                                                 last_byte_pos=None,
#                                                 server_sockfile=server_sockfile,
#                                                 nonproxy_camouflage=nonproxy_camouflage)
#             server_sockfile = respack.server_sockfile
#
#             if respack.res.status_code == 200:
#                 logger.info(
#                     "temporary cache found: " + video_cache.get_cachefilename())
#                 logger.info(
#                     "response of video is not 206 Partial Content. cache will not work.")
#                 return respack
#
#             elif respack.res.status_code == 206:
# if respack.res.is_chunked():  # ないとは思うけど
#                     logger.info(
#                         "temporary cache found: " + video_cache.get_cachefilename())
#                     logger.info(
#                         "but response of video(206 Partial Content) is chunked. cache will not work.")
#                     del req.headers["Range"]
#                     server_sockfile.close()
#                     server_sockfile = None
#                     return proxtheta.utility.client.get_http_resource(
#                         (host, port), req)
#
# else:  # めでたくエコノミー回避
#                     if video_cache.exsists_in_filesystem():
#                         logger.info(
#                             "temporary cache found: " + video_cache.get_cachefilename())
#                         logger.info(
#                             "Partial download from " + str(video_cache.get_cachefilelen()) + " byte")
#                     else:
#                         logger.info(
#                             "no cache found: " + video_cache.get_cachefilename())
#                     ncr = NicoCachingReader(video_cache,
#                                             originalfile=respack.body_file,
#                                             length=complete_video_size,
#                                             complete_cache=complete_cache, logger=logger)
#                     respack.body_file = ncr
#                     respack.res.status_code = 200
#                     respack.res.reason_phrase = "OK"
#                     respack.res.headers[
#                         "Content-Length"] = str(complete_video_size)
#                     return respack
#
#             else:
#
#                 return respack
#         except:
#             safe_close(server_sockfile)
#
#
# ??video_numにマッチするファイルのリストを得る(lowでない)
# ローカルに完全な非エコノミーキャッシュファイルがあるなら:
# openして返す
# else(非エコノミーキャッシュファイルが中途半端なキャッシュなら、もしくはキャッシュがないなら):
# キャッシュの続きが非エコノミーでとれるなら(リクエストuriのクエリがlowで終わってるかどうかで判断):
# NicoCachingReaderを提供
# エコノミー動画しかとれないなら:
# ローカルに完全なエコノミーキャッシュファイルがあるなら:
# openして返す
# 中途半端なキャッシュしかない、もしくはキャッシュがないなら:
# NicoCachingReaderを提供
# #
#
#     @classmethod
#     def get_http_resource_with_localcache(cls, video_cache_getter, thumbinfo, option, xxx_todo_changeme1,
#                                           req,
#                                           server_sockfile=None,
#                                           nonproxy_camouflage=False,
#                                           complete_cache=False, logger=logger):
#         (host, port) = xxx_todo_changeme1
#         body_file = None
#         try:
# fixme!!!タイトル変わってるときの挙動は？
#             video_id = thumbinfo.video_id
#             title = thumbinfo.title
#             movie_type = thumbinfo.movie_type
#
#             video_cache = video_cache_getter.get(video_id, low=False)
#
#             video_cache.set_title(title)
#             if not video_cache.exsists_in_filesystem():
#                 video_cache.set_filename_extension(movie_type)
#
#             if video_cache.is_complete():
# 非エコノミーな完全キャッシュがあるとき
#                 return cls._get_http_resource_with_complete_localcache(
#                     video_cache, server_sockfile, logger)
#
#             else:
#                 if not req.query.endswith("low"):
# 非エコノミーな不完全なキャッシュがとれるとき(サーバによるエコノミー強制がかかってないとき)
#                     return cls._get_http_resource_with_tmp_localcache_and_server(video_cache,
# complete_video_size=
#                                                                                    int(
#                                                                                        thumbinfo.size_high),
#                                                                                    (host,
#                                                                                     port),
#                                                                                    req,
#                                                                                    server_sockfile,
#                                                                                    nonproxy_camouflage,
#                                                                                    complete_cache, logger)
#                 else:
# !!!このコードデジャブだからなんとかしたい
#                     video_cache = video_cache_getter.get(video_id, low=True)
#                     video_cache.set_title(title)
#                     if not video_cache.exsists_in_filesystem():
#                         video_cache.set_filename_extension(movie_type)
#
#                     if video_cache.is_complete():
# エコノミーな完全なキャッシュがある
#                         return cls._get_http_resource_with_complete_localcache(
#                             video_cache, server_sockfile, logger)
#                     else:
#                         return cls._get_http_resource_with_tmp_localcache_and_server(video_cache,
# complete_video_size=
#                                                                                        int(
#                                                                                            thumbinfo.size_low),
#                                                                                        (host,
#                                                                                         port),
#                                                                                        req,
#                                                                                        server_sockfile,
#                                                                                        nonproxy_camouflage,
#                                                                                        complete_cache, logger)
#
#         except:
#             safe_close(server_sockfile)
#             safe_close(body_file)
#             raise

    @property
    def videofilename(self):
        return self._video_cache.get_cachefilename()

    def __init__(self, video_cache, originalfile, length,
                 complete_cache=False, logger=logger):
        if 0:
            """arg type"""
            video_cache = VideoCache()

        self._video_cache = video_cache
        CachingReader.__init__(
            self, video_cache.get_cachefile(), originalfile, length, complete_cache, logger)

    def read(self, size=-1):
        self._logger.debug("NicoCachingReader.read(): %s", self.videofilename)
        return CachingReader.read(self, size=size)

    def close(self):

        if self._complete_cache:
            self._logger.info("continue caching: " + self.videofilename)

        CachingReader.close(self)

        # nicocache apiによって保存された時に名前が変わってるかもしれないからこうする
        # dirty!!! グローバル変数に依存
        # todo!!! キャッシュを開いたり閉じたりするロジック(つまりcreate_*関数とcloseメソッド)
        # をどっかに分離する
        self._video_cache = nicocache.video_cache_getter.get(
            self._video_cache.get_videoid(),
            self._video_cache.is_economy())

        if self._left_size == 0:
            # close()するまでハードディスクにかきこまれてないかもしれないので
            # read()内でself._left_size == 0をチェックするのではなく、ここでチェックしてログを残す
            self._video_cache.change_to_complete_cache()
            self._logger.info("cache completed: " + self.videofilename)
        else:
            self._logger.info("suspended: " + self.videofilename)

    def __del__(self):
        try:
            if not self._closed:
                self._logger.error(
                    "not correctly closed: " + self.videofilename)
                CachingReader.__del__(self)
        except Exception:
            pass


class Extension():

    def __init__(self, extension_name=None):
        self.name = extension_name

        self.request_filters = []
        self.request_filters_extend = []

        self.response_servers = []

        self.response_filters = []
        self.response_filters_extend = []


class NicoCache(object):

    """おそらくnicocache.pyが起動したら一つ出来るであろうシングルトン"""

    def __init__(self, **kwargs):
        """secondary_proxy_addr: ((host, port)のtuple, None)
            Noneの場合secondary proxyを通さない
            (host, port)が設定されればそこを経由する
        secondary_proxy_addr が Noneでないなら"""
        self.video_cache_getter = None
        self.secondary_proxy_addr = None
        self.nonproxy_camouflage = True
        self.complete_cache = False
        self.logger = logger

        self.__dict__.update(kwargs)

    def _get_http_resource_hook(self, req,
                                nonproxy_camouflage=None):
        """proxtheta.utility.client.get_http_resource()
        を呼び出す前の前処理、非プロクシ偽装
        (host, port)は__init__で設定されたセカンダリproxyを使うか、reqから推測される
        =Noneとなっているパラメータは、__init__で設定された値がデフォルトで使われる
        __init__でセカンダリproxyが設定されている場合と、されていない場合で
        nonproxy_camouflage=Trueのときの挙動が異なる
        後者の場合、GET http://host:8080/ ...はGET / ...となるが、前者だと変更されない
        どちらの場合もhop by hop ヘッダは削除される"""

        nonproxy_camouflage = (nonproxy_camouflage
                               if nonproxy_camouflage is not None
                               else self.nonproxy_camouflage)

        if self.secondary_proxy_addr:
            (host, port) = self.secondary_proxy_addr
        else:
            (host, port) = (req.host, req.port)

        if nonproxy_camouflage:
            req = deepcopy(req)
            httpmes.remove_hop_by_hop_header(req)
            if not self.secondary_proxy_addr:
                httpmes.remove_scheme_and_authority(req)

        return ((host, port), req)

    def get_http_resource(self, req, server_sockfile,
                          load_body=False,
                          nonproxy_camouflage=None):
        """proxtheta.utility.client.get_http_resource()
        のラッパーだが、(host, port)は__init__で設定されたセカンダリproxyを使うか、reqから推測される
        =Noneとなっているパラメータは、__init__で設定された値がデフォルトで使われる
        __init__でセカンダリproxyが設定されている場合と、されていない場合で
        nonproxy_camouflage=Trueのときの挙動が異なる
        後者の場合、GET http://host:8080/ ...はGET / ...となるが、前者だと変更されない
        どちらの場合もhop by hop ヘッダは削除される"""

        (host, port), req = self._get_http_resource_hook(req,
                                                         nonproxy_camouflage)

        return proxtheta.utility.client.get_http_resource(
            (host, port),
            req, server_sockfile,
            load_body,
            nonproxy_camouflage=False)  # 自前で処理するのでnonproxy_camouflageはFalse

    def _get_partial_http_resource(self,
                                   req,
                                   first_byte_pos,
                                   last_byte_pos=None,
                                   server_sockfile=None,
                                   load_body=False,
                                   nonproxy_camouflage=None):
        """nicocache.get_partial_http_resource()
        のラッパーだが、(host, port)は__init__で設定されたセカンダリproxyを使うか、reqから推測される
        =Noneとなっているパラメータは、__init__で設定された値がデフォルトで使われる
        __init__でセカンダリproxyが設定されている場合と、されていない場合で
        nonproxy_camouflage=Trueのときの挙動が異なる
        後者の場合、GET http://host:8080/ ...はGET / ...となるが、前者だと変更されない
        どちらの場合もhop by hop ヘッダは削除される"""
        (host, port), req = self._get_http_resource_hook(req,
                                                         nonproxy_camouflage)

        return get_partial_http_resource((host, port), req,
                                         first_byte_pos,
                                         last_byte_pos,
                                         server_sockfile,
                                         load_body,
                                         nonproxy_camouflage=False)
        # 自前で処理するのでnonproxy_camouflageはFalse

    @convert_upstream_error
    def simple_proxy_response_server(self, req, server_sockfile, info):
        host, port = req.host, req.port

        if is_request_to_this_server(
                host, port, info.this_server_address.port):
            return ResponsePack(httpmes.HTTP11Error((403, "Forbidden")))

        respack = self.get_http_resource(req, server_sockfile)

        self.logger.debug("%s: request: %s, "
                          "response: %s",
                          info.client_address,
                          req.get_request_uri(),
                          respack.res.get_start_line_str())

        return respack

    @convert_upstream_error
    def handle_video_request(self, req, server_sockfile, info, logger=None):
        logger = (logger if logger is not None else self.logger)
        video_cache_getter = self.video_cache_getter

        (host, port) = (req.host, req.port)

        if (req.host.startswith("smile-") and
                req.host.endswith(".nicovideo.jp") and
                req.path == "/smile"):  # 例えば http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688

            video_id = get_videoid_with_httpreq(None, req)
            video_cache = video_cache_getter.get(video_id, low=False)

            # video_cache.set_title("")

            if video_cache.is_complete():
                # 完全キャッシュがあるとき

                respack = NicoCachingReader.\
                    create_response_with_complete_localcache(video_cache)
                respack.server_sockfile = server_sockfile
                return respack
            else:
                # 完全キャッシュがないとき
                del req.headers["Accept-Encoding"]
                # http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
                if req.query.endswith("low"):
                    video_cache = video_cache_getter.get(video_id, low=True)
                    if video_cache.is_complete():
                        respack = NicoCachingReader.\
                            create_response_with_complete_localcache(
                                video_cache)
                        respack.server_sockfile = server_sockfile
                        return respack

                else:
                    video_cache = video_cache_getter.get(video_id, low=False)

                # video_cache.set_title("")

                respack = self._get_partial_http_resource(req,
                                                          first_byte_pos=video_cache.get_cachefilelen(),
                                                          last_byte_pos=None,
                                                          server_sockfile=server_sockfile)

                if respack.res.status_code == 200:
                    logger.warn(
                        "temporary cache found: " + video_cache.get_cachefilename())
                    logger.warn(
                        "response of video is not 206 Partial Content. cache will not work.")
                    return respack

                elif respack.res.status_code == 206 and respack.res.is_chunked():
                    logger.warn(
                        "temporary cache found: " + video_cache.get_cachefilename())
                    logger.warn(
                        "but response of video(206 Partial Content) is chunked. cache will not work.")
                    del req.headers["Content-Range"]
                    server_sockfile.close()
                    server_sockfile = None
                    return proxtheta.utility.client.get_http_resource(
                        (host, port), req)

                elif respack.res.status_code != 206:
                    return respack

                if not video_cache.exsists_in_filesystem():
                    content_type = respack.res.headers.get(
                        "Content-Type", None)
                    if content_type is None:
                        video_cache.set_filename_extension("unknown")
                    else:
                        filename_extension = guess_filename_extension(
                            content_type)
                        if filename_extension is None:
                            logger.warn("unknown mimetype: %s", content_type)
                            video_cache.set_filename_extension("unknown")
                        else:
                            video_cache.set_filename_extension(
                                filename_extension)

                complete_video_size_str = respack.res.headers["Content-Range"].\
                    split("/")[1]  # "Range: bytes: 30-50/100" => "100"
                if complete_video_size_str == "*":
                    raise NotImplemented(
                        "%s is not implemented response type\n"
                        "%s ", respack.res.headers["Content-Range"], respack.res)

                complete_video_size = int(complete_video_size_str)

                respack = NicoCachingReader.\
                    create_response_with_tmp_localcache_and_server(video_cache,
                                                                   respack,
                                                                   complete_video_size,
                                                                   self.complete_cache)
                respack.server_sockfile = server_sockfile
                return respack

        else:
            # ニコニコ動画の動画ファイルへのアクセスでないとき
            return ResponsePack(None, server_sockfile=server_sockfile)

nicocache = NicoCache()


class CONNECT_Handler(proxtheta.utility.server.ResponseServer):

    @staticmethod
    def accept(req, info):
        return req.method == "CONNECT"

    @staticmethod
    def serve(req, server_sockfile, info):
        logger.info(req.get_request_line_str() + " from " +
                    str((info.client_address.host, info.client_address.port)))
        logger.info("but cannot handle CONNECT(501 Not Implemented)")
        return ResponsePack(httpmes.HTTP11Error((501, "Not Implemented")),
                            server_sockfile=server_sockfile)


class ReqForThisServerHandler(proxtheta.utility.server.ResponseServer):

    @staticmethod
    def accept(req, info):
        return proxtheta.utility.server.\
            is_request_to_this_server(
                req.host, req.port, info.this_server_address.port)

    @staticmethod
    def serve(req, server_sockfile, info):
        if req.path == "/":
            res = httpmes.HTTPResponse.create(
                src="HTTP/1.1 200 OK\r\n", load_body=False)
            res.body = "nicocache.py"
            res.set_content_length()
            return ResponsePack(res, server_sockfile=server_sockfile)
        else:
            return ResponsePack(httpmes.HTTP11Error((404, "Not Found")), server_sockfile=server_sockfile)


class NicoCacheAPIHandler(proxtheta.utility.server.ResponseServer):

    """とりあえず saveだけ"""
    macher = re.compile("/watch/([^/]+)/(.+)")

    def __init__(self, video_cache_getter):

        self.video_cache_getter = video_cache_getter
        proxtheta.utility.server.ResponseServer.__init__(self)

    def accept(self, req, info):
        return (req.host == "www.nicovideo.jp" and
                bool(self.macher.match(req.path)))

    def serve(self, req, server_sockfile, info):
        """とりあえずsaveだけ"""
        m = self.macher.match(req.path)
        video_id = m.group(1)
        command = m.group(2)

        if command != "save":
            return None

        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))

        video_cache = self.video_cache_getter.get(video_id, low=False)

        thumbinfo = ThumbInfo(video_id)
        title = thumbinfo.title
        video_cache.set_title(title)
        res.body = ("NicoCacheAPI command successed: %s %s %s" %
                    (command, video_id,
                     video_cache.get_video_cache_filepath()))
        logger.info(res.body)
        res.set_content_length()

        return ResponsePack(res, server_sockfile=server_sockfile)


def load_extensions():
    extensions = []
    importer = pkgutil.get_importer("extensions")
    for i in importer.iter_modules():
        modname = i[0]
        mod = importlib.import_module("." + modname, "extensions")
        if hasattr(mod, "extension"):
            mod.extension.name = mod.extension.name or modname
            extensions.append(mod.extension)

    return extensions


def main(argv):
    argc = len(argv)
    if argc > 1 and ("debug" in argv):
        _logging.basicConfig(format="%(levelname)s:%(name)s: %(message)s")
        _logging.root.setLevel(_logging.DEBUG)
    else:
        _logging.basicConfig(format="%(message)s")
        _logging.root.setLevel(_logging.INFO)

    # todo!!!設定ファイルから読み込む
    import config
    port = config.listen_port
    recursive = True
    complete_cache = False
    if config.proxy_host:
        secondary_proxy_addr = core.common.Address(
            (config.proxy_host, config.proxy_port))
    else:
        secondary_proxy_addr = None
    nonproxy_camouflage = True

    cache_dir_path = "./cache"
    if not os.path.isdir(cache_dir_path):
        os.mkdir(cache_dir_path)

    logger.info("making video cache file path table")

    # ファクトリやらシングルトンやらの初期化
    nicocache_filesystem = NicoCacheFileSystem(cache_dir_path, recursive)
    video_cache_getter = VideoCacheGetter(nicocache_filesystem)

    logger.info("finish making video cache file path table")

    nicocache.video_cache_getter = video_cache_getter
    nicocache.secondary_proxy_addr = secondary_proxy_addr
    nicocache.nonproxy_camouflage = nonproxy_camouflage
    nicocache.complete_cache = complete_cache

    default_request_filters = []
    default_response_servers = [CONNECT_Handler(),
                                ReqForThisServerHandler(),
                                NicoCacheAPIHandler(video_cache_getter),
                                nicocache.handle_video_request,
                                nicocache.simple_proxy_response_server]
    default_response_filters = []

    # エクステンションの取り込み
    logger.info("load extensions")
    extensions = load_extensions()

    for extension in extensions:
        logger.info("loaded extension: %s", extension.name)

    request_filters = []
    response_servers = []
    response_filters = []

    for extension in extensions:
        request_filters.extend(extension.request_filters)
        response_servers.extend(extension.response_servers)
        response_filters.extend(extension.response_filters)

    request_filters.extend(default_request_filters)
    response_servers.extend(default_response_servers)
    response_filters.extend(default_response_filters)

    for extension in extensions:
        request_filters.extend(extension.request_filters_extend)
        response_filters.extend(extension.response_filters_extend)

    handler = proxtheta.utility.proxy.FilteringResponseServers(
        request_filters=request_filters,
        response_servers=response_servers,
        response_filters=response_filters)

    try:
        return proxtheta.server.run_multithread(handler, port=port)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt occurred. finish nococache.py.")
        return


if __name__ == "__main__":
    import sys

    main(sys.argv)
