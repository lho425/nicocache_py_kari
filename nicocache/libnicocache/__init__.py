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
from __future__ import absolute_import
from proxtheta.core.iowrapper import FileWrapper
from . import pathutil


"""ニコ動の動画キャッシュプロクシサーバを実装する上で、ファイルシステム上のキャッシュを管理するため道具をまとめたライブラリ"""

import os
import logging as _logging
import xml.etree.cElementTree as ElementTree
import StringIO
import re
import mimetypes
from copy import copy, deepcopy
import time
import importlib
import pkgutil
import locale
import shutil
import weakref
import threading

import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server

from proxtheta import utility, core
from proxtheta.core import httpmes, iowrapper
from proxtheta.core.common import ResponsePack
from proxtheta.utility.common import safe_close
from proxtheta.utility.proxy import convert_upstream_error
from proxtheta.utility.server import is_request_to_this_server


from .base import VideoCacheInfo, VideoCacheFile, VideoCacheInfoParameterError
from .filecachetool import CachingReader
from .utility import get_partial_http_resource


logger = _logging.getLogger(__name__)
# logger.setLevel(_logging.DEBUG)

# proxtheta.utility.client.logger.setLevel(_logging.DEBUG)
# proxtheta.logger.setLevel(_logging.DEBUG)

# if 0:
#     """Type Define"""
#     logger = _logging.Logger()

try:
    WindowsError
except NameError:
    class WindowsError(Exception):
        pass


def parse_nicovideo_request_query(query):
    """ニコニコ動画の動画サーバへのリクエストのクエリから、
    (query_name, video_num, hash_num, is_low)を抽出して返す
    hash_numはvideo_num.とlowの間にの後ろについてるよくわかんない数字
    例)
    url: http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
    query: m=24992647.47688low
    (query_name, video_num, hash_num, is_low) =
    ("m", "24992647", "47688", True)"""
    is_low = query.endswith("low")

    try:
        query_name, query_value = query.split('=')
        video_num, tail = query_value.split('.')
        # (例) tail = 47688low
        if is_low:
            hash_num = tail[:-3]
        else:
            hash_num = tail
    except (ValueError, IndexError):
        raise RuntimeError(
            "get_videoid_with_httpreq(): error. query: " + query)

    return (query_name, video_num, hash_num, is_low)


def unparse_nicovideo_request_query(query_name, video_num, hash_num, is_low):
    """parse_nicovideo_request_queryの逆"""
    is_low_str = "low" if is_low else ""

    query = ''.join((query_name, "=", video_num, ".", hash_num, is_low_str))
    return query


def get_videotype_videonum_islow__with_req(req, video_type_cacher):
    query_name, video_num, _, is_low = parse_nicovideo_request_query(req.query)

    video_type = None
    if video_type_cacher is not None:
        video_type = video_type_cacher.get_videotype(video_num)

    if video_type is None:
        video_type = guess_video_type_by_query_name(query_name)

    return video_type, video_num, is_low


def get_videonum_with_httpreq(req):

    return parse_nicovideo_request_query(req.query)[1]


def guess_video_type_by_query_name(query_name):
    if query_name == "s":
        video_type = "nm"
    else:
        video_type = "sm"

    return video_type


mimetypes.add_type("video/flv", ".flv")  # ここに書くのはなぁ


def guess_mimetype(path):
    """不明だった場合Noneを返す"""
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


class VideoCacheFileManager(object):

    """NicoCacheのプロセスが起動中、
    ファイルシステム上のキャッシュファイルに対応するVideoCacheFileオブジェクトは
    プロセス内に1つしか存在しないことを保証する
    """

    def __init__(self, filesystem_wrapper, VideoCacheFileClass=VideoCacheFile):
        self._filesystem_wrapper = filesystem_wrapper
        self._VideoCacheFileClass = VideoCacheFileClass

        # {video_cache_info: video_cache} なるdict
        self._weak_cacheobj_dict = weakref.WeakValueDictionary()

    def _get_cachefile_from_weak_dick(self, video_cache_file):
        """video_cache_fileが弱参照辞書にあったら、それをかえす
        なかったら、video_cache_fileを弱参照辞書に登録してからvideo_cache_fileを返す"""
        # todo!!!ここの処理は複雑なので、デバッグログを残す
        video_cache_file_in_dick = self._weak_cacheobj_dict.get(
            video_cache_file.info, None)
        if video_cache_file_in_dick is not None:
            if video_cache_file.info != video_cache_file_in_dick.info:
                # video_cache_in_dickが更新されていて、keyのinfoとvalue.infoが一致していない時は
                # 辞書を更新する
                self._weak_cacheobj_dict[
                    video_cache_file.info] = video_cache_file
                video_cache_file_in_dick = video_cache_file

        if video_cache_file_in_dick is None:
            # 辞書にない時は
            # 辞書を更新する
            self._weak_cacheobj_dict[video_cache_file.info] = video_cache_file
            video_cache_file_in_dick = video_cache_file

        return video_cache_file_in_dick

    def get(self, video_cache_info):
        video_cache = self._VideoCacheFileClass(
            self._filesystem_wrapper, video_cache_info)

        return self._get_cachefile_from_weak_dick(video_cache)


def get_partial_http_resource(
        req, get_http_resource_func, server_sockfile,
        first_byte_pos, last_byte_pos=None,):
    """Rengeヘッダをつけてからリクエストを送る"""

    if last_byte_pos is not None:
        req.headers["Range"] = (
            ''.join(("bytes=", str(first_byte_pos), "-", str(last_byte_pos))))
    else:
        req.headers["Range"] = (''.join(("bytes=", str(first_byte_pos), "-")))
    return get_http_resource_func(req, server_sockfile)

# アルゴリズム

# 新規cache
# log
# ファイル名設定して新規作成
# サーバからソケット取得
# ラップして返す

# tmp cache
# video_numからキャッシュファイル特定
# log
# サーバからソケット取得
# 異常があったらログをのこしてfallback
# ラップして返す

# complete cache
# video_numからキャッシュファイル特定
# open して返す


class VideoCache(object):

    # ***設計思想***
    # using cache: とかPartial download fromとかのキャッシュに関するログはすべてこのクラスのスコープで行うようにする

    class _OnCloseCommands(object):

        def __init__(self, logger=logger):

            self._lock = threading.Lock()
            self._commands = []
            self._logger = logger

        def append(self, command):
            self._commands.append(command)

        def execute(self):
            with self._lock:
                for command in self._commands:
                    self._logger.info("on close command: %s", command.name)
                    command()

                self._commands = []

    _lock_for_making_on_close_commands = threading.Lock()

    def __init__(self, video_cache_file, logger=logger):

        self._video_cache_file = video_cache_file

        self._logger = logger

    @property
    def info(self):
        return self._video_cache_file.info

    def _execute_command(self, command):
        """def command(): => any_type
        return: status_str
        commandが例外を投げる場合、video_cacheのon_close_commandsに予約される"""
        try:
            command()
        except WindowsError as e:
            # 32は使用中でアクセスできないエラー
            if e.winerror != 32:
                raise

            self._logger.info("command failed: %s", command.name)
            with VideoCache._lock_for_making_on_close_commands:
                if not hasattr(self._video_cache_file, "on_close_commands"):
                    self._video_cache_file.on_close_commands = \
                        self._OnCloseCommands(self._logger)

            self._video_cache_file.on_close_commands.append(command)

            return "reserved"

        return "success"

    def update_info(self, **kwargs):

        def command():
            new_video_cache_info = self.info.replace(**kwargs)

            self._video_cache_file.update_cache_info(new_video_cache_info)

            if not self.exists():
                # 内部的な処理のみのときはdebugログにする
                self._logger.debug(
                    "rename cache(internal): %s",
                    self._video_cache_file.info.make_cache_file_path())
            else:
                self._logger.info(
                    "rename cache: %s",
                    self._video_cache_file.info.make_cache_file_path())

        command.name = ("rename " +
                        self._video_cache_file.info.make_cache_file_path())

        status_str = self._execute_command(command)

        return status_str

    def create(self):

        self._video_cache_file.create()

        self._logger.info(
                "remove cache: %s", 
                self._video_cache_file.info.make_cache_file_path())

    def remove(self):

        def command():
            if not self.exists():
                internal = "(internal)"
            else:
                internal = ""
            self._video_cache_file.remove()
            self._logger.info(
                "remove cache%s: %s", internal,
                self._video_cache_file.info.make_cache_file_path())
        command.name = ("remove " +
                        self._video_cache_file.info.make_cache_file_path())

        status_str = self._execute_command(command)

        return status_str

    def exists(self):
        return self._video_cache_file.exists()

    def is_complete(self):
        return not self.info.tmp

    def _make_http_video_resource_with_comlete_localcache(
            self, server_sockfile):

        self._logger.info(
            "using cache: %s", self.info.make_cache_file_path())
        res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))
        cachefile_path = self.info.make_cache_file_path()
        res.set_content_length(self._video_cache_file.get_size())
        mimetype = guess_mimetype(cachefile_path)
        if mimetype:
            res.headers["Content-Type"] = mimetype
        respack = ResponsePack(
            res, body_file=self._CompleteCacheReader(self._video_cache_file),
            server_sockfile=server_sockfile)
        return respack

    def _make_http_video_resource_with_tmp_localcache(
            self, req,
            http_resource_getter_func, server_sockfile):

        del req.headers["Accept-Encoding"]

        is_new_cache = not self._video_cache_file.exists()

        if is_new_cache:
            self._logger.info(
                "no cache found: %s",
                self.info.make_cache_file_path())

            del req.headers["Range"]

        else:
            self._logger.info(
                "temporary cache found: %s",
                self.info.make_cache_file_path())

            req.headers["Range"] = (
                # (例)Range: bytes=100-
                ''.join(("bytes=",
                         str(self._video_cache_file.get_size()), "-")))

        # サーバから動画の続きを取ってくる
        # self._get_http_video_resourceを用意したのは苦肉の策
        # もっといい関数の切り分け方があるなら教えて to コードレビューする人
        (respack, complete_video_size,
         is_unexpected_response) = self._get_http_video_resource(
            is_new_cache, req,
            http_resource_getter_func, server_sockfile)

        if is_unexpected_response:
            return respack

        if not is_new_cache:
            self._logger.info(
                "Partial download from %d byte",
                self._video_cache_file.get_size())

        respack.body_file = self._NicoCachingReader(
            self._video_cache_file, respack.body_file, complete_video_size)
        respack.res.status_code = 200
        respack.res.reason_phrase = "OK"
        respack.res.headers["Content-Length"] = str(complete_video_size)
        return respack

    def _get_http_video_resource(
            self, is_new_cache, req,
            http_resource_getter_func, server_sockfile):
        """return (respack, complete_video_size, is_unexpected_response)"""

        respack = http_resource_getter_func(req, server_sockfile)

        # キャッシュを掛けられない普通じゃない レスポンスの為のガード節
        if not (respack.res.status_code == 200 or
                respack.res.status_code == 206):
            return respack, None, True

        if (respack.res.status_code == 206 and
                respack.res.is_chunked()):
            # ないとは思うけど
            self._logger.warn(
                "response of video(206 Partial Content) is chunked. "
                "cache will not work. (fall back).\n"
                "%s ", respack.res)
            del req.headers["Range"]
            respack.close_all()
            return http_resource_getter_func(req, None), None, True

        if respack.res.status_code == 200:
            complete_video_size = httpmes.get_transfer_length(respack.res, req)

            # 長さ不明でキャッシュを掛けられないレスポンスの為のガード節
            if not (isinstance(complete_video_size, int) and
                    complete_video_size >= 0):
                self._logger.warn(
                    "length of response is unknown. "
                    "cache will not work. (fall back).\n"
                    "%s ", respack.res)
                return respack, None, True

            # tmpキャッシュがあるからRangeヘッダ送ったのに200だった時の レスポンス
            # キャッシュを上書きして作りなおす
            if respack.res.status_code == 200 and not is_new_cache:
                self._logger.warn(
                    "response of video is not 206 Partial Content.\n"
                    "overwrite cache file: %s",
                    self.info.make_cache_file_path())

                self.remove()

        if respack.res.status_code == 206:

            complete_video_size_str = respack.res.headers["Content-Range"].\
                split("/")[1]  # "Range: bytes: 30-50/100" => "100"

            # 長さ不明でキャッシュを掛けられない レスポンスの為のガード節
            if complete_video_size_str == "*":
                self._logger.warn(
                    "not implemented response type: %s\n"
                    " cache will not work (fall back).\n"
                    "%s ", respack.res.headers["Content-Range"], respack.res)
                respack.close_all()
                return http_resource_getter_func(req, None), None, True

            complete_video_size = int(complete_video_size_str)

        return respack, complete_video_size, False

    def make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile):
        """reqを利用してローカルのキャッシュからレスポンスを作ったり、
        reqのURI中で指定されているvideo_numやlowの有無がselfと違っていた場合、
        また、そもそもニコニコ動画の動画サーバへの動画リクエストでない場合、動作はreqの内容に依る(チェックしない)
        基本的にVideoCacheManager経由で呼び出されるべき関数(クライアントが直接呼び出してはいけないとは言ってない)
        http_resource_getter_funcを用いてニコニコ動画のサーバから動画を取ってきたりする
        def http_resource_getter_func(req, server_sockfile) => ResponsePack:
        """

        if not self.info.tmp:
            # 完全なキャッシュがローカルにある場合
            return self._make_http_video_resource_with_comlete_localcache(
                server_sockfile)

        else:
            # 非完全なキャッシュがローカルにある場合
            # もしくはキャッシュがなく新規作成するとき
            return self._make_http_video_resource_with_tmp_localcache(
                req, http_resource_getter_func, server_sockfile)
# _NicoCachingReaderにはvideo_cacheとvideo_cache_fileどちらを渡すべきか？

    class _NicoCachingReader(CachingReader):

        @property
        def videofilename(self):
            return self._video_cache_file.info.make_cache_file_path()

        def __init__(self, video_cache_file, originalfile, length,
                     complete_cache=False, logger=logger):
            #             if 0:
            #                 """arg type"""
            #                 video_cache_info = libnicocache.VideoCacheInfo()

            self._video_cache_file = video_cache_file
            cachefile = self._video_cache_file.open(readonly=False)
            CachingReader.__init__(
                self, cachefile, originalfile, length, complete_cache, logger)

        def read(self, size=-1):
            self._logger.debug(
                "_NicoCachingReader.read(): %s", self.videofilename)
            return CachingReader.read(self, size=size)

        def close(self):

            if self._complete_cache:
                self._logger.info("continue caching: " + self.videofilename)

            CachingReader.close(self)

            # oh my god!
            # windowsだとopen中のファイルに対するremove/renameが失敗するからといってこれは…
            # もっとシンプルに出来ないんでしょうか
            if hasattr(self._video_cache_file, "on_close_commands"):
                # on_close_commandsは存在したら消えないので、時間差不整合は起きない
                self._video_cache_file.on_close_commands.execute()

            if self._left_size == 0:
                # close()するまでハードディスクにかきこまれてないかもしれないので
                # read()内でself._left_size == 0をチェックするのではなく、ここでチェックしてログを残す
                self._video_cache_file.change_to_complete_cache()
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

    class _CompleteCacheReader(iowrapper.FileWrapper):

        def __init__(self, video_cache_file):
            self._video_cache_file = video_cache_file
            FileWrapper.__init__(
                self, video_cache_file.open(readonly=True), close=True)

        def close(self):
            iowrapper.FileWrapper.close(self)

            if hasattr(self._video_cache_file, "on_close_commands"):
                # on_close_commandsは存在したら消えないので、時間差不整合は起きない
                self._video_cache_file.on_close_commands.execute()


class VideoCacheManager:

    """与えられた情報から得られる複数のキャッシュ候補から、
        実装されたロジックを基に適切なキャッシュを絞り込んだ上でCRUDを行う.
        このクラスを経由すると、クライアントが一つのvideo_numを与えると、
        VideoCacheManagerが、なんかいい感じに、矛盾することなく
        ファイルシステム上のキャッシュファイルを操作してくれる.

        新しいキャッシュファイルをどこにどういう名前で作るか
        既に存在するキャッシュをどういう順番で探索し、どのキャッシュファイルを使うか
        等の挙動を決定する

        NicoCacheの挙動を左右する重要なクラス

        現段階でこのクラスは、一つの(video_num, low)に対し、複数のファイルがあることを隠蔽しているかのように振舞っている

        需要があれば一つの(video_num, low)に対しすべてのキャッシュを返す機能を追加しても良いが、
        めんどくさいのでパス(難しくはないけど)

    """

    @classmethod
    def _applyVideoCacheFileMixin(cls, VideoCacheFileClass,
                                  get_dir_mtime_dict, getmtime):

        class VideoCacheFile(VideoCacheFileClass):

            @staticmethod
            def __update_dir_mtime_dict(video_cache_info):
                dirpath = os.path.dirname(
                    video_cache_info.make_cache_file_path())

                get_dir_mtime_dict()[dirpath] = getmtime(dirpath)

            # キャッシュが存在していない場合内部情報だけ書き換えるので、ディレクトリのmtimeは更新されない
            # しかし、人の手で更新されている可能性もあるので、キャッシュが存在している(していた)時のみ_update_dir_mtime_dictを実行する

            def update_cache_info(self, new_video_cache_info):
                # (video_num, low)を変えられてしまうとテーブルが崩壊するのでガードする

                old_info = self.info
                new_info = new_video_cache_info

                if (self.info.video_num, self.info.low) !=\
                        (new_info.video_num, new_info.low):
                    raise NotImplementedError(
                        "can not change video_num or low")

                VideoCacheFileClass.update_cache_info(
                    self, new_video_cache_info)

                if self.exists():
                    self.__update_dir_mtime_dict(old_info)
                    self.__update_dir_mtime_dict(new_info)

            def create(self):

                rv = VideoCacheFileClass.create(self)

                self.__update_dir_mtime_dict(self.info)

                return rv

            def remove(self):
                existed = self.exists()

                rv = VideoCacheFileClass.remove(self)

                if existed:
                    self.__update_dir_mtime_dict(self.info)

                return rv

            def open(self, *args, **kwargs):
                rv = VideoCacheFileClass.open(self, *args, **kwargs)

                self.__update_dir_mtime_dict(self.info)

                return rv

        return VideoCacheFile

    def __init__(
            self, rootdir,
            VideoCacheClass=VideoCache, logger=logger):

        filesystem_wrapper = pathutil.FileSystemWrapper()

        # 再代入してはいけない
        self._dir_mtime = {}

        self._video_cache_file_manager = VideoCacheFileManager(
            filesystem_wrapper,
            self._applyVideoCacheFileMixin(
                VideoCacheFile, lambda: self._dir_mtime, self._getmtime))

        self._filesystem_wrapper = filesystem_wrapper
        self._rootdir = os.path.normpath(rootdir)
        self._VideoCacheClass = VideoCacheClass
        self._logger = logger

        self._video_cache_file_table = {}

        self._construct_video_cache_file_table()

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

    def _construct_video_cache_file_table(self):

        self._logger.info("construct cache table")

        self._dir_mtime.clear()

        video_cache_file_list = []
        # rootdirは正規化されている
        rootdir = self._rootdir
        walk_iterator = self._filesystem_wrapper.walk(
            rootdir, followlinks=True)

        for dirpath, _, filenames in walk_iterator:
            dirpath = os.path.normpath(dirpath)
            self._dir_mtime[dirpath] = self._getmtime(dirpath)

            subdirpath = dirpath[(len(rootdir) + 1):]  # "rootdir/"の部分だけ取り除く
            for filename in filenames:

                try:
                    a_video_cache_info = VideoCacheInfo.create_from_filename(
                        filename, subdir=subdirpath, rootdir=rootdir)
                except VideoCacheInfoParameterError:
                    # キャッシュ以外のファイルがあると例外を投げられてしまう
                    continue

                self._logger.debug("cache file found: %s", a_video_cache_info)
                video_cache_file_list.append(
                    self._video_cache_file_manager.get(a_video_cache_info))

        for video_cache_file in video_cache_file_list:
            video_cache_id = (
                video_cache_file.info.video_num, video_cache_file.info.low)
            if video_cache_id not in self._video_cache_file_table:
                self._video_cache_file_table[video_cache_id] = video_cache_file

        self._logger.info("finish constructing cache table")

    def _update_video_cache_file_table(self):
        """キャッシュディレクトリに変更が加わっていた場合
        _construct_video_cache_file_table()が実行される"""

        for dirpath in self._dir_mtime:
            if self._dir_mtime[dirpath] != self._getmtime(dirpath):
                self._logger.info("cache directory changed. "
                                  "have to reconstruct cache table.")
                self._construct_video_cache_file_table()
                break

    def _make_video_cache(self, video_cache_file):
        return self._VideoCacheClass(video_cache_file, self._logger)

    def get_video_cache_pair(self, video_num):
        """return: (非エコノミーvideo_cache, エコノミーvideo_cache)
        存在しない場合はvideo_cacheが新規作成される(ファイルシステムへの反映は遅延される)"""
        return (self.get_video_cache(video_num, low=False),
                self.get_video_cache(video_num, low=True))

    def get_video_cache(self, video_num, low):
        """low: bool
        return: VideoCache
        存在しない場合はvideo_cacheが新規作成される(ファイルシステムへの反映は遅延される)
        """

        self._update_video_cache_file_table()

        video_cache_id = (video_num, low)

        # 実際に存在していないキャッシュならばテーブルから消す
        # それをしないと、例えば、cache/sub/にあるキャッシュを消して、
        # もう一度新規作成するときに、get_video_cacheが古いcachefileを返し、
        # cache/sub/に新規作成されてしまう

        # また、存在していないキャッシュをupdate_infoでcache/sub/に移動した場合、
        # get_video_cacheがcache/sub/にある事になっている(まだ実際には存在していない)キャッシュを返してしまう

        if (video_cache_id in self._video_cache_file_table and
                not self._video_cache_file_table[video_cache_id].exists()):

            del self._video_cache_file_table[video_cache_id]

        if video_cache_id not in self._video_cache_file_table:
            video_cache_info = VideoCacheInfo.create(
                rootdir=self._rootdir, video_type="sm",
                video_num=video_num, low=low, tmp=True)

            self._video_cache_file_table[video_cache_id] = \
                self._video_cache_file_manager.get(video_cache_info)

        video_cache_file = self._video_cache_file_table[video_cache_id]

        return self._make_video_cache(video_cache_file)

    def get_video_cache_list(self, video_cache_info_query):
        """video_cache_queryは要素にNoneを含められるVideoCacheInfo
        主にVideoCacheInfo.make_query()の戻り値
        video_cache_info_query.rootdir=Noneの場合、rootdirを適当に決める

        return: video_cache_list

        video_cache_listは(video_num, low)に対し、video_cacheが1つに定まっている
        """
        self._update_video_cache_file_table()

        video_cache_list = []

        for video_cache_file in self._video_cache_file_table.itervalues():

            if video_cache_info_query.match(video_cache_file.info):

                video_cache_list.append(
                    self._make_video_cache(video_cache_file))

        return video_cache_list

    def make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile):
        """reqを基にローカルのキャッシュからレスポンスを作ったり、
        http_resource_getter_funcを用いてニコニコ動画のサーバから動画を取ってきたりする
        def http_resource_getter_func(req, server_sockfile) => ResponsePack:"""
        _, video_num, low = get_videotype_videonum_islow__with_req(
            req, None)
        video_cache = self.get_video_cache(video_num, low)
        return video_cache.make_http_video_resource(
            req, http_resource_getter_func, server_sockfile)

    def _check_video_cache_id_in_table(self, video_cache_id):
        if video_cache_id not in self._video_cache_file_table:
            raise RuntimeError("invalid video_cache_id(not in table)"
                               ": %s" % video_cache_id)
