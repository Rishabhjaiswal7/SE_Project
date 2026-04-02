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
