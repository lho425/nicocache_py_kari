# -*- coding: utf-8 -
import logging as _logging
# todo!!!py2かpy3でimportを分岐
from urlparse import urlparse, urlunparse, parse_qs

from .libnicovideo import videoinforewriter
from .libnicocache import (parse_nicovideo_request_query,
                           unparse_nicovideo_request_query)

logger = _logging.getLogger(__name__)


class NicoCacheRewriterMixin(object):

    def __init__(self, video_cache_manager):
        self._video_cache_manager = video_cache_manager

    def _has_video_caches_in_local(self, video_num):
        """return: (has_cache, has_low_cache)
        return type: (bool, bool)"""

        video_cache_pair = self._video_cache_manager.get_video_cache_pair(
            video_num)

        return (video_cache_pair[0].is_complete(), video_cache_pair[1].is_complete())


class NicoCacheGinzaRewriter(NicoCacheRewriterMixin,
                             videoinforewriter.GinzaRewriter):

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

        req_query = parse_qs(req.query, keep_blank_values=True)

        if (("eco" in req_query) and
                (req_query["eco"][0] != "" or req_query["eco"][0] != "0")):
            # eco=1等ユーザーによるエコノミー強制がTrueのとき
            pass
        else:
            if has_non_low_cache:  # とりあえず非エコノミーだけ
                # todo!!! 動画が削除されているときに、ローカルにエコノミーキャッシュがあるのなら、それを使うように書き換える

                if "url" not in flvinfo_dict:
                    # ダミーのデータを含む動画URLを入れる
                    flvinfo_dict["url"] = [
                        'http://smile-dummy00.nicovideo.jp/smile?m=' +
                        true_video_num + ".00000"]

                url = urlparse(flvinfo_dict["url"][0])
                (query_name, video_num, hash_num, is_low) = parse_nicovideo_request_query(
                    url.query)
                is_low = False

                # 有料動画フラグを消す
                watch_api_data_dict["flashvars"]["isNeedPayment"] = 0

                query = unparse_nicovideo_request_query(
                    query_name, video_num, hash_num, is_low)
                url = url._replace(query=query)
                flvinfo_dict["url"][0] = urlunparse(url)

        logger.debug("# rewrited watchAPIDataContainer #")
        videoinforewriter.print_dict(watch_api_data_dict, logger.debug)

        logger.debug("# rewrited flvinfo #")
        videoinforewriter.print_dict(flvinfo_dict, logger.debug)

        return watch_api_data_dict, flvinfo_dict

Rewriter = NicoCacheGinzaRewriter
