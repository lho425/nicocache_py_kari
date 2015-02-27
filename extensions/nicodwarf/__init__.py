# -*- coding: utf-8 -
from nicocache import Extension
from proxtheta.utility import proxy
import os

if not os.path.isdir("./nicodwarf"):
    os.mkdir("./nicodwarf")


class VideoRequestSaver(proxy.RequestFilter):

    @staticmethod
    def accept(req, info):
        if (req.host.startswith("smile-") and
                req.host.endswith(".nicovideo.jp") and
                req.path == "/smile"):
            name = req.query
            with open("./nicodwarf/" + name, "wb") as f:
                f.write(str(req))
        return False


extension = Extension()

extension.request_filters = [VideoRequestSaver()]