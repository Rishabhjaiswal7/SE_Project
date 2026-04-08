from flask import Blueprint, request, jsonify
from core.database import locations_col
from core.auth import require_auth
from core.ml_engine import knn_localize
from core.utils import serialize
from core.logger import log
from core.limiter import limiter
from bson import ObjectId
from datetime import datetime

bp = Blueprint("location_routes", __name__)

@bp.route("/api/localize", methods=["POST"])
@require_auth()
@limiter.limit("60 per minute")
def localize():
    data    = request.get_json() or {}
    signals = data.get("signals", [])
    if not signals:
        return jsonify({"error": "No signals provided", "code": 400}), 400

    loc = knn_localize(signals)
    if request.user_role == "user":
        locations_col.insert_one({
            "user_id":   ObjectId(request.user_id),
            "floor":     loc["floor"],
            "x":         loc["x"],
            "y":         loc["y"],
            "area":      loc["area"],
            "signals":   signals,
            "timestamp": datetime.utcnow()
        })
    return jsonify(loc)
@bp.route("/api/user/heartbeat", methods=["POST"])
@require_auth(roles=["user", "admin", "operator"])
@limiter.limit("60 per minute")
def user_heartbeat():
    data = request.get_json() or {}
    signals = data.get("signals", [])

    if signals:
        loc = knn_localize(signals)
    else:
        last = locations_col.find_one(
            {"user_id": ObjectId(request.user_id)}, 
            sort=[("timestamp", -1)]
        )
        loc = {
            "floor": last.get("floor", 1) if last else 1,
            "x":     last.get("x", 0)     if last else 0,
            "y":     last.get("y", 0)     if last else 0,
            "area":  last.get("area", "Unknown") if last else "Unknown"
        }

    locations_col.insert_one({
        "user_id":   ObjectId(request.user_id),
        "floor":     loc.get("floor", 1),
        "x":         loc.get("x", 0),
        "y":         loc.get("y", 0),
        "area":      loc.get("area", ""),
        "timestamp": datetime.utcnow()
    })
    return jsonify({"success": True, "location": loc})

@bp.route("/api/location-history", methods=["GET"])
@require_auth()
def get_location_history():
    limit = int(request.args.get("limit", 50))
    records = list(
        locations_col.find({"user_id": ObjectId(request.user_id)})
        .sort("timestamp", -1).limit(limit)
    )
    return jsonify(serialize(records))

@bp.route("/api/location-history", methods=["POST"])
@require_auth()
def post_location_history():
    data = request.get_json()
    locations_col.insert_one({
        "user_id": ObjectId(request.user_id),
        "floor":   data.get("floor", 1),
        "x":       data.get("x", 0),
        "y":       data.get("y", 0),
        "area":    data.get("area", ""),
        "timestamp": datetime.utcnow()
    })
    return jsonify({"success": True}), 201
