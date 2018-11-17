from flask import Flask, jsonify


def create_flask_app(video_cache_manager):
    app = Flask(__name__)

    @app.route("/nicocache/api/v1/save/<video_id>", methods=["PUT"])
    def save(video_id):
        return jsonify({}), 500

    return app
