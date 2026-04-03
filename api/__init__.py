from flask import Blueprint, jsonify
from core.logger import log

def register_error_handlers(app):
    @app.errorhandler(400)
    def handle_400(e):
        return jsonify({"error": "Bad Request", "code": 400}), 400

    @app.errorhandler(401)
    def handle_401(e):
        return jsonify({"error": "Unauthorized", "code": 401}), 401

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not Found", "code": 404}), 404

    @app.errorhandler(500)
    def handle_500(e):
        log.error(f"Internal Server Error: {str(e)}")
        return jsonify({"error": "Internal Server Error", "code": 500}), 500
