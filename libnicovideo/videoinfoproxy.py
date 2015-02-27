# -*- coding: utf-8 -

"""ニコ動のwatchページ(というかプレイヤー)は、動画を得るための情報をなんらかの方法で得ている
このモジュールは、プレイヤーとニコニコのサーバの間に割り込んで様々なフックを掛けるためのインターフェース及び実装を提供する"""
from proxtheta.utility.client import get_http_resource
import gzip
import zlib


class ProxyAbstructBase(object):

    def __init__(self, logger, nonproxy_camouflage=True):
        self._logger = logger.getChild("Nico Video Info Proxy")
        self._nonproxy_camouflage = nonproxy_camouflage

    def is_videoinfo_request(self, req):
        if req.method == "HEAD":
            return False

        return self._impl__is_videoinfo_request(req)

    def serve_response_pack(self, req, server_sockfile, *args, **kwargs):
        respack = get_http_resource((req.host, req.port), req, server_sockfile,
                                    load_body=False,
                                    nonproxy_camouflage=self._nonproxy_camouflage)

        if respack.res.status_code != 200:
            return respack

        content = None
        # see rfc2616 3.5, 14.11
        content_encoding = respack.res.headers.get("Content-Encoding", "")
        try:
            if content_encoding == "gzip" or content_encoding == "x-gzip":

                with gzip.GzipFile(fileobj=respack.body_file) as f:
                    content = f.read()

            elif content_encoding == "deflate":

                ziped_content = respack.body_file.read(
                    respack.res.get_content_length())
                content = zlib.decompress(ziped_content)

            elif content_encoding == "" or content_encoding == "identity":

                content = respack.body_file.read(
                    respack.res.get_content_length())

            else:
                self._logger.warning(
                    "compress encoding we cannot handle: %s", content_encoding)
                return respack

        except:
            respack.close()
            raise

        del respack.res.headers["Content-Encoding"]
        respack.body_file.close()
        respack.body_file = None

        hooked_content = self._impl__hook_videoinfo(content, req, respack.res)

        respack.res.body = hooked_content
        respack.res.set_content_length()

        return respack

    def _impl__is_videoinfo_request(self, req):
        """実装しろ(boolを返せ)"""
        pass

    def _impl__hook_videoinfo(self, content, req, res):
        """実装しろ(strを返せ)"""
        pass
