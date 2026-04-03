import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config

def make_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(roles=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "Missing token", "code": 401}), 401
            payload = decode_token(auth.split(" ", 1)[1])
            if not payload:
                return jsonify({"error": "Invalid or expired token", "code": 401}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Insufficient permissions", "code": 403}), 403
            request.user_id = payload["sub"]
            request.user_role = payload["role"]
            return fn(*args, **kwargs)
        return wrapper
    return decorator
