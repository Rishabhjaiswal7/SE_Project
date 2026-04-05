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

@bp.route("/api/register", methods=["POST"])
@require_auth(roles=["admin", "operator"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    name     = data.get("name", "")
    email    = data.get("email", "")
    role     = data.get("role", "user")

    if not all([username, password, name]):
        return jsonify({"error": "Username, password, name are required", "code": 400}), 400
    if len(password) < 8 or len(password) > 100:
        return jsonify({"error": "Password must be 8-100 characters long", "code": 400}), 400
    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be 3-30 characters long", "code": 400}), 400
    if role not in ("user", "admin", "operator"):
        return jsonify({"error": "Invalid role", "code": 400}), 400

    if users_col.find_one({"username": username}):
        return jsonify({"error": "Username already taken", "code": 409}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    result  = users_col.insert_one({
        "username": username,
        "password_hash": pw_hash,
        "name": name,
        "email": email,
        "role": role,
        "created_at": datetime.utcnow()
    })
    log.info(f"New user {username} manually registered by admin/operator")
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201
