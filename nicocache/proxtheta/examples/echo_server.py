import proxtheta
import proxtheta.core.httpmes
import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility

import logging as _logging
_logging.basicConfig()
logger = _logging.getLogger(__name__)
logger.setLevel(_logging.INFO)

logger.info("echo server")


def echo(req, _, __):

    logger.debug(str(req))

    res = proxtheta.core.httpmes.HTTPResponse.create("HTTP/1.1 200 OK")
    res.body = bytes(req)
    res.set_content_length()
    result = proxtheta.server.ResponsePack(res)
    return result


def main(port):
    proxtheta.server.run_multiproc(echo, port=port)


if __name__ == "__main__":
    import sys
    port = 8080
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    main(port)
