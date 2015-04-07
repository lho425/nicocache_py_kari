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


#     !!! あとで何処かへ移動されるはずのコード
#     def lazy_create(self, video_cache_info):
#         video_cache = self._VideoCacheFileClass(
#             self._filesystem_wrapper, video_cache_info)
#
#         return self._get_cachefile_from_weak_dick(video_cache)
#
#     def create(self, video_cache_info):
#         video_cache = self.lazy_create(video_cache_info)
#         video_cache.create()
#         return video_cache


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
    #     !!! あとでVideoCacheManagerに移るべき部分
    #     """与えられた情報から得られる複数のキャッシュ候補から、
    #     実装されたロジックを基に適切なキャッシュを絞り込んだ上でCRUDを行う.
    #     このクラスを経由すると、クライアントが一つのvideo_numを与えると、
    #     VideoCacheOperatorが、なんかいい感じに、矛盾することなく
    #     ファイルシステム上のキャッシュファイルを操作してくれる.
    #
    #     しかし、このクラスは、一つのvideo_numに対し、複数のファイルがあることを隠蔽しない.
    #
    #     新しいキャッシュファイルをどこにどういう名前で作るか
    #     既に存在するキャッシュをどういう順番で探索し、どのキャッシュファイルを使うか
    #     等の挙動を決定する
    #
    #     NicoCacheの挙動を左右する重要なクラス"""

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
        if 0:
            """type def"""
            self._video_cache_file = VideoCacheFileManager()

        self._video_cache_file = video_cache_file

        self._logger = logger

#     def rename_cache(
#             self, video_num, new_video_cache_info, low=None, rootdir=None):
#         video_cache = self._get_video_cache(video_num, low, rootdir)
#         if video_cache is None:
#             raise libnicocache.NoSuchCacheError("video_num: %s" % video_num)
#
#         video_cache.update_cache_info(new_video_cache_info)
#
#         return video_cache.info

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
        new_video_cache_info = self.info.replace(**kwargs)
        if self.info == new_video_cache_info:
            return "success"

        def command():
            if not self.exists():
                internal = "(internal)"
            else:
                internal = ""
            self._video_cache_file.update_cache_info(new_video_cache_info)
            self._logger.info(
                "rename cache%s: %s", internal,
                self._video_cache_file.info.make_cache_file_path())
        command.name = ("rename " +
                        self._video_cache_file.info.make_cache_file_path())

        status_str = self._execute_command(command)

        return status_str

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


#     !!! あとでVideoCacheManagerに移るべき部分

#
#     def _create_video_cache(
#             self, video_num, low, default_video_type="sm", rootdir=None):
#         """rootdir=Noneなら適当に決める"""
#         rootdir = rootdir or self._rootdir
#         video_cache_info = VideoCacheInfo.create(
#             rootdir=self._rootdir, video_type=default_video_type,
#             video_num=video_num, low=low, tmp=True)
#
#         return self._video_cache_manager.create(video_cache_info)
#
#     def get_video_cache_info_list(self, video_num, rootdir=None):
#         video_cache_list = self._get_video_cache_list(video_num, rootdir)
#
#         video_cache_info_list = [
#             video_cache.info for video_cache in video_cache_list]
#         return video_cache_info_list
#
#     def get_video_cache_info(self, video_num, low, rootdir=None):
#         video_cache = self._get_video_cache(video_num, low, rootdir)
#         if video_cache is None:
#             return None
#
#         return video_cache.info

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

    def __init__(
            self, video_cache_file_manager, filesystem_wrapper, rootdir,
            VideoCacheClass=VideoCache, logger=logger):
        self._video_cache_file_manager = video_cache_file_manager
        self._filesystem_wrapper = filesystem_wrapper
        self._rootdir = os.path.normpath(rootdir)
        self._VideoCacheClass = VideoCacheClass
        self._logger = logger

    def _make_video_cache(self, video_cache_info):
        return self._VideoCacheClass(
            self._video_cache_file_manager.get(
                video_cache_info), self._logger)

    def get_video_cache_pair(self, video_num):
        """return: (非エコノミーvideo_cache, エコノミーvideo_cache)
        存在しない場合はvideo_cacheが新規作成される(ファイルシステムへの反映は遅延される)"""
        video_cache_info_query = VideoCacheInfo.make_query(
            rootdir=self._rootdir, video_num=video_num)

        video_cache_list = self.get_video_cache_list(video_cache_info_query)

        video_cache_pair_dict = {False: None, True: None}
        for is_low in (False, True):
            for video_cache in video_cache_list:
                if video_cache.info.low == is_low:
                    video_cache_pair_dict[is_low] = video_cache
                    break

        for is_low in (False, True):
            if video_cache_pair_dict[is_low] is None:
                video_cache_info = VideoCacheInfo.create(
                    rootdir=self._rootdir, video_type="sm",
                    video_num=video_num, low=is_low, tmp=True)
                video_cache_pair_dict[is_low] = self._make_video_cache(
                    video_cache_info)

        return (video_cache_pair_dict[False], video_cache_pair_dict[True])

    def get_video_cache(self, video_num, low):
        """low: bool
        return: VideoCache
        存在しない場合はvideo_cacheが新規作成される(ファイルシステムへの反映は遅延される)
        """
        video_cache_info_query = VideoCacheInfo.make_query(
            rootdir=self._rootdir, video_num=video_num, low=low)
        video_cache_list = self.get_video_cache_list(video_cache_info_query)
        if not video_cache_list:
            video_cache_info = VideoCacheInfo.create(
                rootdir=self._rootdir, video_type="sm",
                video_num=video_num, low=low, tmp=True)
            video_cache = self._make_video_cache(video_cache_info)
            return video_cache

        return video_cache_list[0]

    def get_video_cache_list(self, video_cache_info_query, recursive=True):
        """video_cache_queryは要素にNoneを含められるVideoCacheInfo
        主にVideoCacheInfo.make_query()の戻り値
        video_cache_info_query.rootdir=Noneの場合、rootdirを適当に決める"""

        video_cache_info_list = []
        # rootdirは正規化されている
        rootdir = (video_cache_info_query.rootdir
                   if video_cache_info_query.rootdir is not None
                   else self._rootdir)
        walk_iterator = self._filesystem_wrapper.walk(
            rootdir, followlinks=True)
        if not recursive:
            walk_iterator = [next(walk_iterator)]

        for dirpath, _, filenames in walk_iterator:
            dirpath = os.path.normpath(dirpath)
            subdirpath = dirpath[(len(rootdir) + 1):]  # "rootdir/"の部分だけ取り除く
            for filename in filenames:

                try:
                    a_video_cache_info = VideoCacheInfo.create_from_filename(
                        filename, subdir=subdirpath, rootdir=rootdir)
                except VideoCacheInfoParameterError:
                    # キャッシュ以外のファイルがあると例外を投げられてしまう
                    continue

                if video_cache_info_query.match(a_video_cache_info):

                    video_cache_info_list.append(a_video_cache_info)

        video_cache_list = []
        for video_cache_info in video_cache_info_list:
            video_cache = self._make_video_cache(video_cache_info)
            video_cache_list.append(video_cache)

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
