# -*- coding: utf-8 -
import proxtheta.utility
from proxtheta.core import httpmes
from io import BytesIO


def abandon_body(res, body_file):
    if body_file is None:
        return
    if res.is_chunked():
        proxtheta.utility.server.trancefer_chunked(
            body_file, BytesIO())
        return
    length = httpmes.get_transfer_length(res)
    if length == "unknown":
        return

    body_file.read(length)


def get_partial_http_resource(xxx_todo_changeme,
                              req,
                              first_byte_pos,
                              last_byte_pos=None,
                              server_sockfile=None,
                              load_body=False,
                              nonproxy_camouflage=True):
    """Rengeヘッダをつけてからリクエストを送る"""
    (host, port) = xxx_todo_changeme
    if last_byte_pos is not None:
        req.headers["Range"] = (
            ''.join(("bytes=", str(first_byte_pos), "-", str(last_byte_pos))))
    else:
        req.headers["Range"] = (''.join(("bytes=", str(first_byte_pos), "-")))
    return proxtheta.utility.client.get_http_resource((host, port), req,
                                                      server_sockfile,
                                                      load_body,
                                                      nonproxy_camouflage)
