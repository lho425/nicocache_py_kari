# -*- coding: utf-8 -

import os
import datetime
import time
import threading
import socket
import ssl
import urllib
import re
import logging as _logging

import nicocache
from nicocache import Extension
from proxtheta.utility import proxy
from proxtheta.core import httpmes, iowrapper
from libnicocache.base import VideoCacheInfo


_video_cache_manager = None

default_config = {"passwordFile": None}

logger = _logging.getLogger(__name__)


class HTTPResponseError(Exception):
    pass


class NicoNicoAccessError(Exception):
    pass


class NicoNicoLoginError(Exception):
    pass


def http11_get(url, headers=None,
               load_body=True, raise_on_error=True, proxy=()):

    req = httpmes.HTTPRequest.create("GET %s HTTP/1.1\r\n\r\n" % str(url))

    req.headers["Host"] = req.host
    if proxy:
        host, port = proxy
    else:
        host, port = req.host, req.port
        req.scheme = ""
        req.host = ""
        req.port = None
        port = port or 80

    req.headers["Connection"] = "close"
    if headers:
        for k, v in headers.iteritems():
            req.headers[k] = v

    sock = iowrapper.create_sockfile((host, port))

    sock.write(str(req))

    res = httpmes.HTTPResponse.create(sock, load_body)

    if raise_on_error and (400 <= res.status_code <= 599):
        sock.close()
        raise HTTPResponseError(res)

    if load_body:
        sock.close()
        return res

    return res, sock


def login_to_niconico():
    pwfilename = nicocache.get_config(
        "nicodwarf", "passwordFile", default_config)
    with open(pwfilename) as passwd:
        username = passwd.readline().rstrip("\r\n")
        password = passwd.readline().rstrip("\r\n")

    req_str = """\
POST /secure/login?site=niconico HTTP/1.1
Host: secure.nicovideo.jp
Connection: close
Content-Type: application/x-www-form-urlencoded
"""

    body = "mail={mail}&password={password}".format(
        mail=urllib.quote(username), password=urllib.quote(password))

    req = httpmes.HTTPRequest.create(req_str)
    req.set_body(body)

    sock = socket.create_connection(("secure.nicovideo.jp", 443))
    sock = ssl.wrap_socket(sock, ca_certs="cacert.pem",
                           cert_reqs=ssl.CERT_REQUIRED)

    sock.write(str(req))

    # fixme!!! iowrapperのバグを直してiowrapperを使う
    res_str = sock.read(10000)

    res = httpmes.HTTPResponse.create(res_str)

    cookie = None
    for s in res.headers.getheaders("set-cookie"):
        if s.startswith("user_session=user_session_"):
            cookie = s
            break

    if not cookie:
        raise NicoNicoLoginError("login failed. email: %s" % username)

    return cookie


def get_nicohistory(video_id, cookie):
    """video_idはsm...かスレッドid
    自動でリダイレクトはしない
    余計なcookieも入る"""

    res, f = http11_get("http://www.nicovideo.jp/watch/" + video_id,
                        {"Cookie": cookie}, load_body=False)
    f.close()

    cookie = None
    for s in res.headers.getheaders("set-cookie"):
        if s.startswith("nicohistory="):
            cookie = s
            break

    if not cookie:
        raise NicoNicoAccessError("no nicohistory cookie from server: \n"
                                  "%s:\n"
                                  "%s" % ("http://www.nicovideo.jp/watch/"
                                          + video_id, res))

    return cookie


def get_video_url(video_id, cookie):

    res = http11_get(
        "http://flapi.nicovideo.jp/api/getflv/" + video_id,
        dict(cookie=cookie))

    m = re.match(r".*url=([^&]*)(&.*)?", res.body)

    if not m:
        raise NicoNicoAccessError("can not get getflv info of %s" % video_id)

    video_url = urllib.unquote(m.group(1))

    return video_url


def get_seconds_to_next_fetch_time(fetch_time):
    """fetch_time: datetime.time"""
    now = datetime.datetime.now()
    fetch_datetime = datetime.datetime.combine(now.date(), fetch_time)
    if fetch_datetime < now:
        # fetch_timeをすでに過ぎている場合、次の日にfetchする
        next_fetch_datetime = fetch_datetime + datetime.timedelta(days=1)
    else:
        next_fetch_datetime = fetch_datetime

    return (next_fetch_datetime - now).total_seconds()


def fetch_all_saved_video():
    logger.info("dwarf: start fetching.")
    _video_cache_manager = nicocache.get_video_cache_manager()

    video_cache_list = _video_cache_manager.get_video_cache_list(
        VideoCacheInfo.make_query(
            rootdir=nicocache.get_config(
                "global", "cacheFolder"),
            subdir="save"))

    def have_to_fetch(video_cache):
        return video_cache.info.low or video_cache.info.tmp

    video_cache_list = filter(have_to_fetch, video_cache_list)

    if not video_cache_list:
        logger.info("dwarf: nothing to fetch. finish fetching.")
        return

    nicocache_port = nicocache.get_config_int("global", "listenPort")

    # ニコニコにログインし
    # fetchするvideo_idに対し
    #     videoのuriを取得し
    #     httpリクエストを作り
    #     自分自身(nicocache)にリクエストを送って
    #     動画を読み
    #     saveする

    cookie = login_to_niconico()
    for video_cache in video_cache_list:

        try:

            video_id = video_cache.info.video_id
            logger.info("fetching %s", video_id)

            nonlow_video_cache = _video_cache_manager.get_video_cache(
                video_cache.info.video_num, low=False)

            if (nonlow_video_cache.is_complete() and
                    nonlow_video_cache.info.subdir):
                logger.info("found %s",
                            nonlow_video_cache.info.make_cache_file_path())
                logger.info(
                    "there is a non economy saved complete cache of %s. "
                    "skipping.", video_id)
                continue

            if video_id.startswith("so"):
                # watchページのリダイレクトを利用してスレッドidを取得
                res = http11_get(
                    "http://www.nicovideo.jp/watch/" + video_id,
                    dict(cookie=cookie))

                video_id = re.match(
                    r"http://www.nicovideo.jp/watch/(.*)",
                    res.headers["location"]).group(1)

            video_url = get_video_url(video_id, cookie)

            if video_url.endswith("low"):
                logger.info("video %s is forced economy mode. "
                            "skip fetching.", video_cache.info.video_id)

            nicohistory_cookie = get_nicohistory(video_id, cookie)

            res, sockfile = http11_get(
                video_url, {"Cookie": nicohistory_cookie}, False,
                raise_on_error=False,
                proxy=("localhost", nicocache_port))

            if res.status_code != 200:
                logger.error("denied: %s", res)
                continue

            while True:
                data = sockfile.read(4096 * 1024)
                if not data:
                    break

            sockfile.close()

            http11_get("http://www.nicovideo.jp/watch/%s/save" %
                       video_id, proxy=("localhost", nicocache_port))

        except:
            logger.exception(
                "exception raised. skip %s.", video_cache.info.video_id)

        # サーバに負荷をかけ過ぎないようにするため、間隔をあける
        time.sleep(30)

    logger.info("dwarf: finish fetching.")


def main_loop():

    fetch_time = datetime.time(hour=2, minute=1)

    if 2 <= datetime.datetime.now().hour <= 6:
        # 初回(プラグインロード時)が夜中なら、１秒後にfetchを開始する
        logger.info("it's midnight. Nico dwarf will wake up soon.")
        seconds_to_next_fetch_time = 1
    else:
        seconds_to_next_fetch_time = get_seconds_to_next_fetch_time(fetch_time)

    while True:

        try:
            # ログに表示する時間は、渡す秒数の小数点以下を切り捨てないとミリ秒まで表示されて鬱陶しいので
            # seconds=int(...)とする
            logger.info("dwarf will wake up after '%s'.",
                        datetime.timedelta(
                            seconds=int(seconds_to_next_fetch_time)))
            time.sleep(seconds_to_next_fetch_time)
            fetch_all_saved_video()
        except NicoNicoLoginError:
            logger.exception("")
        except:
            # 例外を垂れ流すとスレッドが終了するのでここで止める
            logger.exception("")

        seconds_to_next_fetch_time = get_seconds_to_next_fetch_time(fetch_time)


def check_passwd_file_format(passwd):
    try:
        with open(pwfilename) as passwd:
            username = passwd.readline().rstrip("\r\n")
            password = passwd.readline().rstrip("\r\n")

            return username and password
    except:
        logger.exception()

    return False

pwfilename = nicocache.get_config(
    "nicodwarf", "passwordFile", default_config)

if not pwfilename:
    logger.error(
        u"'passwordFile' オプションが configファイルの[nicodwarf] セクションにありません。")
    logger.error(
        u"nicodwarf が動作するために'passwordFile' オプションを設定し、 "
        u"nicocache を再起動してください.")

elif not os.path.exists(pwfilename):
    logger.error(
        u"passwordFile '%s' が存在しません.", pwfilename)
    logger.error(
        u"nicodwarf が動作するために '%s' を作成し、 "
        u"nicocache を再起動してください.", pwfilename)

elif not check_passwd_file_format(pwfilename):
    logger.error(u"'%s' は不正な passwordFileです。", pwfilename)
    logger.error(u"1行目にニコニコ動画に登録したメールアドレス、\n"
                 u"2行目にニコニコ動画のパスワードをかいてください。")

else:
    def get_extension():

        extension = Extension(u"nicodwarf(fetcher相当)")

        fethcer_thread = threading.Thread(target=main_loop)
        fethcer_thread.daemon = True
        fethcer_thread.start()

        return extension

del pwfilename
