# -*- coding: utf-8 -
import logging as _logging
from proxtheta.core import httpmes
import errno
_logging.basicConfig(format="%(name)s: %(message)s", level=_logging.INFO)

import socket


import proxtheta.server
import proxtheta.utility.client
import proxtheta.core

logger = _logging.getLogger(__name__)

hdlr = _logging.StreamHandler()
fmt = _logging.Formatter("%(message)s")
hdlr.setFormatter(fmt)
logger.propagate = 0
logger.addHandler(hdlr)


# proxtheta.utility.client.logger.setLevel(_logging.DEBUG)
# proxtheta.logger.setLevel(_logging.DEBUG)

def proxy_root(req, info):
    """handle /"""
    res = proxtheta.core.httpmes.HTTPResponse.create(
        src="HTTP/1.1 200 OK\r\n", load_body=0)
    res.body = "nico analyzer"
    res.set_content_length()
    return proxtheta.server.ResponsePack(res=res)


def proxying(req, server_sockfile, info):

    if req.method == "CONNECT":
        logger.info(req.get_request_line_str() + " from " +
                    str((info.client_address.host, info.client_address.port)))
        e = httpmes.HTTP11Error((501, "Not Implemented"))
        logger.info("end CONNECT req")
        raise e

    (host, port) = (req.host, req.port)

    if req.host == "ext.nicovideo.jp" and req.path.startswith("/api/getthumbinfo"):
        logger.info("######## getthumbinfo ########")
        logger.info(req.get_request_uri())

    if req.host == "ext.nicovideo.jp":
        logger.info(req.get_request_uri())

    elif (not req.host.startswith("ads")) and req.host.endswith("nicovideo.jp"):
        logger.info(req.get_request_uri())

    else:
        logger.info(req.get_request_uri())

    try:
        if proxtheta.utility.server.\
                is_request_to_this_server(host, port, info.this_server_address.port):
            if req.path == "/":
                return proxy_root(req, info)
            else:
                return proxtheta.server.ResponsePack(httpmes.HTTP11Error((404, "Not Found")))

        else:
            # logger.info(req.get_request_line_str())
            return proxtheta.utility.client.get_http_resource(
                (host, port),
                req,
                server_sockfile,
                load_body=False,
                nonproxy_camouflage=True)

    except httpmes.HTTPError:
        raise

    except (socket.gaierror, proxtheta.utility.common.EmptyResponseError) as e:
        return proxtheta.server.ResponsePack(httpmes.HTTP11Error((502, "Bad Gateway")))

    except socket.timeout as e:
        return proxtheta.server.ResponsePack(httpmes.HTTP11Error((504, "Gateway Timeout")))

    except socket.error as e:
        if e.errno == errno.ETIMEDOUT:
            return proxtheta.server.ResponsePack(httpmes.HTTP11Error((504, "Gateway Timeout")))


def main(port):
    proxtheta.server.run_multithread(proxying, port=port)


if __name__ == "__main__":
    import sys
    port = 8080
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    main(port)
