import proxtheta
import proxtheta.core.httpmes
import proxtheta.server
import proxtheta.utility.server as util


def dispatching_echo(req, client_file, info):
    if util.is_request_to_this_server(req.host, req.port, info.this_server_address.port):
        res = proxtheta.core.httpmes.HTTPResponse.create("HTTP/1.1 200 OK")
        res.body = bytes(req)
        res.set_content_length()
        r = proxtheta.server.ResponsePack(res)

        return r
    else:
        res = proxtheta.core.httpmes.HTTPResponse.create(
            "HTTP/1.1 404 Not Found")
        res.body = "404 Not Found\n"
        res.set_content_length()
        r = proxtheta.server.ResponsePack(res)
        return r


def main(port):
    proxtheta.server.run_multiproc(dispatching_echo, port=port)


if __name__ == "__main__":
    import sys
    port = 8080
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    main(port)
