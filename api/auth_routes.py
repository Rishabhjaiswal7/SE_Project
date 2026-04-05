from flask import Blueprint, request, jsonify
from core.database import users_col
from core.auth import make_token, require_auth
from core.logger import log
from core.limiter import limiter
import bcrypt
from datetime import datetime

bp = Blueprint("auth_routes", __name__)

@bp.route("/api/login", methods=["POST"])
@limiter.limit("20 per minute")
def login():
    data = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    role     = data.get("role", "user")

    if not username or not password:
        return jsonify({"error": "Username and password required", "code": 400}), 400

    user = users_col.find_one({"username": username})
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"]):
        log.warning(f"Failed login attempt for user: {username}")
        return jsonify({"error": "Invalid credentials", "code": 401}), 401

    if user["role"] != role:
        return jsonify({"error": f"Account is not a {role}", "code": 403}), 403

    log.info(f"Successful login for user {username}")
    token = make_token(str(user["_id"]), user["role"])
    return jsonify({
        "success": True,
        "token": token,
        "role": user["role"],
        "user": {"name": user["name"], "email": user.get("email", ""), "role": user["role"]}
    })
