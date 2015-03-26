# -*- coding: utf-8 -
import logging as _logging
from copy import deepcopy


from ..core import httpmes, common
from ..core.iowrapper import create_sockfile

from .debug import get_processing_function_name as func_name
from .common import EmptyResponseError
from proxtheta.utility.common import safe_close
logger = _logging.getLogger(__name__)


#!!!まだ不完全、もっと充実させる
def make_nonproxy_camouflaged_request(req):
    httpmes.remove_hop_by_hop_header(req)
    # discuss!!! according to rfc2616,
    # removing hop by hop header is obligation of proxy server.
    # So, should we contain remove_hop_by_hop_header task to
    # request camouflaging?

    req = deepcopy(req)
    httpmes.remove_scheme_and_authority(req)
    return req


#!!!適当に実装したので、乱暴に扱うと不味いことが起きると思われる。
def get_http_resource(
        (host, port),
        req,
        server_sockfile=None,
        load_body=False,
        nonproxy_camouflage=True):
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

    if port is None:
        port = 80

    # Judgeing server_sockfile can be used or not.
    # if can not use server_sockfile:
    haveto_connect_sock = False
    if server_sockfile is None:
        haveto_connect_sock = True
        logger.debug(
            my_func_name + "(): server_sockfile is None. Have to create new connection.")
    elif (host, port) != (server_sockfile.address.host, server_sockfile.address.port):
        haveto_connect_sock = True
        logger.debug(my_func_name + "(): " +
                     str((host, port)) +
                     " != " +
                     str((server_sockfile.address.host, server_sockfile.address.port)) +
                     " Have to reconnect."
                     )
        server_sockfile.close()
    else:
        logger.debug(my_func_name + "(): " +
                     str((host, port)) +
                     " == " +
                     str((server_sockfile.address.host, server_sockfile.address.port)) +
                     " server socket cache hit!")
        haveto_connect_sock = False

    if haveto_connect_sock:
        logger.debug(my_func_name + "(): connecting to " + str((host, port)))

        server_sockfile = create_sockfile((host, port))
    else:
        logger.debug(
            my_func_name + "(): reuse server socket file of " + str((host, port)))

    if nonproxy_camouflage:
        req = make_nonproxy_camouflaged_request(req)
        assert req is not None

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
    # fixme!!!server_sockfileが例外安全でない！
    my_func_name = func_name()
    (host, port) = (server_sockfile.address.host, server_sockfile.address.port)
    try:
        server_sockfile.write(str(req))
        server_sockfile.flush()
    except IOError:

        logger.debug(my_func_name +
                     "(): given server_sockfile is broken. connecting to " +
                     str((host, port)))
        safe_close(server_sockfile)
        server_sockfile = create_sockfile((host, port))

        server_sockfile.write(str(req))
        server_sockfile.flush()

    res = httpmes.HTTPResponse.create(server_sockfile, load_body)

    if res is None:
        logger.debug(my_func_name + "(): no response from server with " +
                     req.get_start_line_str())
        logger.debug("retry Communicating.")

        safe_close(server_sockfile)
        server_sockfile = create_sockfile((host, port))
        server_sockfile.write(str(req))
        server_sockfile.flush()
        res = httpmes.HTTPResponse.create(server_sockfile, load_body)
        if res is None:
            server_sockfile.close()
            raise EmptyResponseError((host, port), str(req))

    return res, server_sockfile