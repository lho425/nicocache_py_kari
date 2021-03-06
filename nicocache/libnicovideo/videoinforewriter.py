# -*- coding: utf-8 -

"""ニコ動のwatchページ(というかプレイヤー)は、動画を得るための情報をなんらかの方法で得ている
このモジュールは、プレイヤーとニコニコのサーバの間に割り込んで様々なフックを掛けるためのインターフェース及び実装を提供する"""
import logging as _logging
from xml.etree import ElementTree
from xml.sax.saxutils import escape, unescape
import urllib
import re
import json
import urlparse
from pprint import pprint
from proxtheta.utility import common
from proxtheta.utility.client import get_http_resource
from proxtheta.utility.proxy import ResponseFilter

from proxtheta.server import ResponsePack

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
        """実装しろ(書き換えたcontentをbytes型で返せ、_rewrite_mainを呼べ)"""
        pass

    def _rewrite_main(self, *args):
        """実装しろ(なんか書き換えるべきデータが渡されるから書き換えてreturnしろ)"""
        return args


def dict_to_str_list(a_dict, a_list=None, indent_level=0):
    a_list = a_list or []
    # a_list.append("    " * indent_level)
    a_list.append("{\n")
    for k, v in a_dict.iteritems():
        a_list.append("    " * (indent_level + 1))
        if isinstance(v, dict):
            a_list.append("%s: " % k)
            dict_to_str_list(v, a_list, indent_level + 1)
        else:
            a_list.append("%s: %s\n" % (k, v))
    a_list.append("    " * indent_level)
    a_list.append("}\n")
    return a_list


def print_dict(a_dict, print_func):
    """logger_funcにはlogger.info等を渡してください"""
    print_func(''.join(dict_to_str_list(a_dict)))


class GinzaRewriter(RewriterAbstructBase):
    # 頑張ってニコキャッシュPyのAPIが引っかからないようにする
    req_path_pattern = re.compile("/+watch/+[^/]+/*$")

    # re.DOTALLがないと'.'が改行にマッチしない
    watchAPIDataContainer_pattern = re.compile(
        """(?P<head>.*<div id="watchAPIDataContainer" style="display:none">)"""
        """(?P<watch_api_data>.*?)(?P<tail></div>.*)""", re.DOTALL)

    def _is_videoinfo_request(self, req):
        return (req.host.startswith("www.nicovideo.jp") and
                self.req_path_pattern.match(req.path))

    def _rewrite(self, content, req, res):
        escaped_json = bool()

        try:
            if res.headers.get("Content-Type").\
                    startswith("application/json"):
                escaped_json = False
                watch_api_data = content

            else:
                escaped_json = True
                match = self.watchAPIDataContainer_pattern.match(content)
                if not match:
                    # Ginza player ではないので処理をやめる
                    return content
                watch_api_data = match.group("watch_api_data")
                # エスケープされたjson文字列のエスケープを解く
                watch_api_data = unescape(
                    watch_api_data, {"&quot;": '"'})
            # json文字列をdictにする
            watch_api_data_dict = json.loads(watch_api_data)

            if not "flashvars" in watch_api_data_dict:
                # Ginza player ではないので処理をやめる
                return content

            # 動画(mp4等)のURLを得るにはさらにURLエンコードを解く必要がある(=とか%がエンコードされている)
            flvinfo = watch_api_data_dict["flashvars"]["flvInfo"]
            # URLエンコードを解く、そうすると値がURLエンコードされたクエリ文字列がでてくる
            # nickname=%E2%98%86&param=... <=こんな感じの
            # 通常のURLにおけるクエリと同じ
            flvinfo_query_str = urllib.unquote(flvinfo)

            # URLのクエリをdictにする
            flvinfo_dict = urlparse.parse_qs(str(flvinfo_query_str))
            # 下の注意に書いてあることを回避するためにstrに変換してからパースさせる
            # ここまでくれば好き勝手いじれるでしょう
            watch_api_data_dict, flvinfo_dict = self._rewrite_main(
                req, watch_api_data_dict, flvinfo_dict)

            # 注意
            # python2のurlparse.parse_qs(s)は内部的にurlparse.unquoteを呼んでいる
            # urlparse.unquote(s)はunicode文字を渡すと
            # sをbytesに変換 => unquote => unicodeに戻してreturn
            # という働きをする。このとき最後のunicode変換にはlatin1文字コードが採用される
            # asciiがunicodeの128までのコードポイントと互換性があるように、
            # latin1もunicodeの255までのコードポイントと互換性がある
            # また、pythonはu'\xij'をu'\u00ij'と同等に解釈する
            # https://www.python.org/dev/peps/pep-0223/
            # http://docs.python.jp/2/howto/unicode.html#python-unicode
            flvinfo_query_str = urllib.urlencode(flvinfo_dict, True)
            flvinfo = urllib.quote(flvinfo_query_str)

            # json dictに入れるときはunicode型にする必要はない
            watch_api_data_dict["flashvars"]["flvInfo"] = flvinfo
            watch_api_data = json.dumps(watch_api_data_dict)

            if not escaped_json:
                return watch_api_data
            else:
                # htmlにjsonが埋め込まれていたので、エスケープした上で、ちゃんと戻してあげる
                watch_api_data = escape(
                    watch_api_data, {'"': "&quot;"})
                return ''.join(
                    (match.group("head"), watch_api_data, match.group("tail")))

        except Exception as e:
            logger.exception("error occurred, fallback.\n%s", e)
            return content

    def _rewrite_main(self, req, watch_api_data_dict, flvinfo_dict):
        """このメソッドをオーバーライドして
        watch_api_data_dict, flvinfo_dict
        の書き換えを実際に行う"""

        return watch_api_data_dict, flvinfo_dict


class Html5PlayerRewriter(RewriterAbstructBase):
    # 頑張ってニコキャッシュPyのAPIが引っかからないようにする
    req_path_pattern = re.compile("/+watch/+[^/]+/*$")

    watchAPIDataContainer_pattern = re.compile(
        """(?P<head>.*?)"""
        """<div id="js-initial-watch-data" """
        """data-api-data="(?P<data_api_data>.*)" """
        """data-environment="(?P<data_environment>.*)" hidden></div>(?P<tail>.*)""", re.DOTALL)

    def _is_videoinfo_request(self, req):
        return (req.host.startswith("www.nicovideo.jp") and
                self.req_path_pattern.match(req.path))

    def _rewrite(self, content, req, res):
        escaped_json = bool()

        try:
            if res.headers.get("Content-Type").\
                    startswith("application/json"):
                escaped_json = False
                data_api_data = content

            else:
                escaped_json = True
                match = self.watchAPIDataContainer_pattern.match(content)
                data_api_data = match.group("data_api_data")
                # エスケープされたjson文字列のエスケープを解く
                data_api_data = unescape(
                    data_api_data, {"&quot;": '"'})

            # json文字列をdictにする
            data_api_data_dict = json.loads(data_api_data)

            # pprint(data_api_data_dict)

            data_api_data_dict = self._rewrite_main(req, data_api_data_dict)

            data_api_data = json.dumps(data_api_data_dict)

            if not escaped_json:
                return data_api_data
            else:
                # htmlにjsonが埋め込まれていたので、エスケープした上で、ちゃんと戻してあげる
                data_api_data = escape(
                    data_api_data, {'"': "&quot;"})
                return ("""{head}"""
                        """<div id="js-initial-watch-data" """
                        """data-api-data="{data_api_data}" """
                        """data-environment="{data_environment}" hidden></div>{tail}""").format(
                            head=match.group("head"),
                            data_api_data=data_api_data,
                    data_environment=match.group("data_environment"),
                    tail=match.group("tail"))

        except Exception as e:
            logger.exception("error occurred, fallback.\n%s", e)

            return content

    def _rewrite_main(self, req, data_api_data_dict):
        """このメソッドをオーバーライドして
        data_api_data_dict
        の書き換えを実際に行う"""

        return data_api_data_dict
