# -*- coding: utf-8 -

def close_if_not_None(fileobj):
    if fileobj is not None:
        return fileobj.close()

def safe_close(fileobj):
    """fileobj can be None
    this function will never raise error"""
    
    try:
        return close_if_not_None(fileobj)
    except Exception as e:
        return e #not raise!