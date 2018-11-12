# -*- coding: utf-8 -
import logging as _logging
from copy import deepcopy


from ..core import httpmes, common, utility
from ..core.iowrapper import create_sockfile

from .debug import get_processing_function_name as func_name
from .common import EmptyResponseError
from proxtheta.utility.common import safe_close
logger = _logging.getLogger(__name__)


def _have_to_connect_sock(host, port, ssl, server_sockfile):
    my_func_name = func_name()

    # Judgeing server_sockfile can be used or not.
    # if can not use server_sockfile:
    if server_sockfile is None:
        logger.debug(
            my_func_name + "(): server_sockfile is None. Have to create new connection.")
        return True

    if (host, port) != (server_sockfile.address.host, server_sockfile.address.port):
        logger.debug(my_func_name + "(): " +
                     str((host, port)) +
                     " != " +
                     str((server_sockfile.address.host, server_sockfile.address.port)) +
                     " Have to reconnect."
                     )
        return True
    if ssl != server_sockfile:
        logger.debug(my_func_name + "(): %s != %s (server_sockfile.ssl), Have to reconnect.",
                     ssl,
                     server_sockfile.ssl
                     )
        return True

    logger.debug(my_func_name + "(): " +
                 str((host, port)) +
                 " == " +
                 str((server_sockfile.address.host, server_sockfile.address.port)) +
                 " server socket cache hit!")
    return False


def _prepare_server_sock(host, port, ssl, server_sockfile):
    my_func_name = func_name()

    if _have_to_connect_sock(host, port, ssl, server_sockfile):
        logger.debug(my_func_name + "(): connecting to " + str((host, port)))
        utility.close_if_not_None(server_sockfile)

        server_sockfile = create_sockfile((host, port), ssl=ssl)
    else:
        logger.debug(
            my_func_name + "(): reuse server socket file of " + str((host, port)))

    return server_sockfile


def make_nonproxy_camouflaged_request(req):
    httpmes.remove_hop_by_hop_header(req)
    # discuss!!! according to rfc2616,
    # removing hop by hop header is obligation of proxy server.
    # So, should we contain remove_hop_by_hop_header task to
    # request camouflaging?

    #!!!まだ不完全、もっと充実させる
    req = deepcopy(req)
    httpmes.remove_scheme_and_authority(req)
    return req


#!!!適当に実装したので、乱暴に扱うと不味いことが起きると思われる。
def get_http_resource(
        (host, port),
        req,
        server_sockfile=None,
        load_body=False,
        nonproxy_camouflage=True,
        ssl=None):
    """return type: proxtheta.server.ResponsePack

    Send req to given (host, port) server and get response.

    req will be changed if nonproxy_camouflage.

    If server_sockfile is not None, reuse server_sockfile
    if (host, port) of server_sockfile equal to given (host, port).

    If load_body, contain response body in ResponsePack.res, and
    ResponsePack.body_file will be None.
    If not load_body, not contain response body in ResponsePack.res, and
    ResponsePack.body_file will be a duplication of server_sockfile.
    The duplication can close() but original server_sockfile will not be closed.

    If response is Connection: close,ResponsePack.server_sockfile
    will be None.

    If transfer length of response is 0,
    ResponsePack.res.body will be "", ResponsePack.body_file will be None.
    """
    # fixme!!!server_sockfileが例外安全でない！
    my_func_name = func_name()

    if ssl is None:
        ssl = (req.scheme == "https")
        logger.debug("%s(): req.scheme=%s, ssl=%s",
                     my_func_name, req.scheme, ssl)
    if port is None:
        if ssl:
            port = 443
        else:
            port = 80

    if nonproxy_camouflage:
        req = make_nonproxy_camouflaged_request(req)
        assert req is not None

    server_sockfile = _prepare_server_sock(host, port, ssl, server_sockfile)

    res, server_sockfile = get_http_response_with_sockfile(
        req, server_sockfile, load_body)

    if load_body:

        body_file = None
        if res.is_connection_close():
            server_sockfile.close()
            server_sockfile = None
    else:
        if httpmes.get_transfer_length(res, req) == 0:
            res.body = ""
            body_file = None
        else:
            if not res.is_connection_close():
                body_file = server_sockfile.make_unclosable_dup()
            else:
                body_file = server_sockfile
                server_sockfile = None

    return common.ResponsePack(res, body_file, server_sockfile)


def _do_get_http_response_with_sockfile(req, server_sockfile, load_body, raise_io_error):
    """
    return: (res, io_error)
    """
    my_func_name = func_name()
    try:
        server_sockfile.write(str(req))
        server_sockfile.flush()
    except IOError as e:

        logger.debug(my_func_name +
                     "(): given server_sockfile is broken.")
        if raise_io_error:
            raise e
        else:
            return None, e

    res = httpmes.HTTPResponse.create(server_sockfile, load_body)

    if res is None:
        logger.debug(my_func_name + "(): no response from server with " +
                     req.get_start_line_str())
        return None, None

    return res, None


def get_http_response_with_sockfile(
        req,
        server_sockfile,
        load_body=False):
    """
    returns (res, used_server_sockfile).
    you can reuse used_server_sockfile if connection keeps alive.
    server_sockfile must not be None.
    will not check where server_sockfile is connecting.
    if write or read error occurred, reconnect to server_sockfile.address and retry once.
    this is low level function. you had better use get_http_resource().
    """
    my_func_name = func_name()
    (host, port) = (server_sockfile.address.host, server_sockfile.address.port)

    res, io_error = _do_get_http_response_with_sockfile(
        req, server_sockfile, load_body, raise_io_error=False)

    # reporting error to logger.debug
    if io_error is not None:
        logger.debug(my_func_name +
                     "(): given server_sockfile is broken. connecting to " +
                     str((host, port)))
    elif res is None:
        logger.debug(my_func_name + "(): no response from server with " +
                     req.get_start_line_str())
        logger.debug("retry Communicating.")

    if res is None:

        safe_close(server_sockfile)
        server_sockfile = create_sockfile(
            (host, port), ssl=server_sockfile.ssl)
        res, _ = _do_get_http_response_with_sockfile(
            req, server_sockfile, load_body, raise_io_error=True)
        if res is None:
            server_sockfile.close()
            raise EmptyResponseError((host, port), str(req))

    return res, server_sockfile
