# -*- coding: utf-8 -
from __future__ import absolute_import
import os
import logging as _logging
import re
from libnicocache.base import VideoCacheInfo


import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility.server

from proxtheta import core
from proxtheta.core import httpmes
from proxtheta.core.common import ResponsePack
from proxtheta.utility import proxy
from proxtheta.utility.proxy import convert_upstream_error
from proxtheta.utility.server import is_request_to_this_server


logger = _logging.getLogger(__name__)


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

        elif req.path == "/log.txt":
            respack = ReqForThisServerHandler.serve_log()
            respack.server_sockfile = server_sockfile
            return respack

        else:
            return ResponsePack(httpmes.HTTP11Error((404, "Not Found")), server_sockfile=server_sockfile)

    @staticmethod
    def serve_log():
        res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"), body=None)
        res.set_content_length(os.path.getsize("log.txt"))
        return ResponsePack(res, body_file=open("log.txt", "rb"))


class NicoCacheAPIHandler(proxtheta.utility.server.ResponseServer):

    """とりあえず save unsave removeだけ"""
    pattern = re.compile("/watch/(?P<watch_id>[^/]+)/(?P<command>.+)")

    def __init__(self, video_cache_manager, thimbinfo_server):

        self.video_cache_manager = video_cache_manager
        self._thimbinfo_server = thimbinfo_server
        proxtheta.utility.server.ResponseServer.__init__(self)

    def accept(self, req, info):
        return (req.host == "www.nicovideo.jp" and
                bool(self.pattern.match(req.path)))

    def serve(self, req, server_sockfile, info):
        match = self.pattern.match(req.path)
        watch_id = match.group("watch_id")
        command = match.group("command")

        res = httpmes.HTTPResponse(
            ("HTTP/1.1", 200, "OK"))
        res.headers["Content-type"] = "text/plain ;charset=utf-8"

        if hasattr(self, command):
            logs = getattr(self, command)(watch_id)
        else:
            return None

        res_body = "NicoCacheAPI command results: \n" + ''.join(logs)

        logger.info(res_body)

        # !!! あまりよろしくない
        # VideoCacheInfoをunicode化したほうがよいかと
        if isinstance(res_body, unicode):
            res.body = res_body.encode("utf-8")
        else:
            res.body = res_body

        res.set_content_length()

        return ResponsePack(res, server_sockfile=server_sockfile)

    def save(self, watch_id):
        thumbinfo = self._thimbinfo_server.get(watch_id)
        video_num = thumbinfo.video_id[2:]
        video_cache_pair = self.video_cache_manager.get_video_cache_pair(
            video_num)
        logs = []

        if not filter(lambda cache: cache.exists(), video_cache_pair):
            # キャッシュがまだ存在していない場合は
            # 非エコノミーの大きさ0のキャッシュを作る
            video_cache_pair[0].create()

            

        # dirty!!! 以下のforループが各コマンドで殆どコピペなのをなんとかする
        for video_cache in video_cache_pair:
            if (video_cache.exists() and
                video_cache.info.subdir == os.path.normpath("")):

                status_str = video_cache.update_info(
                    video_id=thumbinfo.video_id,
                    title=thumbinfo.title,
                    filename_extension=thumbinfo.movie_type,
                    subdir="save")
                log = "%s: %s %s\n" % (status_str, "save",
                                       video_cache.info.make_cache_file_path())
                logs.append(log)

        return logs

    def unsave(self, watch_id):
        thumbinfo = self._thimbinfo_server.get(watch_id)
        video_num = thumbinfo.video_id[2:]
        video_cache_pair = self.video_cache_manager.get_video_cache_pair(
            video_num)
        logs = []
        for video_cache in video_cache_pair:
            if (video_cache.exists() and
                    video_cache.info.subdir == os.path.normpath("save")):

                status_str = video_cache.update_info(
                    video_id=thumbinfo.video_id,
                    title="",
                    filename_extension="",
                    subdir="")
                log = "%s: %s %s\n" % (status_str, "unsave",
                                       video_cache.info.make_cache_file_path())
                logs.append(log)

        return logs

    def remove(self, watch_id):
        thumbinfo = self._thimbinfo_server.get(watch_id)
        video_num = thumbinfo.video_id[2:]
        video_cache_pair = self.video_cache_manager.get_video_cache_pair(
            video_num)
        logs = []
        for video_cache in video_cache_pair:
            if (video_cache.exists() and
                    video_cache.info.subdir == os.path.normpath("")):

                status_str = video_cache.remove()
                log = "%s: %s %s\n" % (status_str, "remove",
                                       video_cache.info.make_cache_file_path())
                logs.append(log)

        return logs


class LocalURIHandler(proxy.ResponseServer):

    """http://www.nicovideo.jp/local/*
    を取り扱う.
    (NicoCache_Py.pyがあるディレクトリ)/local/にあるファイルを転送する"""

    @staticmethod
    def accept(req, info):
        return (req.host == "www.nicovideo.jp" and
                req.path.startswith("/local"))

    @staticmethod
    def serve(req, server_sockfile, info):
        path = "." + req.path
        logger.debug("local file request: %s", path)
        if not os.path.isfile(path):
            res = httpmes.HTTP11Error((404, "Not Found"))
            return ResponsePack(res, server_sockfile=server_sockfile)

        size = os.path.getsize(path)

        res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"), body=None)
        res.set_content_length(size)

        return ResponsePack(res, body_file=open(path, "rb"),
                            server_sockfile=server_sockfile)
