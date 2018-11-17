from unittest import TestCase

from . import apiserver

from logging import getLogger

logger = getLogger(__name__)


def _create_test_client(video_cache_manager):
    app = apiserver.create_flask_app(video_cache_manager)
    return app.test_client()


class TestMyFlaskApp(TestCase):
    def test_root(self):
        client = _create_test_client(None)
        res = client.get("/")
        self.assertEqual(404, res.status_code)

    def test_save(self):
        client = _create_test_client(None)
        res = client.put("/nicocache/api/v1/save/sm1")
        if res.status_code != 200:
            logger.error("save api failed, response: %s", res)
        self.assertEqual(200, res.status_code)
