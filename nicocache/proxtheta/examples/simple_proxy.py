
import proxtheta
import proxtheta.core.httpmes
import proxtheta.server
import proxtheta.utility.client
import proxtheta.utility

import logging as _logging
_logging.basicConfig()
logger = _logging.getLogger(__name__)
logger.setLevel(_logging.INFO)
logger.info("simple proxy")


def proxying(req, server_sockfile, info):
    logger.info("request from " + str(info.client_address) + "\n" + 
                "request message is:\n" + 
                "### start message ###\n" +
                str(req) + 
                "$$$ end message $$$"
                )
    (host, port) = (req.host, req.port)
    
    if proxtheta.utility.server.\
    is_request_to_this_server(host, port, info.this_server_address.port):
        res = proxtheta.core.httpmes.HTTPResponse.create(src="HTTP/1.1 200 OK\r\n", load_body=0)
        res.body = "proxy server"
        res.set_content_length()
        return proxtheta.server.ResponsePack(res=res)
    
    r = proxtheta.utility.client.get_http_resource(
                       (host, port),
                       req,
                       server_sockfile,
                       load_body=False,
                       nonproxy_camouflage=True)
    
    logger.info("get response from " + str((host, port)) + " to " +
                str(info.client_address) + "\n" +
                "response header is:\n" + 
                "### start message ###\n" +
                str(r.res) + 
                "$$$ end message $$$"
                )
    
    return r

def main(port):
    proxtheta.server.run_multithread(proxying, port=port)
    
if __name__ == "__main__":
    import sys
    port = 8080
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    main(port)
    
