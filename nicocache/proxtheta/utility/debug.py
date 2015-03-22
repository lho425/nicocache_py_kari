# -*- coding: utf-8 -
import inspect
def get_processing_function_name():
    framerecord = inspect.stack()[1]
    #index [1] is  framerecord of caller of get_processing_function_name
    return framerecord[3] #index [3] is function name


