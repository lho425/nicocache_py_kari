from unittest import TestCase

from . import apiserver


def _create_test_client(video_cache_manager):
    app = apiserver.create_flask_app(video_cache_manager)
    return app.test_client()


class TestMyFlaskApp(TestCase):
    def test_root(self):
        client = _create_test_client(None)
        res = client.get("/")
        self.assertEqual(404, res.status_code)
