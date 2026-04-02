"""
Z-Traces Backend API (Production Architecture)
Team: ALPHACODERS
Stack: Python Flask + PyMongo (MongoDB)
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from core.database import init_db
from core.logger import log
from core.limiter import limiter

from api import register_error_handlers
from api.auth_routes import bp as auth_bp
from api.admin_routes import bp as admin_bp
from api.location_routes import bp as location_bp
from api.data_routes import bp as data_bp

def create_app():
    app = Flask(__name__, static_folder=".", static_url_path="")
    app.config.from_object(Config)
    CORS(app)
    limiter.init_app(app)

    # Initialize Database mapping & indexes
    init_db()

    # Register decoupled API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(data_bp)

    # Apply global error configurations
    register_error_handlers(app)

    @app.route("/")
    def index():
        return send_from_directory(".", "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(".", path)

    log.info("Z-Traces Backend Production Architecture fully dynamically assembled.")
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
