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
import logging.handlers as _
import re
from copy import deepcopy
import importlib
import pkgutil
import locale
import shutil
import sys
from libnicocache.base import VideoCacheInfo
import errno


if sys.version_info.major == 2:
    from ConfigParser import RawConfigParser
else:
    from configparser import RawConfigParser


import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server

from proxtheta import core
from proxtheta.core import httpmes
from proxtheta.core.common import ResponsePack
from proxtheta.utility import proxy
from proxtheta.utility.proxy import convert_upstream_error
from proxtheta.utility.server import is_request_to_this_server


import libnicovideo.thumbinfo
import libnicocache.pathutil
from . import rewriter
from .urlapi import (
    ReqForThisServerHandler, NicoCacheAPIHandler, LocalURIHandler)

logger = _logging.getLogger("nicocache.py")
# logger.setLevel(_logging.DEBUG)


def applyVideoCacheGuessVideoTypeMixin(VideoCacheClass):
    class VideoCacheGuessVideoType(VideoCacheClass):

        def make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile):

            if not self.exists():

                video_type, _, _ = libnicocache.\
                    get_videotype_videonum_islow__with_req(
                        req, None)

                self.update_info(video_type=video_type)

            return VideoCacheClass.make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile)

    return VideoCacheGuessVideoType


def applyVideoCacheTitleMixin(VideoCacheClass):
    class VideoCacheWithTitle(VideoCacheClass):

        def make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile):
            raise NotImplementedError

    return VideoCacheWithTitle


class ConfigLoader(object):

    def __init__(self):
        self._config = None
        self._config_mtime = 0

        self._load_config()

    def _reload_config_if_modified(self):
        if self._config_mtime != os.path.getmtime("config.conf"):
            logger.info("reload config")
            self._load_config()

    def _load_config(self):
        self._config = RawConfigParser()
        self._config.read("config.conf")
        self._config_mtime = os.path.getmtime("config.conf")

    def get_config(
            self, section, key, defaults={}):

        self._reload_config_if_modified()

        if self._config.has_option(section, key):
            return self._config.get(section, key)
        else:
            return defaults[key]

    def get_config_int(
            self, section, key, defaults={}):

        self._reload_config_if_modified()

        if self._config.has_option(section, key):
            return self._config.getint(section, key)
        else:
            return defaults[key]

    def get_config_float(
            self, section, key, defaults={}):

        self._reload_config_if_modified()

        if self._config.has_option(section, key):
            return self._config.getfloat(section, key)
        else:
            return defaults[key]

    def get_config_bool(
            self, section, key, defaults={}):

        self._reload_config_if_modified()

        if self._config.has_option(section, key):
            return self._config.getboolean(section, key)
        else:
            return defaults[key]
#def get_config(key, value_type, default_value=None):

_config_loader = None

_default_global_config = {
    "listenPort": 8080,
    "proxyHost": "",
    "proxyPort": 8080,
    "touchCache": True,
    "cacheFolder": "",  # デフォルトは./cacheだが、それはこの項目を参照するときに""かどうかで判断する
    "autoSave": True,
    "autoRemoveLow": True,

    "allowFrom": "local",
}

# [S]のついているconfig項目
# _init_config()で一度だけ初期化される
_static_global_config = {
    "listenPort": None,
    "cacheFolder": None,
}


def _init_config():
    global _config_loader
    if not os.path.exists("./config.conf"):
        logger.info("config.conf not exists. generate config.conf.")
        shutil.copyfile(os.path.join(
            os.path.dirname(__file__), "config.conf.template"),
            "./config.conf")

    _config_loader = ConfigLoader()

    _static_global_config["listenPort"] = _config_loader.get_config_int(
        "global", "listenPort", _default_global_config)

    _static_global_config["cacheFolder"] = _config_loader.get_config(
        "global", "cacheFolder", _default_global_config)


def _get_config(type_string, section, key, defaults={}):
    if section == "global":
        defaults = _default_global_config

    if section == "global" and key in _static_global_config:
        return _static_global_config[key]

    if type_string:
        get_config_func_name = "get_config_" + type_string
    else:
        get_config_func_name = "get_config"

    return getattr(_config_loader, get_config_func_name)(
        section, key, defaults)


def get_config(section, key, defaults={}):
    return _get_config(None, section, key, defaults)


def get_config_int(section, key, defaults={}):
    return _get_config("int", section, key, defaults)


def get_config_float(section, key, defaults={}):
    return _get_config("float", section, key, defaults)


def get_config_bool(section, key, defaults={}):
    return _get_config("bool", section, key, defaults)


def applyVideoCacheAutoRemoveMixin(VideoCacheClass):

    class VideoCacheWithAutoRemoving(VideoCacheClass):

        """キャッシュ時に、動画ファイル数が上限を超えていたり、動画の合計サイズが上限を超えていたりしたときに、
        自動的に古いキャッシュを消す機能を加えるMixin
        現状では大量のキャッシュに対して、動画ファイル数や動画の合計サイズを高速で取得する方法と、
        古い動画ファイルを高速で見つける方法が思いつかないので、保留"""

        MixedClass = None

        def make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile):
            # config = load_config()  # 直にグローバル関数を呼んでいるので注意
            raise NotImplementedError

    return VideoCacheWithAutoRemoving


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


def applyVideoCacheTouchCacheMixin(VideoCacheClass):
    class VideoCacheTouchCache(VideoCacheClass):

        def _make_http_video_resource_with_comlete_localcache(
                self, server_sockfile, *args, **kwargs):
            if get_config_bool("global", "touchCache"):
                logger.debug("touch %s", self.info.make_cache_file_path())
                self._video_cache_file.touch()

            return VideoCacheClass.\
                _make_http_video_resource_with_comlete_localcache(
                    self, server_sockfile, *args, **kwargs)

    return VideoCacheTouchCache


def applyVideoCacheAutoSaveAndRemoveMixin(VideoCacheClass):
    class VideoCacheAutoSaveAndRemove(VideoCacheClass):

        """lowキャッシュがsaveされていた場合、非lowキャッシュも新規作成時に自動的にsaveする
        また、非lowキャッシュがcompleteしたときに、lowキャッシュがあったら消す"""

        # ほとんどがautoRemoveLowの為の処理
        # 一部autoSaveの為の処理

        def make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile):

            # 自分自身がlowキャッシュだったときは、completeした瞬間に消えてもらっては困る
            if self.info.low:
                low_cache = None

            else:
                low_cache = get_video_cache_manager().get_video_cache(
                    video_num=self.info.video_num, low=True)

                # ここはautoSaveの為の処理
                if (low_cache.exists() and not self.exists() and
                    low_cache.info.subdir.startswith("save") and
                    get_config_bool(
                        "global", "autoSave")):
                    # todo!!! saveがハードコードしているので、解消する
                    self.update_info(
                        **low_cache.info.replace(tmp=True, low=False).
                        _asdict())

                if (low_cache.exists() and (
                        low_cache.info.subdir.startswith("save") or
                        low_cache.info.subdir == ".")):
                    # 直下とsave以下にあるキャッシュ以外には変更を加えない
                    pass
                else:
                    low_cache = None

            respack = VideoCacheClass.make_http_video_resource(
                self, req, http_resource_getter_func, server_sockfile)

            if isinstance(respack.body_file, self._NicoCachingReader):
                respack.body_file._low_cache = low_cache

            return respack

        class _NicoCachingReader(VideoCacheClass._NicoCachingReader):

            def close(self):
                VideoCacheClass._NicoCachingReader.close(self)

                if (self._left_size == 0 and self._low_cache is not None and
                    get_config_bool(
                        "global", "autoRemoveLow")):
                    self._low_cache.remove()

    return VideoCacheAutoSaveAndRemove


VideoCache = applyVideoCacheTouchCacheMixin(
    applyVideoCacheGuessVideoTypeMixin(libnicocache.VideoCache))

VideoCache = applyVideoCacheAutoSaveAndRemoveMixin(VideoCache)


class NicoCache(object):

    """おそらくnicocache.pyが起動したら一つ出来るであろうシングルトン"""

    def __init__(self, **kwargs):

        self.video_cache_manager = None
        self.nonproxy_camouflage = True
        self.complete_cache = False
        self.logger = logger

        self.__dict__.update(kwargs)

    def _get_http_resource_hook(self, req,
                                nonproxy_camouflage=None):
        """proxtheta.utility.client.get_http_resource()
        を呼び出す前の前処理、非プロクシ偽装
        (host, port)はconfig.confで設定されたセカンダリproxyを使うか、reqから推測される
        =Noneとなっているパラメータは、__init__で設定された値がデフォルトで使われる
        __init__でセカンダリproxyが設定されている場合と、されていない場合で
        nonproxy_camouflage=Trueのときの挙動が異なる
        後者の場合、GET http://host:8080/ ...はGET / ...となるが、前者だと変更されない
        どちらの場合もhop by hop ヘッダは削除される"""
        secondary_proxy_host = get_config(
            "global", "proxyHost")
        if secondary_proxy_host:
            secondary_proxy_addr = core.common.Address(
                (secondary_proxy_host, get_config_int(
                    "global", "proxyPort")))
        else:
            secondary_proxy_addr = None
        del secondary_proxy_host

        nonproxy_camouflage = (nonproxy_camouflage
                               if nonproxy_camouflage is not None
                               else self.nonproxy_camouflage)

        if secondary_proxy_addr:
            (host, port) = secondary_proxy_addr
        else:
            (host, port) = (req.host, req.port)

        if nonproxy_camouflage:
            req = deepcopy(req)
            httpmes.remove_hop_by_hop_header(req)
            if not secondary_proxy_addr:
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

_nicocache = NicoCache()


def get_video_cache_manager():
    return _nicocache.video_cache_manager


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

_http_403forbidden_res = httpmes.HTTPResponse(("HTTP/1.1", 403, "Forbidden"),
                                              body="403 Forbidden")
_http_403forbidden_res.set_content_length()


class ForbiddenClientHandler(proxtheta.utility.server.ResponseServer):

    @staticmethod
    def accept(req, info):
        """弾く時はTrueを返す
        Trueを返すと403を返すserve()が呼ばれるので注意"""

        return not ForbiddenClientHandler.allow(req, info)

    @staticmethod
    def allow(req, info):
        allow_from = get_config("global", "allowFrom")

        if info.client_address.host.startswith("127."):
            # 127.*.*.*からは常に許可
            return True

        elif allow_from == "all":
            return True

        elif allow_from == "lanA":
            # 末尾の"."まで含めないと100.*.*.*とかもひっかかるので注意
            if info.client_address.host.startswith("10."):
                return True

        elif allow_from == "lanB":
            if info.client_address.host.startswith("172."):
                client = info.client_address.host

                return (16 <= int(client.split(".")[1]) <= 31)

        elif allow_from == "lanC" or allow_from == "lan":
            if info.client_address.host.startswith("192.168."):
                return True

        return False  # not allow

    @staticmethod
    def serve(req, server_sockfile, info):
        logger.info("Forbidden client: %s", info.client_address.host)
        return ResponsePack(_http_403forbidden_res, server_sockfile)


def load_extension_modules():
    extension_modules = []
    importer = pkgutil.get_importer("extensions")
    for i in importer.iter_modules():
        modname = i[0]

        if (os.path.exists("extensions/" + modname + ".pyc") and
                not os.path.exists("extensions/" + modname + ".py")):
                # extensions/mod.pyが存在しないとき
                # つまりpycしかないとき
                # extensionのロードをスキップ
            continue

        mod = importlib.import_module("." + modname, "extensions")
        extension_modules.append(mod)

    return extension_modules


def load_extensions(extension_modules):
    extensions = []
    for mod in extension_modules:
        if hasattr(mod, "get_extension"):
            extension = mod.get_extension()
            extension.name = extension.name or mod.__name__
            extensions.append(extension)
            logger.info("loaded extension: %s", extension.name)
    return extensions


def main():
    import sys
    argv = sys.argv
    argc = len(argv)
    if argc > 1 and ("debug" in argv):
        logger_format = "%(levelname)s:%(name)s: %(message)s"
        logger_level = _logging.DEBUG

    else:
        logger_format = "%(message)s"
        logger_level = _logging.INFO

    _logging.basicConfig(format=logger_format)
    _logging.root.setLevel(logger_level)

    try:
        os.remove("log.old.txt")
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

    try:
        os.rename("log.txt", "log.old.txt")
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

    try:
        os.remove("log.txt.1")
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

    rotating_log_handler = _logging.handlers.RotatingFileHandler(
        "log.txt", "w",
        # maxBytes=1GB
        maxBytes=1024 * 1024 * 1024, backupCount=1)

    _logging.captureWarnings(True)

    rotating_log_handler.setLevel(logger_level)
    rotating_log_handler.setFormatter(_logging.Formatter(logger_format))

    _logging.root.addHandler(rotating_log_handler)

    logger.info(
        "guessed system default encoding: %s", locale.getpreferredencoding())
    logger.info(u"ニコキャッシュ.py(仮)")

    logger.info("initializing")

    _init_config()

    port = get_config_int("global", "listenPort")
    complete_cache = False

    nonproxy_camouflage = True

    cache_dir_path = get_config(
        "global", "cacheFolder") or "./cache"

    if not os.path.isdir(cache_dir_path):
        os.makedirs(cache_dir_path)

    save_dir_path = os.path.join(cache_dir_path, "save")
    if not os.path.isdir(save_dir_path):
        os.makedirs(save_dir_path)

    extension_modules = load_extension_modules()

    # ファクトリやらシングルトンやらの初期化

    video_cache_manager = libnicocache.VideoCacheManager(
        cache_dir_path, VideoCache)

    video_info_rewriter = rewriter.Rewriter(video_cache_manager)

    _nicocache.video_cache_manager = video_cache_manager
    _nicocache.nonproxy_camouflage = nonproxy_camouflage
    _nicocache.complete_cache = complete_cache

    thumbinfo_server = libnicovideo.thumbinfo.CashngThumbInfoServer()

    default_request_filters = []
    default_response_servers = [CONNECT_Handler(),
                                ReqForThisServerHandler(),
                                NicoCacheAPIHandler(
                                    video_cache_manager, thumbinfo_server),
                                LocalURIHandler(),
                                _nicocache.handle_video_request,
                                _nicocache.simple_proxy_response_server]
    default_response_filters = [video_info_rewriter]

    logger.info("finish initializing")

    # エクステンションの取り込み
    logger.info("load extensions")
    extensions = load_extensions(extension_modules)

    request_filters = []
    response_servers = []
    response_filters = []

    response_servers.append(ForbiddenClientHandler())

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
