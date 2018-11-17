# -*- coding: utf-8 -

import urllib.request, urllib.error, urllib.parse
from xml.etree import ElementTree
import time


def getthumbinfo(watch_id):
    """
    http://ext.nicovideo.jp/api/getthumbinfo api wrapper
    returns xml (str)
    """
    return urllib.request.urlopen(
        "http://ext.nicovideo.jp/api/getthumbinfo/" + watch_id).read()


def getthumbinfo_etree(watch_id):
    return ElementTree.fromstring(getthumbinfo(watch_id))


class ThumbInfo(object):

    class NotThumbInfoError(Exception):
        pass

    def __init__(self, thumbinfo_etree):

        try:

            self.video_id = thumbinfo_etree.find(".//video_id").text
            self.title = thumbinfo_etree.find(".//title").text
            self.movie_type = thumbinfo_etree.find(".//movie_type").text
            self.size_high = thumbinfo_etree.find(".//size_high").text
            self.size_low = thumbinfo_etree.find(".//size_low").text
        except AttributeError:
            raise ThumbInfo.NotThumbInfoError(str(thumbinfo_etree))


class ThumbInfoServer(object):

    def __init__(self):
        pass

    def get(self, watch_id):
        """watch_id はvideo_idかwatchページのurlのwatch/XXXXX のXXXXXの部分
        常にXXXXX == video_idになるとは限らない(公式動画)
        getthumbinfoはvideo_idでもwatchページの番号でも、どちらでも取れる"""
        return ThumbInfo(getthumbinfo_etree(watch_id))


class CashngThumbInfoServer(object):
    # todo!!! スレッドセーフにする

    def __init__(self, max_age_secs=60 * 60):
        """max_age_secsのデフォルト値=60分"""
        # {watch_id: (timestamp, thumbinfo)} # timestampは取得した時のエポック秒
        self._thumbinfo_dict = {}
        self._max_age_secs = max_age_secs

    def get(self, watch_id):
        """watch_id はvideo_idかwatchページのurlのwatch/XXXXX のXXXXXの部分
        常にXXXXX == video_idになるとは限らない(公式動画)
        getthumbinfoはvideo_idでもwatchページの番号でも、どちらでも取れる"""
        now = time.time()
        thumb_tuple = self._thumbinfo_dict.get(watch_id, None)
        if ((thumb_tuple is None) or
                (now - thumb_tuple[0] > self._max_age_secs)):
            thumbinfo_etree = getthumbinfo_etree(watch_id)
            thumbinfo = ThumbInfo(thumbinfo_etree)
            self._thumbinfo_dict[watch_id] = (now, thumbinfo)

        else:
            thumbinfo = thumb_tuple[1]
            # _thumbinfo_dictから見つかった時は、timestampは更新しない
            # 永久に古いthumbinfoを返してしまう

        return thumbinfo
