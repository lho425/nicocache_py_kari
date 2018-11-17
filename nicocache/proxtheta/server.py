# -*- coding: utf-8 -
import traceback
from copy import deepcopy
import logging as _logging

from .backends import StandardModule
from .core import httpmes


import proxtheta
from proxtheta import utility
from .utility.server import transfer_resbody_to_client
from .core import common


ResponsePack = common.ResponsePack


logger = _logging.getLogger(__name__)
logger.debug("logger test: this is " + __name__)


def handle_error(error, tracebackinfo, req, client_file, info):
    if isinstance(error, httpmes.HTTPError):
        httperror = error
    else:
        httperror = httpmes.HTTP11Error((500, "Internal Server Error"))
        httperror.set_body(str(error) + "\n" + str(tracebackinfo))

    client_file.write(str(httperror))
    return httperror


# discuss!!!2つのハンドラ関数の分担はこれでよいか、むしろ統合すべきでは？エラー時にsockfileをclose()するのは誰の責任？
def handle_one_request(response_server, req, client_file, server_sockfile, info, always_close_connection):
    # 動作
    # requestをサーバに送る
    # hop by hopヘッダ以外はなるべくそのまま送る
    # なるべく透過的なプロクシとして振る舞う
    # なので、サーバにcloseを送ったのにkeepが帰ってきた場合はクライアントの接続を切らない、keepをそのまま送る
    # always_close_connectionフラグがたってる場合はクライアントにデータを送ったらクライアントをcloseする、closeを送る
    # なるべく透過的なプロクシとして振る舞うので
    # たとえサーバが(フォーマット上正しいが)http(rfc2616)に違反しているヘッダーを送って来てもそのまま転送する
    # たとえば、Content-LengthとTransfer-Encodingを同時に送る等
    # ヘッダに書かれていない部分は、サーバはhttp(rfc2616)に準拠していると仮定する
    # たとえば、コンテントの長さを推測する部分

    # clientがkeepのとき
    #    serveがcloseでもkeepにする
    #    serverはkeepする
    # clientをcloseすることになってるとき
    #    serverにcloseを送る
    #    clientをcloseする

    # fixme!!! 例外でserver_sockfile, result.server_sockfile,
    # result.body_fileがリークする なおせ

    logger.debug(
        str(info.client_address) + ": " + "start handling one request")

    if req.method == "CONNECT":
        logger.debug("client connect request http: %s", req)
        logger.debug("client connect request dest: %s:%s", req.host, req.port)
        client_file.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        client_file.flush()
        client_ssl_file = client_file.ssl_wrap(
            keyfile="./mitm/server.key", certfile="./mitm/server.crt", server_side=True)
        handle_client(response_server, client_ssl_file,
                      info, always_close_connection, connect_host_port=(req.host, req.port))
        return
    try:
        close_client = (always_close_connection or
                        req.is_connection_close() or
                        req.is_proxy_connection_close())
        # discuss!!! is this operation must here?
        httpmes.remove_hop_by_hop_header(req)

        if close_client:
            req.headers["Connection"] = "close"
        else:
            del req.headers["Connection"]
            # discuss!!!クライアントとのソケットを切断する決定権はこの関数がすべて握っているが、それでよいのか？

        results = response_server(req, server_sockfile, info)

        if results is None:
            client_file.close()  # !!! close()が分散してる 統一しろ
            return

    except Exception as e:
        logger.error("%s: error happened.\nrequest uri is:\n%s\nerrtype: %s\ndetail of error is:\n%s",
                     info.client_address, req.get_request_uri(), type(e), traceback.format_exc())

        handle_error(e, traceback.format_exc(), req, client_file, info)
        return None

    if ((not results.res.is_connection_close()) and
            (not results.res.is_chunked()) and
            (results.res.headers.get("Content-Length", None) is None) and
            httpmes.get_transfer_length(results.res, req) != 0):
        logger.warning(str(info.client_address) + ": " + """
########## warning! ##########
NOT Connection: close
and
NOT chunked
and
NO Content-Length HEADER!

request is:
%s
response header is:
%s
#######################""" % (str(req), str(results.res)))

    try:
        if (httpmes.get_transfer_length(results.res, req) == "unknown"):
            logger.debug(
                str(info.client_address) + ": " + "transfer length unknown")
            results.res.headers["Connection"] = "close"
            close_client = True

        res_for_client = deepcopy(results.res)

        if close_client:
            res_for_client.headers["Connection"] = "close"
        else:
            del res_for_client.headers["Connection"]

        try:
            client_file.write(str(res_for_client))
            logger.debug(str(info.client_address) + ": " + "transfer response")

            if results.body_file is not None:
                logger.debug(str(info.client_address) + ": " + "transfer body")
                transfer_resbody_to_client(
                    results.res, results.body_file, client_file, req)

            client_file.flush()

            logger.debug(
                str(info.client_address) + ": " + "transfer response to client, done.")
        except IOError:
            logger.debug(str(info.client_address) + ": " +
                         "connection disconnected suddenly. close connections")
            try:
                client_file.close()
            except Exception as e:
                logger.debug("client close error: %s", e)

            try:
                results.close()
            except Exception as e:
                logger.debug("resource close error: %s", e)

            assert client_file.closed

            return None

        results.close_body_file()

        if close_client:
            # !!! sokect.close()する責任は誰にある？
            logger.debug(str(info.client_address) + ": " + "close() client")
            client_file.close()

        logger.debug(
            str(info.client_address) + ": " + "end handling one request")
        return results.server_sockfile
    except Exception as e:
        logger.error("%s: error happened.\nrequest uri is:\n%s\nerrtype: %s\ndetail of error is:\n%s",
                     info.client_address, req.get_request_uri(), type(e), traceback.format_exc())
        try:
            client_file.close()
        except:
            pass

        try:
            results.close()
        except:
            pass
        return None


def handle_client(response_server, client_file, info, always_close_connection=False, connect_host_port=None):
    """
    connect_host_port: None | (host, port): (str, int)
    """

    logger.debug("client " + str(info.client_address) + " connected")

    server_sockfile = None  # SocketWrapper
    # 外部のserverに接続されているソケットを使いまわす
    try:
        while 1:
            if client_file.closed:
                return
            # fixme!!! まだ例外安全でない
            try:
                req = httpmes.HTTPRequest.create(client_file)
                if req is None:  # sock is EOF
                    logger.debug("client " + str(info.client_address) + " EOF")
                    client_file.close()
                    return
                if connect_host_port is not None:
                    req.host, req.port = connect_host_port
                    req.scheme = "https"
                    if req.port == 443:
                        req.port = None
                logger.debug("client request http: %s", req)
                logger.debug("client request dest: %s:%s", req.host, req.port)
            except httpmes.ParseError as e:
                logger.warning(
                    "bad req" + " `" + str(e) + "'" + " from " + str(info.client_address))
                res = httpmes.HTTP11Error((400, "Bad Request"))
                client_file.write(bytes(res))
                client_file.close()
                break
            except IOError:
                if not client_file.closed:
                    client_file.close()
                break
            # discuss!!!Is server_sockfile cache check necessary here?
#             if server_sockfile is not None:
#                 if not is_same_host_and_port(
#                     (server_sockfile.address.host, server_sockfile.address.port), (req.host, req.port)):
#                     server_sockfile.close()
#                     server_sockfile = None

            server_sockfile = handle_one_request(
                response_server, req, client_file, server_sockfile, info, always_close_connection)
            #!!!ここは非直感的
            # handle_one_requestの戻り値がソケットのキャッシュであるのはわかりにくい
            #!!!ここはtry にすべし
    finally:
        logger.debug("client " + str(info.client_address) + " disconnected")
        if server_sockfile is not None:
            server_sockfile.close()


def run_multiproc(response_server, port=8080, backendmodule=StandardModule):
    """posix only"""

    import os
    if not hasattr(os, "fork"):
        raise NotImplementedError(
            "run_multiproc() is posix only(using fork() system call).")

    return run(response_server=response_server,
               run_server_function=backendmodule.run_forking_server,
               port=port)


def run_multithread(response_server, port=8080, backendmodule=StandardModule):

    return run(response_server=response_server,
               run_server_function=backendmodule.run_multithreading_server,
               port=port)


def run(response_server, run_server_function, port=8080):

    def _handle(client_file, info):
        return handle_client(response_server, client_file, info)

    logger.info("starting on port " + str(port))

    run_server_function(port=port, handler_function=_handle)
