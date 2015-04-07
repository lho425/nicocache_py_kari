# -*- coding: utf-8 -
from nicocache import Extension
from proxtheta.utility import proxy
import logging as _logging
import traceback

logger = _logging.getLogger("KanColle")
# logger.setLevel(_logging.INFO)

import json


class KCSResponseFilter(proxy.ResponseFilter):

    @staticmethod
    def accept(res, req, info):
        return req.path.startswith("/kcs")

    @staticmethod
    def load_body(res, req, info):
        return res.headers.get("Content-Type", "text").startswith("text")

    @staticmethod
    def filtering(res, req, info):
        try:
            logger.info("艦これ通信の傍受に成功した")
            if req.method == "POST":
                logger.info("サーバへの要求:\n"
                            "------------------------------\n"
                            "%s\n%s\n"
                            "------------------------------\n",
                            req.get_start_line_str(), req.body)
            else:
                logger.info("サーバへの要求:\n"
                            "------------------------------\n"
                            "%s\n"
                            "------------------------------\n",
                            req.get_start_line_str())

            if res.headers.get("Content-Type") == "text/plain":

                try:
                    svdata = res.body.split(
                        "=", 1)[1]  # """svdata={"api_result": ..."""
                    svdict = json.loads(svdata)
                    res_body = json.dumps(
                        svdict, ensure_ascii=False, indent=2).encode("utf-8")
                except Exception as e:
                    logger.error(
                        " could not parse as json\n"
                        "Content-Type: %s\n"
                        "%s", res.headers.get("Content-Type", None), e)
                    res_body = res.body

            elif res.headers.get("Content-Type").startswith("text"):
                res_body = res.body

            else:
                res_body = "(文字列で無いデータ)"

            logger.info("サーバからの返答:\n"
                        "------------------------------\n"
                        "%s\n%s\n"
                        "------------------------------\n",
                        res.get_start_line_str(), res_body)

            logger.info("報告終わり!")
        except:
            try:
                logger.exception()
            except:
                pass

        return proxy.ResponseFilter.filtering(res, req, info)


def get_extension():

    extension = Extension("艦これ盗聴器")
    extension.response_filter = KCSResponseFilter()

    return extension
