from flask import Blueprint, request, jsonify
from core.database import users_col, locations_col, access_points_col
from core.auth import require_auth
from core.utils import serialize
from core.logger import log
from bson import ObjectId
from datetime import datetime, timedelta

bp = Blueprint("admin_routes", __name__)

@bp.route("/api/admin/stats", methods=["GET"])
@require_auth(roles=["admin"])
def admin_stats():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total_users         = users_col.count_documents({})
    localizations_today = locations_col.count_documents({"timestamp": {"$gte": today_start}})
    active_aps          = access_points_col.count_documents({"status": "active"})
    ten_min_ago         = datetime.utcnow() - timedelta(minutes=10)
    recent_count        = locations_col.count_documents({"timestamp": {"$gte": ten_min_ago}})
    avg_rpm             = round(recent_count / 10, 1)

    return jsonify({
        "total_users": total_users,
        "localizations_today": localizations_today,
        "active_aps": active_aps,
        "avg_rpm": avg_rpm
    })

@bp.route("/api/admin/live-locations", methods=["GET"])
@require_auth(roles=["admin"])
def admin_live_locations():
    all_users = list(users_col.find({"role": "user"}, {"password_hash": 0}))
    user_map = {u["_id"]: u for u in all_users}
    if not user_map:
        return jsonify([])

    latest_locs = []
    for uid in user_map.keys():
        # Fetch the single most recent location ping for this specific user
        loc = locations_col.find_one({"user_id": uid}, sort=[("timestamp", -1)])
        if loc:
            loc["_id"] = uid # Map ID to match previously expected structure
            latest_locs.append(loc)

    result = []
    for loc in latest_locs:
        u = user_map.get(loc["_id"])
        if u:
            result.append({
                "user_id":   str(u["_id"]),
                "user_name": u.get("name", u.get("username", "Unknown")),
                "role":      u.get("role", "user"),
                "floor":     loc.get("floor", 1),
                "x":         loc.get("x", 0),
                "y":         loc.get("y", 0),
                "area":      loc.get("area", "—"),
                "timestamp": loc["timestamp"].isoformat() if loc.get("timestamp") else None,
            })
    return jsonify(result)

@bp.route("/api/admin/users", methods=["GET"])
@require_auth(roles=["admin"])
def admin_list_users():
    search = request.args.get("q", "")
    query  = {}
    if search:
        query["$or"] = [
            {"name":     {"$regex": search, "$options": "i"}},
            {"email":    {"$regex": search, "$options": "i"}},
            {"username": {"$regex": search, "$options": "i"}}
        ]
    users = list(users_col.find(query, {"password_hash": 0}).limit(100))
    return jsonify(serialize(users))