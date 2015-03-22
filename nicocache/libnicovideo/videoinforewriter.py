# -*- coding: utf-8 -

"""ニコ動のwatchページ(というかプレイヤー)は、動画を得るための情報をなんらかの方法で得ている
このモジュールは、プレイヤーとニコニコのサーバの間に割り込んで様々なフックを掛けるためのインターフェース及び実装を提供する"""
import logging as _logging
from xml.etree import ElementTree
from xml.sax.saxutils import escape, unescape
import urllib

from proxtheta.utility import common
from proxtheta.utility.client import get_http_resource
from proxtheta.utility.proxy import ResponseFilter

from proxtheta.server import ResponsePack
import re
import json
import urlparse

logger = _logging.getLogger(__name__)


class RewriterAbstructBase(ResponseFilter):

    def accept(self, res, req, info):
        return self.is_videoinfo_request(req)

    @staticmethod
    def load_body(res, req, info):
        return True

    def filtering(self, res, req, info):
        return self.rewrite(res, req)

    def is_videoinfo_request(self, req):
        if req.method == "HEAD":
            return False

        return self._is_videoinfo_request(req)

    def rewrite(self, res, req):

        hooked_content = self._rewrite(res.body, req, res)

        res.body = hooked_content
        res.set_content_length()
        return res

    def _is_videoinfo_request(self, req):
        """実装しろ(boolを返せ)"""
        pass

    def _rewrite(self, content, req, res):
        """実装しろ(書き換えたcontentをbytes型で返せ、_rewrite_implを呼べ)"""
        pass

    def _rewrite_main(self, *args):
        """実装しろ(なんか書き換えるべきデータが渡されるから書き換えてreturnしろ)"""
        return args


def print_dict(dct, logger):
    logger.info("{")
    for k, v in dct.iteritems():
        if isinstance(v, dict):
            logger.info("%s:", k)
            print_dict(v, logger)
        else:
            logger.info("%s: %s", k, v)
    logger.info("}")


class GinzaRewriter(RewriterAbstructBase):
    req_path_macher = re.compile("/+watch/+[^/]+/*$")
    # 頑張ってニコキャッシュPyのAPIが引っかからないようにする
    macher = re.compile(
        """(.*<div id="watchAPIDataContainer" style="display:none">)"""
        """(.*?)(</div>.*)""", re.DOTALL)
    # re.DOTALLがないと'.'が改行にマッチしない

    def _is_videoinfo_request(self, req):
        return (req.host.startswith("www.nicovideo.jp") and
                self.req_path_macher.match(req.path))

    def _rewrite(self, content, req, res):
        escaped_json = bool()

        try:
            if res.headers.get("Content-Type").\
                    startswith("application/json"):
                escaped_json = False
                watch_api_data_container = content

            else:
                escaped_json = True
                m = self.macher.match(content)
                watch_api_data_container = m.group(2)
                # エスケープされたjson文字列のエスケープを解く
                watch_api_data_container = unescape(
                    watch_api_data_container, {"&quot;": '"'})
            # json文字列をdictにする
            watch_api_data_dict = json.loads(watch_api_data_container)

            # 動画(mp4等)のURLを得るにはさらにURLエンコードを解く必要がある(=とか%がエンコードされている)
            flvinfo = watch_api_data_dict["flashvars"]["flvInfo"]
            # URLエンコードを解く、そうすると値がURLエンコードされたクエリ文字列がでてくる
            # nickname=%E2%98%86&param=... <=こんな感じの
            # 通常のURLにおけるクエリと同じ
            flvinfo_unquote = urllib.unquote(flvinfo)

            # URLのクエリをdictにする
            flvinfo_dict = urlparse.parse_qs(flvinfo_unquote)
            # ここまでくれば好き勝手いじれるでしょう
            watch_api_data_dict, flvinfo_dict = self._rewrite_main(
                watch_api_data_dict, flvinfo_dict)

            logger.info("unquote 1 + urlparse.parse_qs")
            print_dict(flvinfo_dict, logger)

            watch_api_data_container = json.dumps(watch_api_data_dict)

            if not escaped_json:
                return watch_api_data_container
            else:
                # htmlにjsonが埋め込まれていたので、ちゃんと戻してあげる
                watch_api_data_container = escape(
                    watch_api_data_container, {'"': "&quot;"})
                return ''.join(
                    (m.group(1), watch_api_data_container, m.group(3)))

        except Exception as e:
            logger.exception("error occurred, fallback.\n%s", e)
            return content


Rewriter = GinzaRewriter
