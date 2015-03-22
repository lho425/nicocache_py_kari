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
import os
import logging as _logging
import re
from copy import deepcopy
import importlib
import pkgutil
import locale
import shutil

import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server

from proxtheta import core
from proxtheta.core import httpmes
from proxtheta.core.common import ResponsePack
from proxtheta.utility.proxy import convert_upstream_error
from proxtheta.utility.server import is_request_to_this_server

import libnicovideo

import libnicocache.pathutil

logger = _logging.getLogger("nicocache.py")
# logger.setLevel(_logging.DEBUG)


class VideoCacheGuessVideoTypeMixin():
    MixedClass = None

    def make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile):
        video_type, _, _ = libnicocache.get_videotype_videonum_islow__with_req(
            req, None)

        self.update_info(video_type=video_type)

        return self.MixedClass.make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile)


def makeVideoCacheGuessVideoTypeMixin(VideoCacheClass):
    class VideoCache(
            VideoCacheGuessVideoTypeMixin, VideoCacheClass):

        MixedClass = VideoCacheClass

    return VideoCache

VideoCache = makeVideoCacheGuessVideoTypeMixin(libnicocache.VideoCache)


class VideoCacheTitleMixin():
    MixedClass = None

    def make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile):
        raise NotImplementedError


class NicoCacheConfig(object):

    def __init__(self, config):
        self.listen_port = getattr(config, "listen_port", 8080)
        # セカンダリプロクシ
        self.proxy_host = getattr(config, "proxy_host", "")
        self.proxy_port = getattr(config, "proxy_host", 8080)


def load_config():
    import config
    reload(config)
    return NicoCacheConfig(config)


class VideoCacheAutoRemoveMixin():

    """キャッシュ時に、動画ファイル数が上限を超えていたり、動画の合計サイズが上限を超えていたりしたときに、
    自動的に古いキャッシュを消す機能を加えるMixin
    現状では大量のキャッシュに対して、動画ファイル数や動画の合計サイズを高速で取得する方法と、
    古い動画ファイルを高速で見つける方法が思いつかないので、保留"""

    MixedClass = None

    def make_http_video_resource(
            self, req, http_resource_getter_func, server_sockfile):
        config = load_config()  # 直にグローバル関数を呼んでいるので注意
        raise NotImplementedError


class Extension(object):
    __slots__ = ("name",
                 "request_filter",
                 "response_filter",
                 "response_server", )

    def __init__(self, extension_name=None):
        self.name = extension_name

        self.request_filter = None
        self.response_filter = None

        self.response_server = None


class NicoCache(object):

    """おそらくnicocache.pyが起動したら一つ出来るであろうシングルトン"""

    def __init__(self, **kwargs):
        """secondary_proxy_addr: ((host, port)のtuple, None)
            Noneの場合secondary proxyを通さない
            (host, port)が設定されればそこを経由する
        secondary_proxy_addr が Noneでないなら"""
        self.video_cache_manager = None
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
        video_cache_manager = self.video_cache_manager

        if (req.host.startswith("smile-") and
                req.host.endswith(".nicovideo.jp") and
                req.path == "/smile"):
            # 例えば http://smile-fnl21.nicovideo.jp/smile?m=24992647.47688

            return video_cache_manager.make_http_video_resource(
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

    def __init__(self, video_cache_manager):

        self.video_cache_manager = video_cache_manager
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

        thumbinfo = libnicovideo.ThumbInfo(watch_id)

        video_cache_pair = self.video_cache_manager.get_video_cache_pair(
            thumbinfo.video_id[2:])
        logs = []
        for video_cache in video_cache_pair:
            if video_cache.exists():
                status_str = video_cache.update_info(
                    video_id=thumbinfo.video_id,
                    title=thumbinfo.title,
                    filename_extension=thumbinfo.movie_type,
                    subdir="save")
                log = ("%s: %s %s\n" %
                       (status_str, command,
                        video_cache.info.make_cache_file_path()))
                logs.append(log)

        res_body = "NicoCacheAPI command results: \n" + ''.join(logs)

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
        shutil.copyfile(os.path.join(
            os.path.dirname(__file__), "config.py.template"), "./config.py")

    config = load_config()
    port = config.listen_port
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

    logger.info("initializing")

    # ファクトリやらシングルトンやらの初期化
    filesystem_wrapper = libnicocache.pathutil.FileSystemWrapper()
    video_cache_file_manager = libnicocache.VideoCacheFileManager(
        filesystem_wrapper, libnicocache.VideoCacheFile)

    video_cache_manager = libnicocache.VideoCacheManager(
        video_cache_file_manager, filesystem_wrapper,
        cache_dir_path, VideoCache)

    video_info_rewriter = libnicovideo.videoinforewriter.Rewriter()

    nicocache.video_cache_manager = video_cache_manager
    nicocache.secondary_proxy_addr = secondary_proxy_addr
    nicocache.nonproxy_camouflage = nonproxy_camouflage
    nicocache.complete_cache = complete_cache

    thumbinfo_server = libnicovideo.thumbinfo.CashngThumbInfoServer()

    default_request_filters = []
    default_response_servers = [CONNECT_Handler(),
                                ReqForThisServerHandler(),
                                NicoCacheAPIHandler(
                                    video_cache_manager, thumbinfo_server),
                                nicocache.handle_video_request,
                                nicocache.simple_proxy_response_server]
    default_response_filters = [video_info_rewriter]

    logger.info("finish initializing")

    # エクステンションの取り込み
    logger.info("load extensions")
    extensions = load_extensions()

    for extension in extensions:
        logger.info("loaded extension: %s", extension.name)

    request_filters = []
    response_servers = []
    response_filters = []

    for extension in extensions:
        if extension.request_filter:
            request_filters.append(extension.request_filter)
        if extension.response_filter:
            response_filters.append(extension.response_filter)
        if extension.response_server:
            response_servers.append(extension.response_server)

    request_filters.extend(default_request_filters)
    response_filters.extend(default_response_filters)
    response_servers.extend(default_response_servers)

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
