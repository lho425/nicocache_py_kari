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
from libnicocache import VideoCacheInfo, VideoCache


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


from proxtheta.core import httpmes
from proxtheta import utility, core
import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server
from proxtheta.utility.common import safe_close
import time
import importlib
import pkgutil
import locale
import shutil
import libnicocache
from libnicocache.filecachetool import CachingReader
from libnicocache.utility import get_partial_http_resource
from libnicovideo import ThumbInfo
import weakref
logger = _logging.getLogger("nicocache.py")
# logger.setLevel(_logging.DEBUG)
logger.info("nicocache.py")

# proxtheta.utility.client.logger.setLevel(_logging.DEBUG)
# proxtheta.logger.setLevel(_logging.DEBUG)

# if 0:
#     """Type Define"""
#     logger = _logging.Logger()


def parse_nicovideo_request_query(query):
    """ニコニコ動画の動画サーバへのリクエストのクエリから、
    (query_name, video_num)を抽出して返す
    例)
    url: http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
    query: m=24992647.47688low
    (query_name, video_num, is_low) = ("m", "24992647", True)"""

    try:
        query_name, query_value = query.split('=')
        video_num = query_value.split('.')[0]
    except ValueError:
        raise RuntimeError(
            "get_videoid_with_httpreq(): error. query: " + query)

    return (query_name, video_num, query.endswith("low"))


def get_videotype_videonum_islow__with_req(req, video_type_cacher):
    query_name, video_num, is_low = parse_nicovideo_request_query(req.query)

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


def ___get_videoid_with_httpreq(video_type_cacher, req):
    """httpリクエストをヒントにしてvideo idを得る
    video_type_cacherから得られなかった時は推論も行う
    video_type_cacher = None のときは推論のみ行う"""
    # url: http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688low
    # query: m=24992647.47688low

    query_name, video_num, _ = parse_nicovideo_request_query(req.query)

    video_type = None
    if video_type_cacher is not None:
        video_type = video_type_cacher.get_videotype(video_num)

    if video_type is None:
        if query_name == "s":
            video_type = "nm"
        else:
            video_type = "sm"

    return video_type + video_num


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


class VideoCacheManager(object):

    """NicoCacheのプロセスが起動中、
    ファイルシステム上のキャッシュファイルに対応するVideoCacheオブジェクトは
    プロセス内に1つしか存在しないことを保証する
    """

    def __init__(self, FileSystemWrapperClass, VideoCacheClass=VideoCache):
        self._filesystem_wrapper = FileSystemWrapperClass()
        self._VideoCacheClass = VideoCacheClass

        # {video_cache_info: video_cache} なるdict
        self._weak_cacheobj_dict = weakref.WeakValueDictionary()

    def _get_cacheobj_from_weak_dick(self, video_cache):
        """video_cacheが弱参照辞書にあったらそれをかえす
        なかったら、video_cacheを弱参照辞書に登録してからvideo_cacheを返す"""
        # todo!!!ここの処理は複雑なので、デバッグログを残す
        video_cache_in_dick = self._weak_cacheobj_dict.get(
            video_cache.info, None)
        if video_cache_in_dick is None:
            self._weak_cacheobj_dict[video_cache.info] = video_cache
            video_cache_in_dick = video_cache

        return video_cache_in_dick

    def get(self, rootdir, video_num, **kwargs):
        cache_list = self.get_cache_list(rootdir, video_num, **kwargs)

        if not cache_list:
            return None

        else:
            return cache_list[0]

    def get_cache_list(self, rootdir, video_num, **kwargs):
        """与えられたvideo_num(部分的なvideo_cache_info)にマッチする
        ファイルシステム上のキャッシュファイルに対応するVideoCacheオブジェクトを返す(listで)
        マッチした数 == listの長さ

        ファイルシステム上のキャッシュファイルに対応するVideoCacheオブジェクトは
    プロセス内に1つしか存在しないことを保証する
        """
        video_cache_info_query = libnicocache.VideoCacheInfo.make_query(
            rootdir=rootdir, video_num=video_num, **kwargs)

        cache_list = self._VideoCacheClass.get_cache_list(
            self._filesystem_wrapper, video_cache_info_query)
        cache_list2 = []
        for video_cache in cache_list:
            cache_list2.append(self._get_cacheobj_from_weak_dick(video_cache))

        return cache_list2

    def lazy_create(self, video_cache_info):
        video_cache = self._VideoCacheClass(
            self._filesystem_wrapper, video_cache_info)

        return self._get_cacheobj_from_weak_dick(video_cache)

    def create(self, video_cache_info):
        video_cache = self.lazy_create(video_cache_info)
        video_cache.create()
        return video_cache


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


class VideoCacheOperator:

    """与えられた情報から得られる複数のキャッシュ候補から、
    実装されたロジックを基に適切なキャッシュを絞り込んだ上でCRUDを行う.
    このクラスを経由すると、クライアントが一つのvideo_numを与えると、
    VideoCacheOperatorが、なんかいい感じに、矛盾することなく
    ファイルシステム上のキャッシュファイルを操作してくれる.

    しかし、このクラスは、一つのvideo_numに対し、複数のファイルがあることを隠蔽しない.

    新しいキャッシュファイルをどこにどういう名前で作るか
    既に存在するキャッシュをどういう順番で探索し、どのキャッシュファイルを使うか
    等の挙動を決定する

    NicoCacheの挙動を左右する重要なクラス"""

    # ***設計思想***
    # using cache: とかPartial download fromとかのキャッシュに関するログはすべてこのクラスのスコープで行うようにする

    def __init__(self, video_cache_manager, rootdir, logger=logger):
        if 0:
            """type def"""
            self._video_cache_manager = VideoCacheManager()

        self._video_cache_manager = video_cache_manager

        self._rootdir = rootdir

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

    def save_cache(
            self, video_num, subdir, title=None, filename_extension=None,
            video_id=None):

        new_video_cache_info = VideoCacheInfo.create_for_update(
            filename_extension=filename_extension, title=title, subdir=subdir,
            video_id=video_id)

        query = VideoCacheInfo.make_query(rootdir=self._rootdir, subdir="")

        video_cache_list = self._get_video_cache_list(video_num)

        saved_cache_info_list = []
        for video_cache in video_cache_list:
            if query.match(video_cache.info):

                video_cache.update_cache_info(new_video_cache_info)
                saved_cache_info_list.append(video_cache.info)
                self._logger.info(
                    "save cache: %s", video_cache.info.make_cache_file_path())

        return saved_cache_info_list

    def _get_video_cache_list(self, video_num, rootdir=None):
        rootdir = rootdir or self._rootdir
        return self._video_cache_manager.get_cache_list(
            rootdir=rootdir, video_num=video_num)

    def _get_video_cache(self, video_num, low, rootdir=None):
        """見つからなければNoneを返す
        rootdir=Noneなら適当に決める"""
        rootdir = rootdir or self._rootdir
        return self._video_cache_manager.get(
            rootdir=rootdir, video_num=video_num, low=low)

    def _create_video_cache(
            self, video_num, low, default_video_type="sm", rootdir=None):
        """rootdir=Noneなら適当に決める"""
        rootdir = rootdir or self._rootdir
        video_cache_info = VideoCacheInfo.create(
            rootdir=self._rootdir, video_type=default_video_type,
            video_num=video_num, low=low, tmp=True)

        return self._video_cache_manager.create(video_cache_info)

    def _make_http_video_resource_with_comlete_localcache(
            self, video_cache, server_sockfile):

        self._logger.info(
            "using cache: %s", video_cache.info.make_cache_file_path())
        res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))
        cachefile_path = video_cache.info.make_cache_file_path()
        res.set_content_length(video_cache.get_size())
        mimetype = guess_mimetype(cachefile_path)
        if mimetype:
            res.headers["Content-Type"] = mimetype
        respack = ResponsePack(
            res, body_file=video_cache.open(readonly=True),
            server_sockfile=server_sockfile)
        return respack

    def _make_http_video_resource_with_tmp_localcache(
            self, video_cache, is_new_cache, req,
            http_resource_getter_func, server_sockfile):

        del req.headers["Accept-Encoding"]

        if is_new_cache:
            self._logger.info(
                "no cache found: %s",
                video_cache.info.make_cache_file_path())

            del req.headers["Range"]

        else:
            self._logger.info(
                "temporary cache found: %s",
                video_cache.info.make_cache_file_path())

            req.headers["Range"] = (
                # (例)Range: bytes=100-
                ''.join(("bytes=", str(video_cache.get_size()), "-")))

        # サーバから動画の続きを取ってくる
        # self._get_http_video_resourceを用意したのは苦肉の策
        # もっといい関数の切り分け方があるなら教えて to コードレビューする人
        (respack, complete_video_size,
         is_unexpected_response) = self._get_http_video_resource(
            video_cache, is_new_cache, req,
            http_resource_getter_func, server_sockfile)

        if is_unexpected_response:
            return respack

        if not is_new_cache:
            self._logger.info(
                "Partial download from %d byte", video_cache.get_size())

        respack.body_file = self._NicoCachingReader(
            video_cache, respack.body_file, complete_video_size)
        respack.res.status_code = 200
        respack.res.reason_phrase = "OK"
        respack.res.headers["Content-Length"] = str(complete_video_size)
        return respack

    def _get_http_video_resource(
            self, video_cache, is_new_cache, req,
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
                    "Overwrite cache file: %s",
                    video_cache.info.make_cache_file_path())

                video_cache.remove()
                video_cache.create()

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
        """reqを基にローカルのキャッシュからレスポンスを作ったり、
        http_resource_getter_funcを用いてニコニコ動画のサーバから動画を取ってきたりする
        def http_resource_getter_func(req, server_sockfile) => ResponsePack:
        """

        video_type, video_num, is_low = get_videotype_videonum_islow__with_req(
            req, None)
        video_cache = self._get_video_cache(video_num, is_low)

        if video_cache is None:
            # キャッシュがなく新規作成するとき
            video_cache = self._create_video_cache(
                video_num, is_low, video_type)
            return self._make_http_video_resource_with_tmp_localcache(
                video_cache, True, req,
                http_resource_getter_func, server_sockfile)

        elif video_cache.info.tmp:
            # 非完全なキャッシュがローカルにある場合
            return self._make_http_video_resource_with_tmp_localcache(
                video_cache, False, req,
                http_resource_getter_func, server_sockfile)

        else:
            # 完全なキャッシュがローカルにある場合
            respack = self._make_http_video_resource_with_comlete_localcache(
                video_cache, server_sockfile)

        return respack

    class _NicoCachingReader(CachingReader):

        @property
        def videofilename(self):
            return self._video_cache.info.make_cache_file_path()

        def __init__(self, video_cache, originalfile, length,
                     complete_cache=False, logger=logger):
            #             if 0:
            #                 """arg type"""
            #                 video_cache_info = libnicocache.VideoCacheInfo()

            self._video_cache = video_cache
            cachefile = self._video_cache.open()
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
        self.video_cache_operator = None
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
        video_cache_operator = self.video_cache_operator

        if (req.host.startswith("smile-") and
                req.host.endswith(".nicovideo.jp") and
                req.path == "/smile"):
            # 例えば http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688

            return video_cache_operator.make_http_video_resource(
                req,
                http_resource_getter_func=self.get_http_resource,
                server_sockfile=server_sockfile)

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

    def __init__(self, video_cache_operator):

        self.video_cache_operator = video_cache_operator
        proxtheta.utility.server.ResponseServer.__init__(self)

    def accept(self, req, info):
        return (req.host == "www.nicovideo.jp" and
                bool(self.macher.match(req.path)))

    def serve(self, req, server_sockfile, info):
        """とりあえずsaveだけ"""
        m = self.macher.match(req.path)
        watch_id = m.group(1)
        command = m.group(2)

        if command != "save":
            return None

        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))
        res.headers["Content-type"] = "text/plain ;charset=utf-8"

        thumbinfo = ThumbInfo(watch_id)

        saved_cache_info_list = self.video_cache_operator.save_cache(
            video_num=thumbinfo.video_id[2:],
            subdir="save",
            video_id=thumbinfo.video_id,
            title=thumbinfo.title,
            filename_extension=thumbinfo.movie_type)

        logs = []

        for cache_info in saved_cache_info_list:
            log = ("%s %s: %s\n" %
                   (command, thumbinfo.video_id,
                    cache_info.make_cache_file_path()))

            logs.append(log)

        res_body = "NicoCacheAPI command success: \n" + ''.join(logs)

        logger.info(res_body)
        res.body = res_body.decode(
            locale.getpreferredencoding()).encode("utf-8")
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


def main():
    import sys
    argv = sys.argv
    argc = len(argv)
    if argc > 1 and ("debug" in argv):
        _logging.basicConfig(format="%(levelname)s:%(name)s: %(message)s")
        _logging.root.setLevel(_logging.DEBUG)
    else:
        _logging.basicConfig(format="%(message)s")
        _logging.root.setLevel(_logging.INFO)
    logger.info(
        "guessed system default encoding: %s", locale.getpreferredencoding())
    logger.info(u"ニコキャッシュ.py(仮)")

    if not os.path.exists("./config.py"):
        shutil.copyfile("./config.py.template", "./config.py")

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

    save_dir_path = "./cache/save"
    if not os.path.isdir(save_dir_path):
        os.mkdir(save_dir_path)

    logger.info("making video cache file path table")

    # ファクトリやらシングルトンやらの初期化
    video_cache_manager = VideoCacheManager(
        libnicocache.pathutil.FileSystemWrapper)
    video_cache_operator = VideoCacheOperator(
        video_cache_manager, rootdir=cache_dir_path)

    logger.info("finish making video cache file path table")

    nicocache.video_cache_operator = video_cache_operator
    nicocache.secondary_proxy_addr = secondary_proxy_addr
    nicocache.nonproxy_camouflage = nonproxy_camouflage
    nicocache.complete_cache = complete_cache

    default_request_filters = []
    default_response_servers = [CONNECT_Handler(),
                                ReqForThisServerHandler(),
                                NicoCacheAPIHandler(video_cache_operator),
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
        return 0


if __name__ == "__main__":

    exit(main())
