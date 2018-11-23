# -*- coding: utf-8 -
import io
import http.client
import urllib.parse
import collections.abc
import copy


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


def _parse_host_port(a_str):
    """
    "host:port" -> (host, port): (str, int)
    "host" -> (host, None): (str, None)
    """
    splitted = a_str.split(":", 1)
    if len(splitted) == 1:
        return splitted[0], None
    host, port_str = splitted
    return host, int(port_str)


def parse_uri_to_6_tuple(uri):
    if isinstance(uri, bytes):
        uri = uri.decode("latin")
    uri = urllib.parse.urlsplit(uri)

    return (uri.scheme,
            uri.hostname or "",
            uri.port,
            uri.path,
            uri.query,
            uri.fragment)


def _unparse_uri(scheme, host, port, path, query, fragment):
    netloc = host if host is not None else ""
    if port is not None:
        netloc += ":" + str(port)
    return urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))


def remove_hop_by_hop_header(mes):
    del mes.headers["Connection"]
    del mes.headers["Proxy-Connection"]


def remove_scheme_and_authority(req):
    req.host = ""
    req.port = None
    req.scheme = ""


class HTTPHeaders(http.client.HTTPMessage):

    def getheaders(self, name):
        return self.get_all(name)

    def __setitem__(self, name, value):
        del self[name]
        super().__setitem__(name, value)


def make_http_header_from_file(rfile):
    return http.client.parse_headers(rfile, _class=HTTPHeaders)


def get_empty_http_header():
    return make_http_header_from_file(io.BytesIO())

# naming rule is based on rfc2616


class HTTPMessage(object):

    def __init__(self, start_line_str="", headers=None, body=b""):
        self._start_line_str = start_line_str
        if headers is None:
            headers = get_empty_http_header()
        if isinstance(headers, collections.abc.Mapping):
            http_headers = get_empty_http_header()
            for key, value in headers.items():
                http_headers[key] = value

            headers = http_headers
            del http_headers

        self.headers = headers
        self._body = body

        # do not set content length because body can be None
        # jp!!! データ抽象クラスの__init__で余計なおせっかいをしない
        # 初期化と同時にcontent lengthを設定させたいなら、別の生成関数を作るべき
        # と思ったけどクッソ使いづらいのでおせっかいする
        # ていうかおせっかいするためのデータ抽象だろうが
        # discuss!!!どこまでおせっかいするか？
        return

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, body):
        if not isinstance(body, (bytes, type(None))):
            raise ValueError("body must be bytes or None, not %s" % type(body))
        self._body = body

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
            src = io.BytesIO(src.encode("utf-8"))
        elif isinstance(src, bytes):
            src = io.BytesIO(src)
        rfile = src
        while 1:
            raw_start_line = rfile.readline()
            assert isinstance(raw_start_line, bytes)
            if raw_start_line == b"\n" or raw_start_line == b"\r\n":
                pass  # continue until get any string or EOF

            elif raw_start_line == b"":
                return None  # no http message
            else:  # not new line or EOF
                break
        raw_start_line_str = raw_start_line.decode("latin")
        start_line_elements = cls._parse_start_line(raw_start_line_str)

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

    def __bytes__(self):
        s = self.get_start_line_str()
        s += "\r\n"

        s += str(self.headers)
        # str(self.headers) contains ending newline that separates headers and body,
        # so we must not append "\r\n".

        b = s.encode()
        if self.body is not None:
            b += self.body

        return b

    def __str__(self):
        return bytes(self).decode("utf-8")

    def set_body(self, body, default_text_subtype="plain"):
        body_is_str = False
        if isinstance(body, str):
            body_is_str = True
            body = body.encode("utf-8")
        self.body = body
        self.set_content_length()
        if body_is_str and (self.headers.get("Content-Type") is None):
            self.headers["Content-Type"] = "text/{}; charset=utf-8".format(
                default_text_subtype)

    def get_body_text(self):
        encoding = self.headers.get_content_charset()
        return self.body.decode(encoding)

    def set_body_text(self, body, default_text_subtype="plain"):
        encoding = self.headers.get_content_charset("utf-8")
        self.body = body.encode(encoding)
        self.set_content_length()
        if self.headers.get("Content-Type") is None:
            self.headers["Content-Type"] = "text/{}; charset={}".format(
                default_text_subtype, encoding)

    def is_chunked(self):
        return self.headers.get("Transfer-Encoding", "").lower() == "chunked"


class HTTPRequest(HTTPMessage):

    def __init__(self, xxx_todo_changeme, headers=None, body=b""):
        (method, (scheme, host, port, path, query, fragment),
         http_version) = xxx_todo_changeme
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
        if method.upper() == "CONNECT":
            host, port = _parse_host_port(uri)
            return (method, (
                '',
                host,
                port,
                '',
                '',
                ''
            ), http_version)

        return (method, parse_uri_to_6_tuple(uri), http_version)

    def get_request_uri(self):
        return _unparse_uri(self.scheme, self.host, self.port, self.path, self.query, self.fragment)

    def get_start_line_str(self):
        """not contain end CRLF"""
        assert isinstance(self.get_request_uri(), str)
        assert isinstance(self.method, str)
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


def create_http11_request(method="GET", uri=None, headers=None, body=None):
    uri_tpl = parse_uri_to_6_tuple(uri)

    req = HTTPRequest((method, uri_tpl, "HTTP/1.1"), headers, body)

    if "Host" not in req.headers:
        req.headers["Host"] = urllib.parse.urlsplit(uri).netloc

    return req


def _to_str(source):
    if isinstance(source, bytes):
        return source.decode("latin")
    else:
        return source


class HTTPResponse(HTTPMessage):

    def __init__(self, xxx_todo_changeme1, headers=None, body=b""):
        (http_version, status_code, reason_phrase) = xxx_todo_changeme1
        self.http_version = _to_str(http_version)
        self.status_code = status_code
        self.reason_phrase = _to_str(reason_phrase)
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


def create_http11_response(status_code, reason_phrase, headers=None, body=None):

    return HTTPResponse(("HTTP/1.1", status_code, reason_phrase), headers, body)


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
        if "Content-Length" in mes.headers:
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
    mes.set_body(body)


class HTTPError(HTTPResponse):

    def __init__(self, xxx_todo_changeme2, headers=None, body=""):
        (http_version, status_code,  reason_phrase) = xxx_todo_changeme2
        HTTPResponse.__init__(self, (http_version, status_code,  reason_phrase),
                              headers=headers, body=body)


class HTTP11Error(HTTPError):

    def __init__(self, xxx_todo_changeme3, headers=None, body=None):
        """if body=None, body will be set  '$status_code $reason_phrase' """
        (status_code,  reason_phrase) = xxx_todo_changeme3
        if body is None:
            body = ''.join((str(status_code), ' ', reason_phrase))

        HTTPError.__init__(self, ("HTTP/1.1", status_code,  reason_phrase),
                           headers=headers, body=body)
        self.set_content_length()
