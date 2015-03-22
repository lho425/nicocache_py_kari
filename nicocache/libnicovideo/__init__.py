# -*- coding: utf-8 -

import urllib2
from xml.etree import ElementTree
import locale


def getthumbinfo(video_id):
    """
    http://ext.nicovideo.jp/api/getthumbinfo api wrapper
    returns xml (str)
    """
    return urllib2.urlopen(
        "http://ext.nicovideo.jp/api/getthumbinfo/" + video_id).read()


def getthumbinfo_etree(video_id):
    return ElementTree.fromstring(getthumbinfo(video_id))


class ThumbInfo(object):

    class NotThumbInfoError(Exception):
        pass

    def __init__(self, id):
        """id はvideo_idかwatchページのurlのwatch/XXXXX のXXXXXの部分
        常にXXXXX == video_idになるとは限らない(公式動画)
        getthumbinfoはvideo_idでもwatchページの番号でも、どちらでも取れる"""
        thumbinfo_etree = getthumbinfo_etree(id)
        try:
            # dirtyhack!!! python3に移植するまではすべてbytes型で文字列をやり取りする
            # unicodeをオブジェクトの外に出さない！
            self.video_id = thumbinfo_etree.find(
                ".//video_id").text.encode(locale.getpreferredencoding(), 'replace')
            self.title = thumbinfo_etree.find(
                ".//title").text.encode(locale.getpreferredencoding(), 'replace')
            self.movie_type = thumbinfo_etree.find(
                ".//movie_type").text.encode(locale.getpreferredencoding(), 'replace')
            self.size_high = thumbinfo_etree.find(
                ".//size_high").text.encode(locale.getpreferredencoding(), 'replace')
            self.size_low = thumbinfo_etree.find(
                ".//size_low").text.encode(locale.getpreferredencoding(), 'replace')
        except AttributeError:
            raise ThumbInfo.NotThumbInfoError(str(thumbinfo_etree))
