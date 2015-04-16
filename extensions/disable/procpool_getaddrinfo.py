# -*- coding: utf-8 -


import socket
from multiprocessing import Pool

import logging

"""windowsではホスト名の名前解決でブロックしてしまうので、
socketモジュールにモンキーパッチを当てて、マルチプロセスで名前解決を行うためのモジュール"""

# 下の2つの値は書き換えてもいい
# 最小のプロセス数、プロセス数は足りなくなったら増える、要らなくなったらこの値まで減る
min_processes_num = 4
# maxtasksperchild回処理をしたプロセスは終了して、あたらしく作り直されるか、足りてるなら作られない
# 大きくすると一度増えたプロセスが減りにくくなるが
# 小さくするとプロセスが頻繁に作り直されるので、性能が劣化する
maxtasksperchild = 10


# なんかの拍子(reload()とか)にmultiproc_getaddrinfoが無限に再帰してしまうのを防ぐ
if hasattr(socket, "_multiprocgai__original_getaddrinfo"):
    original_getaddrinfo = socket._multiprocgai__original_getaddrinfo
else:
    original_getaddrinfo = socket.getaddrinfo
    socket._multiprocgai__original_getaddrinfo = original_getaddrinfo


pool = None


def init():
    global pool
    pool = Pool(processes=min_processes_num, maxtasksperchild=maxtasksperchild)

_active = 0


def getaddrinfo(*args, **kwargs):
    global _active
    logging.debug("getaddrinfo(): %s", (args, kwargs))
    _active += 1

    # protected メンバに外からアクセスするという禁じ手を使っている
    # 尤も、Poolを継承すれば同じことできるけど
    try:
        # 待ちが4こくらいならすぐに番がまわってくるはず
        if _active - pool._processes >= 5:
            pool._processes += 5
            pool._join_exited_workers()
            pool._repopulate_pool()

        elif pool._processes - _active >= 5 and \
                pool._processes - min_processes_num >= 5:
            pool._processes -= 5

        return pool.apply(original_getaddrinfo, args, kwargs)
    finally:
        logging.debug("END getaddrinfo(): %s", (args, kwargs))
        _active -= 1


socket.getaddrinfo = getaddrinfo


import nicocache


def get_extension():
    init()
    return nicocache.Extension()
