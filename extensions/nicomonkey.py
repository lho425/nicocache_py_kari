# -*- coding: utf-8 -

import fnmatch
import logging as _logging

import nicocache
from nicocache.proxtheta.utility import proxy
import re
from nicocache.proxtheta.core.common import ResponsePack
from nicocache.proxtheta.core import httpmes
import os
import collections

logger = _logging.getLogger(__name__)


class NotUserScriptError(Exception):

    """usage: raise NotUserScriptError(filename)"""


def _readline(fileobj):
    rv = fileobj.readline()
    if not rv:
        raise EOFError

    return rv


def _parse_greasemonkey_header(fileobj):
    """return: {key1: [value1, value2, ...]}
    return(when parse error hapend): None"""

    # see http://wiki.greasespot.net/Metadata_Block
    metadata_dict = collections.defaultdict(list)

    try:
        while True:
            line = _readline(fileobj).rstrip("\r\n")
            if line == "// ==UserScript==":
                break

        while True:
            line = _readline(fileobj).rstrip("\r\n")
            # line = "// @key    value1 value2"
            # line = "// ==/UserScript=="
            if line == "// ==/UserScript==":
                break
            if not line.startswith("// @"):
                continue

            line = line[4:]
            # line = "key    value1 value2"

            key, _, value = line.partition(" ")
            # "key", " ", "    value1 value2"

            metadata_dict[key].append(value)

        return metadata_dict

    except EOFError:
        # unexpected EOF
        return None


class UserScript(object):

    def __init__(self, user_script_path):
        self.user_script_path = user_script_path
        with open(user_script_path) as f:
            header_dict = _parse_greasemonkey_header(f)
            f.seek(0, 0)
            self._script_str = f.read()

        if header_dict is None:
            raise NotUserScriptError(user_script_path)

        logger.debug("greasemonkey header: %s", header_dict)

        for key in ("name", "description", "namespace", "version"):
            value = header_dict.get(key, [""])[-1]
            setattr(self, key, value)

        for key in ("include", "exclude", "require"):
            value = header_dict.get(key, [])
            setattr(self, key, value)

    def match_url(self, url):
        match = False

        for include in self.include:
            logger.debug("url: %s; include: %s", url, include)
            if fnmatch.fnmatch(url, include):
                logger.debug("matched, url: %s; include: %s", url, include)
                match = True

        for exclude in self.exclude:
            if fnmatch.fnmatch(url, exclude):
                match = False

        return match

    def get_script_str(self):
        with open(self.user_script_path) as f:
            return self._script_str

    def get_require_list(self):
        return self.require


class UserScriptsGetter(object):

    def __init__(self, user_script_dir):
        self._user_script_dir = user_script_dir
        self._user_script_dir_mtime = None
        self._user_script_list = None

    def __call__(self):
        # 初回call時
        if (self._user_script_dir_mtime is None):
            self._load_user_scripts()

        # userscript directory が更新されたとき
        elif (self._user_script_dir_mtime !=
                os.path.getmtime(self._user_script_dir)):
            logger.info("user script directory `%s' is modified. "
                        "have to reload.", self._user_script_dir)
            self._load_user_scripts()

        # １つずつ更新されているか確かめる
        else:
            new_user_script_list = []

            def reload_if_modified(user_script):
                user_script_path = user_script.user_script_path
                if (user_script.mtime != os.path.getmtime(user_script_path)):
                    logger.info("user script `%s' is modified. "
                                "have to reload.", user_script_path)
                    return self._load_user_script(user_script_path)
                else:
                    return user_script

            new_user_script_list = map(reload_if_modified,
                                       self._user_script_list)
            new_user_script_list = filter(lambda us: us is not None,
                                          new_user_script_list)

            self._user_script_list = new_user_script_list

        return self._user_script_list

    @staticmethod
    def _load_user_script(filename):
        """mtimeを記録しておくカスタム版"""
        logger.info("load user script: %s", filename)
        user_script = load_user_script(filename)
        if user_script is not None:
            user_script.mtime = os.path.getmtime(filename)

        return user_script

    def _load_user_scripts(self):
        logger.info("load user script directory: %s", self._user_script_dir)
        user_script_dir_mtime = os.path.getmtime(self._user_script_dir)
        self._user_script_list = load_user_scripts(
            self._user_script_dir, self._load_user_script)

        # トランザクションにしておく
        self._user_script_dir_mtime = user_script_dir_mtime

    @classmethod
    def test(cls):
        """簡易的なテスト"""

        # 何も起きてない場合
        user_script_getter = cls("nicomonkey")
        user_script_list0 = user_script_getter()
        user_script_list1 = user_script_getter()
        assert user_script_list0 == user_script_list1

        # ディレクトリが更新された場合
        user_script_getter = cls("nicomonkey")
        user_script_list0 = user_script_getter()
        user_script_getter._user_script_dir_mtime = 0
        user_script_list1 = user_script_getter()
        assert user_script_list0 is not user_script_list1

        # userscript が更新された場合
        user_script_getter = cls("nicomonkey")
        user_script_list0 = user_script_getter()
        user_script_list0[0].mtime = 0
        user_script_list1 = user_script_getter()
        assert user_script_list0 is not user_script_list1


# class NicoMonkeyUserScriptServer(proxy.ResponseServer):
#
#     """ローカルファイルシステムのユーザースクリプトをブラウザに提供する"""
#
#     def __init__(self, user_script_dir):
#         self._user_script_dir = user_script_dir
#
#     @staticmethod
#     def accept(req, info):
#         # todo!!! proxthetaの側でreq.pathは正規化しておいて欲しい
#         return (req.host == "www.nicovideo.jp" and
#                 req.path.startswith("/nicomonkey/") and
#                 not req.path.endswith("/"))
#
#     def serve(self, req, server_sockfile, info):
#         #  "/aaa/bbb/ccc".split("/aaa/", 1) => ['', 'bbb/ccc']
#         user_script_path = req.path.split("/nicomonkey/", 1)[-1]
#         assert user_script_path == "dev/null"
#         logger.info(user_script_path)
#         user_script_path = os.path.join(
#             self._user_script_dir, user_script_path)
#
#         res = httpmes.HTTPResponse(("HTTP/1.1", 200, "OK"))
#         res.headers["Content-Type"] = "text/javascript"
#
#         res.headers["Connection"] = "close"
#         # proxthetaはkepp-alliveかつlengthが指定されていないレスポンスを現段階の実装だと扱えない
#
#         return ResponsePack(res=res,
#                             body_file=open(user_script_path),
#                             server_sockfile=server_sockfile)

def load_user_script(user_script_path):
    """ user_script_path をロードして返す
    読めなければNoneを返す"""

    try:
        return UserScript(user_script_path)
    except NotUserScriptError as e:
        logger.error(e)
        return None


def load_user_scripts(user_sript_dir, load_user_script=load_user_script):
    """return: [UserScript(), ...]"""

    user_script_list = []
    for dirname, _, filenames in os.walk("nicomonkey"):
        for filename in filenames:
            if filename.endswith(".js"):
                user_script = load_user_script(os.path.join(dirname, filename))
                if user_script is None:
                    logger.error(e)
                else:
                    user_script_list.append(user_script)

    return user_script_list


class NicoMonkeyResFilter(proxy.ResponseFilter):
    matcher = re.compile("(.*)(</ *body *>.*)", re.DOTALL)
    additionnal_text_start = """
<!-- added by nicomonkey-->
"""
    additionnal_text_script_start = """
<script type="text/javascript">
(function(){

"""

    additionnal_text_end = """
})();
</script>
<!-- END nicomonkey-->
"""

    def __init__(self, user_script_getter):
        self._user_script_getter = user_script_getter
        self._user_script_list = self._user_script_getter()

    def accept(self, res, req, info):
        self._user_script_list = self._user_script_getter()
        for user_script in self._user_script_list:
            if user_script.match_url(req.get_request_uri()):
                return True

    def filtering(self, res, req, info):
        body = res.get_body_text()
        m = self.matcher.match(body)
        if not m:
            return res

        original_body_head = m.group(1)
        original_body_tail = m.group(2)

        bodys = [original_body_head,
                 self.additionnal_text_start]

        scripts = []

        for user_script in self._user_script_list:
            if user_script.match_url(req.get_request_uri()):

                riquire_list = user_script.get_require_list()
                for riquire_uri in riquire_list:
                    # todo!!! type属性をmimetypeモジュールを使って入れるべし
                    script_tag = '<script src="%s"></script>\n' % riquire_uri
                    bodys.append(script_tag)

                scripts.append(user_script.get_script_str())
                scripts.append("\n\n")

        bodys.append(self.additionnal_text_script_start)
        bodys.extend(scripts)
        bodys.append(self.additionnal_text_end)
        bodys.append(original_body_tail)

        body = ''.join(bodys)
        res.set_body_text(body)
        return res


def get_extension():

    extension = nicocache.Extension("nicomonkey")
    extension.response_filter = NicoMonkeyResFilter(
        UserScriptsGetter("nicomonkey"))

    return extension


if __name__ == "__main__":
    _logging.basicConfig()
    logger.setLevel(_logging.INFO)
    logger.info("testing")
    UserScriptsGetter.test()

    logger.info("Test seems to be OK.")
