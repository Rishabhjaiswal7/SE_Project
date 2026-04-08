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