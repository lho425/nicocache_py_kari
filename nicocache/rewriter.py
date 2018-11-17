# -*- coding: utf-8 -
import logging as _logging
# todo!!!py2かpy3でimportを分岐
from urllib.parse import parse_qs

from pprint import pprint, pformat
from .libnicovideo import videoinforewriter


logger = _logging.getLogger(__name__)


class NicoCacheRewriterMixin(object):

    def __init__(self, video_cache_manager):
        self._video_cache_manager = video_cache_manager

    def _has_video_caches_in_local(self, video_num):
        """return: (has_cache, has_low_cache)
        return type: (bool, bool)"""

        video_cache_pair = self._video_cache_manager.get_video_cache_pair(
            video_num)

        return (video_cache_pair[0].is_complete(),
                video_cache_pair[1].is_complete())


def _is_user_economy_mode(req):
    """
    eco=1等ユーザーによるエコノミー強制がかかっているか
    return: bool
    """
    req_query = parse_qs(req.query, keep_blank_values=True)

    return (("eco" in req_query) and
            req_query["eco"][0] != "0")

# NicoCacheHtml5PlayerRewriter は NicoCacheGinzaRewriter のコピペして一部を書き換えたもので、
# よろしくないコードだけど、Ginza(flash) はサポートしたくないので、
# とりあえずこのままで良い


class NicoCacheGinzaRewriter(NicoCacheRewriterMixin,
                             videoinforewriter.GinzaRewriter):

    def _rewrite_for_use_local_cache(
            self, watch_api_data_dict, flvinfo_dict, video_num, is_low):

        # ここでlogを残すのはよろしくないかもしれない
        # レビュアーさんに知恵をかしてもらう
        is_need_payment = (
            watch_api_data_dict["flashvars"].get("isNeedPayment", 0) > 0)

        deleted = ("deleted" in flvinfo_dict)

        if is_need_payment or deleted:
            if is_need_payment:
                logger.info(
                    "Video number %s requires payment to watch.", video_num)
            else:
                assert deleted
                logger.info(
                    "Video number %s was deleted.", video_num)

            logger.info(
                "But local%s cache found."
                " Rewrite video information to use that.",
                "" if not is_low else " low")

        # めんどくさいからsm203207の動画があるサーバに書き換える
        # crossdomain.xmlがそのサーバに飛ぶ
        flvinfo_dict["url"] = [
            'http://smile-com62.nicovideo.jp/smile?m=' +
            video_num + ".00000"]

        if is_low:

            flvinfo_dict["url"][0] += "low"

        # 有料動画フラグを消す
        watch_api_data_dict["flashvars"]["isNeedPayment"] = 0
        # 削除済フラグを消す
        if "deleted" in flvinfo_dict:
            del flvinfo_dict["deleted"]

    def _rewrite_main(self, req, watch_api_data_dict, flvinfo_dict):
        logger.debug("# watchAPIDataContainer #")
        videoinforewriter.print_dict(watch_api_data_dict, logger.debug)
        logger.debug("# flvinfo #")
        videoinforewriter.print_dict(flvinfo_dict, logger.debug)

        video_id = watch_api_data_dict["flashvars"]["videoId"]
        true_video_num = video_id[2:]

        (has_non_low_cache, has_low_cache) = self._has_video_caches_in_local(
            true_video_num)

        logger.debug("(has_non_low_cache, has_low_cache): %s",
                     (has_non_low_cache, has_low_cache))

        is_need_payment = (
            watch_api_data_dict["flashvars"].get("isNeedPayment", 0) > 0)

        deleted = ("deleted" in flvinfo_dict)

        is_user_economy_mode = _is_user_economy_mode(req)

        # 以下でニコ動のAPIのデータを書き換える
        # コードが冗長だが、しょうがない
        if is_user_economy_mode:
            if has_low_cache:
                self._rewrite_for_use_local_cache(
                    watch_api_data_dict, flvinfo_dict,
                    true_video_num, is_low=True)

        elif is_need_payment or deleted:
            if has_non_low_cache:
                self._rewrite_for_use_local_cache(
                    watch_api_data_dict, flvinfo_dict,
                    true_video_num, is_low=False)
            elif has_low_cache:
                self._rewrite_for_use_local_cache(
                    watch_api_data_dict, flvinfo_dict,
                    true_video_num, is_low=True)

        elif has_non_low_cache or has_low_cache:
            assert not is_user_economy_mode
            if has_non_low_cache:
                self._rewrite_for_use_local_cache(
                    watch_api_data_dict, flvinfo_dict,
                    true_video_num, is_low=False)
            else:
                if has_low_cache and flvinfo_dict["url"][0].endswith("low"):
                    self._rewrite_for_use_local_cache(
                        watch_api_data_dict, flvinfo_dict,
                        true_video_num, is_low=True)

        logger.debug("# rewrited watchAPIDataContainer #")
        videoinforewriter.print_dict(watch_api_data_dict, logger.debug)

        logger.debug("# rewrited flvinfo #")
        videoinforewriter.print_dict(flvinfo_dict, logger.debug)

        return watch_api_data_dict, flvinfo_dict


class NicoCacheHtml5PlayerRewriter(NicoCacheRewriterMixin,
                                   videoinforewriter.Html5PlayerRewriter):

    def _rewrite_for_use_local_cache(
            self, data, video_num, is_low):

        # ここでlogを残すのはよろしくないかもしれない
        # レビュアーさんに知恵をかしてもらう
        is_need_payment = data["context"].get("isNeedPayment", False)

        deleted = data["video"]["isDeleted"]

        if is_need_payment or deleted:
            if is_need_payment:
                logger.info(
                    "Video number %s requires payment to watch.", video_num)
            else:
                assert deleted
                logger.info(
                    "Video number %s was deleted.", video_num)

            logger.info(
                "But local%s cache found."
                " Rewrite video information to use that.",
                "" if not is_low else " low")
        # dmcInfo を消す
        # この nicocache は smile video 経由のアクセスでしかキャッシュの使用をしないため
        # dmcInfo があると dmc 経由で動画をダウンロードしてしまう。
        data["video"].pop("dmcInfo", None)

        # めんどくさいからsm203207の動画があるサーバに書き換える
        # crossdomain.xmlがそのサーバに飛ぶ
        data["video"]["smileInfo"]["url"] = 'http://smile-com62.nicovideo.jp/smile?m=' + \
            video_num + ".00000"

        if is_low:
            data["video"]["smileInfo"]["url"] += "low"

        # 有料動画フラグを消す
        data["context"]["isNeedPayment"] = False
        # 削除済フラグを消す
        data["video"]["isDeleted"] = False

    def _rewrite_main(self, req, data):
        logger.debug("# watch page api data #")
        logger.debug("%s", pformat(data))

        video_id = data["video"]["id"]
        true_video_num = video_id[2:]

        (has_non_low_cache, has_low_cache) = self._has_video_caches_in_local(
            true_video_num)

        logger.debug("(has_non_low_cache, has_low_cache): %s",
                     (has_non_low_cache, has_low_cache))

        is_need_payment = data["context"].get("isNeedPayment", False)

        deleted = data["video"]["isDeleted"]

        is_user_economy_mode = _is_user_economy_mode(req)

        # 以下でニコ動のAPIのデータを書き換える
        # コードが冗長だが、しょうがない
        if is_user_economy_mode:
            if has_low_cache:
                self._rewrite_for_use_local_cache(
                    data,
                    true_video_num, is_low=True)

        elif is_need_payment or deleted:
            if has_non_low_cache:
                self._rewrite_for_use_local_cache(
                    data,
                    true_video_num, is_low=False)
            elif has_low_cache:
                self._rewrite_for_use_local_cache(
                    data,
                    true_video_num, is_low=True)

        elif has_non_low_cache:
            assert not is_user_economy_mode
            self._rewrite_for_use_local_cache(
                data,
                true_video_num, is_low=False)

        logger.debug("# rewrited watch page api data #")
        logger.debug("%s", pformat(data))

        return data
