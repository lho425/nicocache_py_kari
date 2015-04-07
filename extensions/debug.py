# -*- coding: utf-8 -
from nicocache import Extension

import logging as _logging
from proxtheta.core import common
from proxtheta.core.common import ResponsePack
from proxtheta.utility import proxy

import proxtheta.utility.client

# name = ""
# logger = _logging.getLogger(name)
#
# proxtheta.utility.client.logger.setLevel(_logging.DEBUG)
#
#
# class ResFilter(proxy.ResponseFilter):
#
#     @staticmethod
#     def accept(res, req, info):
#         # デバッグ用
#
#         return False
#
#
# def get_extension():
#
#     extension = Extension(name)
#     extension.response_filter = ResFilter()
#
#     return extension
