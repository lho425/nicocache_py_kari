# -*- coding: utf-8 -
import StringIO
import mimetools
import urlparse
import copy


def DEBUG(s):
    print "DEBUD:",
    print s


class ParseError(Exception):

    def __init__(self, s):
        Exception.__init__(self, s)
        return


def _parse_request_line(s):
    s = s.rstrip("\r\n")
    words = s.split(None, 3)
    if len(words) == 2:
        words.append("")

    if len(words) != 3:
        raise ParseError(s)
    return words


def _parse_status_line(s):
    s = s.rstrip("\r\n")
    words = s.split(None, 2)
    if len(words) == 2:
        words.append("")

    if len(words) != 3:
        raise ParseError(s)
    return words


def _parse_uri(uri):
    r = urlparse.urlsplit(uri)
    host = r.hostname
    r.host = host or ""
    return r


def _unparse_uri(scheme, host, port, path, query, fragment):
    netloc = host if host is not None else ""
    if port is not None:
        netloc += ":" + str(port)
    return urlparse.urlunsplit((scheme, netloc, path, query, fragment))


def remove_hop_by_hop_header(mes):
    del mes.headers["Connection"]
    del mes.headers["Proxy-Connection"]


def remove_scheme_and_authority(req):
    req.host = ""
    req.port = None
    req.scheme = ""


def make_http_header_from_file(rfile):
    h = mimetools.Message(rfile, 0)
    del h.fp  # for deepcopy
    return h


def get_empty_http_header():
    return make_http_header_from_file(StringIO.StringIO(""))

# naming rule is based on rfc2616


class HTTPMessage(object):

    # when override __init__(), you must override copy()

    def __init__(self, start_line_str="", headers=None, body=""):
        self._start_line_str = start_line_str
        if headers is None:
            headers = get_empty_http_header()
        self.headers = headers
        self.body = body

        # do not set content length because body can be None
        # jp!!! データ抽象クラスの__init__で余計なおせっかいをしない
        # 初期化と同時にcontent lengthを設定させたいなら、別の生成関数を作るべき
        # と思ったけどクッソ使いづらいのでおせっかいする
        # ていうかおせっかいするためのデータ抽象だろうが
        # discuss!!!どこまでおせっかいするか？
        return

    def copy_without_body(self):
        copy = copy.deepcopy(self)
        copy.body = None
        return copy

    def is_body_loaded(self):
        return self.body is not None

#     @classmethod
#     def create(cls, startline_elements, headers, body=None):
#        mes = cls(startline_elements, headers, body)
#        mes.set_content_length()
#        return mes

    @classmethod
    def create(cls, src, load_body=1):
        if isinstance(src, str):
            src = StringIO.StringIO(src)
        rfile = src
        while 1:
            raw_start_line = rfile.readline()
            if raw_start_line == "\n" or raw_start_line == "\r\n":
                pass  # continue until get any string or EOF

            elif raw_start_line == "":
                return None  # no http message
            else:  # not new line or EOF
                break

        start_line_elements = cls._parse_start_line(raw_start_line)

        headers = make_http_header_from_file(rfile)

        mes = cls(start_line_elements, headers, body=None)

        if load_body:
            mes.body = rfile.read(mes.get_content_length())

        return mes

    # must be override
    @classmethod
    def _parse_start_line(cls, raw_start_line):
        return raw_start_line.rsplit("\r\n")

    # must be override
    def get_start_line_str(self):
        return self._start_line_str

    def get_content_length(self):
        length = self.headers.get("Content-Length", None)
        if length is None:
            return None
        return int(length)  # discuss!!! Content-Lengthが無かったらNoneを返すか例外を返すか
        # Content-Lengthが無いケースは決して例外的状況ではないので、例外を投げるようなことはしたくない

    def set_content_length(self, length=None):
        """if length is None, guess length by self.body """
        if length is None and self.body is not None:
            length = len(self.body)
        self.headers["Content-Length"] = str(length)

        return

    def is_onetime_connection(self):
        if self.headers.get("Connection", "").lower() == "close":
            return True
        else:
            return False

    def is_connection_close(self):
        return self.headers.get("Connection", "").lower() == "close"

    def is_proxy_connection_close(self):
        return self.headers.get("Proxy-Connection", "").lower() == "close"

    def __str__(self):
        s = self.get_start_line_str()
        s += "\r\n"
        s += str(self.headers)
        s += "\r\n"
        if self.body is not None:
            s += self.body

        return s

    def set_body(self, body):
        self.body = body
        self.set_content_length()

    def is_chunked(self):
        return self.headers.get("Transfer-Encoding", "").lower() == "chunked"


class HTTPRequest(HTTPMessage):

    def __init__(self, (method, (scheme, host, port, path, query, fragment), http_version), headers=None, body=""):
        self.method = method
        self.http_version = http_version

        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path
        self.query = query
        self.fragment = fragment
        super(HTTPRequest, self).__init__(None, headers, body)
        return

    @classmethod
    def _parse_start_line(cls, raw_start_line):
        method, uri, http_version = _parse_request_line(raw_start_line)
        uri = _parse_uri(uri)

        return (method, (
            uri.scheme,
            uri.host,
            uri.port,
            uri.path,
            uri.query,
            uri.fragment
        ), http_version)

    def get_request_uri(self):
        return _unparse_uri(self.scheme, self.host, self.port, self.path, self.query, self.fragment)

    def get_start_line_str(self):
        """not contain end CRLF"""
        return self.method + " " + self.get_request_uri() + " " + self.http_version

    def get_request_line_str(self):
        """not contain end CRLF"""
        return self.get_start_line_str()

    def is_onetime_connection(self):
        return (super(HTTPRequest, self).is_onetime_connection() or
                self.method == "CONNECT")

    # see rfc2616 section 4.3
    def get_content_length(self):
        return int(self.headers.get("Content-Length", 0))


class HTTPResponse(HTTPMessage):

    def __init__(self, (http_version, status_code, reason_phrase), headers=None, body=""):
        self.http_version = http_version
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        super(HTTPResponse, self).__init__(None, headers, body)
        return

    @classmethod
    def _parse_start_line(cls, raw_start_line):

        http_version, status_str, reason_phrase = _parse_status_line(
            raw_start_line)
        try:
            status_code = int(status_str)
        except ValueError:
            raise ParseError(raw_start_line)

        return (http_version, status_code, reason_phrase)

    def get_start_line_str(self):
        """not contain end CRLF"""
        return self.http_version + " " + str(self.status_code) + " " + self.reason_phrase

    def get_status_line_str(self):
        """not contain end CRLF"""
        return self.get_start_line_str()

    # see rfc2616 section 4.3
    # ja!!!
    # 以下rfc2616日本語訳から引用
#     レスポンスメッセージでは、メッセージボディがメッセージに含まれている
#    かどうかは、リクエストメソッドとレスポンスステータスコード (section
#    6.1.1) の両方に依存する。HEAD リクエストメソッドへのレスポンスは、た
#    とえそこに含まれるエンティティヘッダフィールドがそうするようにあった
#    としても、いかなる場合もメッセージボディを含ん *ではならない*。1xx
#    (Information)、204 (no content)、304 (not modified) レスポンスでは、
#    すべてメッセージボディを含ん *ではならない*。その他のレスポンスでは、
#    その長さはゼロである *かもしれない* が、すべてメッセージボディを含ん
#    でいる
    def get_content_length(self):
        """if return value < 0, you have to read data until EOF."""
        return int(self.headers.get("Content-Length", -1))


CHUNKED = "chunked"

UNKNOWN = "unknown"


def get_transfer_length(mes, hint_req=None):
    # ja!!!
    """このメソッドは、http1.1に準拠するのではなく、サーバから送られてくるデータをなるべく忠実に転送することを目的とするために使う。
    長さがわかるときは数値が返り、
    Transfer Encoding が chunked のときは CHUNKEDが返り、
    EOFまで読み込む必要があるときは-1が返り、
    不明なときは UNKNOWN が返る。
     UNKNOWN が返るときは完全にクライアントとサーバ達だけが長さを知っているものとする。

    hint_reqはmesがHTTP Responseの場合に参考にされる可能性がある
    これは、HEAD メソッドのリクエストに対するレスポンスボディーの長さは0であるというrfc2616の規定に対応するためである。

    """
    if (hint_req is not None and hint_req.method == "HEAD"):
        # response for HEAD
        return 0

    if hasattr(mes, "method"):
        # request
        if mes.method == "CONNECT":
            return UNKNOWN
        else:
            return int(mes.headers.get("Content-Length", 0))

    else:
        # maybe response
        if mes.headers.has_key("Content-Length"):
            return int(mes.headers.get("Content-Length"))
        elif mes.is_connection_close():
            return -1
        elif mes.is_chunked():
            return CHUNKED

        elif (hasattr(mes, "status_code") and
              ((100 <= mes.status_code <= 199) or
               (mes.status_code == 204) or
               (mes.status_code == 304))):
            return 0
        else:
            return UNKNOWN

#!!!後で実装or破棄
# def load_body(mes, body_file, wfile=None):
#     """if wfile is not None, write body content to wfile.
#     else, mes.body = [body content]"""
#     length = httpmes.get_transfer_length(mes)
#     if length == "chunked":


def set_body(mes, body):
    mes.body = body
    mes.set_content_length()


class HTTPError(HTTPResponse, Exception):

    def __init__(self, (http_version, status_code,  reason_phrase), headers=None, body=""):
        HTTPResponse.__init__(self, (http_version, status_code,  reason_phrase),
                              headers=headers, body=body)
        Exception.__init__(
            self, (http_version, status_code,  reason_phrase), headers, body)

    def __deepcopy__(self, *args, **kw):
        # with default implement, copy.deepcopy does not work.
        # Exception class is the reason, I guess.
        return HTTPError((self.http_version, self.status_code, self.reason_phrase),
                         copy.deepcopy(self.headers), self.body)


class HTTP11Error(HTTPError):

    def __init__(self, (status_code,  reason_phrase), headers=None, body=None):
        """if body=None, body will be set  '$status_code $reason_phrase' """
        if body is None:
            body = ''.join((str(status_code), ' ', reason_phrase))

        HTTPError.__init__(self, ("HTTP/1.1", status_code,  reason_phrase),
                           headers=headers, body=body)
        self.set_content_length()
