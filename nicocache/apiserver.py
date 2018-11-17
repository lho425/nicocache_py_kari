from flask import Flask


def create_flask_app(video_cache_manager):
    app = Flask(__name__)

    return app
