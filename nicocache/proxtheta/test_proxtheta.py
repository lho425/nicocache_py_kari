# -*- coding: utf-8 -
import unittest


import os
import StringIO
import shutil
from proxtheta import httpmes, utility
import proxtheta
import proxtheta.utility
import proxtheta.utility.client
verbosity=1

class Test_nonproxy_camouflaged_request(unittest.TestCase):
    def test(self):
        req = httpmes.HTTPRequest(("GET", ("http", "host", None, "/", "", ""), "HTTP/1.1"))
                
        req = proxtheta.utility.client.make_nonproxy_camouflaged_request(req)
        
        self.assertIsNotNone(req)
        
if __name__ == '__main__':
    unittest.main(verbosity=verbosity)




