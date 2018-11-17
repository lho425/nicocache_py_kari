# -*- coding: utf-8 -
import unittest


import os
import io
import shutil
from .core import httpmes
from .utility.client import make_nonproxy_camouflaged_request
verbosity=1

class Test_nonproxy_camouflaged_request(unittest.TestCase):
    def test(self):
        req = httpmes.HTTPRequest(("GET", ("http", "host", None, "/", "", ""), "HTTP/1.1"))
                
        req = make_nonproxy_camouflaged_request(req)
        
        self.assertIsNotNone(req)
        
if __name__ == '__main__':
    unittest.main(verbosity=verbosity)




