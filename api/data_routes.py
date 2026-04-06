from flask import Blueprint, request, jsonify
from core.database import access_points_col, fingerprints_col, users_col
from core.auth import require_auth
from core.utils import serialize
from core.logger import log
from bson import ObjectId
from datetime import datetime
import bcrypt
import re

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

bp = Blueprint("data_routes", __name__)

@bp.route("/api/access-points", methods=["GET"])
@require_auth()
def list_aps():
    floor_filter = request.args.get("floor")
    query = {}
    if floor_filter:
        query["floor"] = int(floor_filter)
    aps = list(access_points_col.find(query))
    return jsonify(serialize(aps))

@bp.route("/api/access-points", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def create_ap():
    data = request.get_json()
    required = ["bssid", "ssid", "floor"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}", "code": 400}), 400
    if not access_points_col.find_one({"bssid": data["bssid"]}):
        pass # allow creation
    else:
        return jsonify({"error": "BSSID already exists", "code": 409}), 409
        
    if not MAC_REGEX.match(data["bssid"]):
        return jsonify({"error": "Invalid BSSID format", "code": 400}), 400

    doc = {
        "bssid":    data["bssid"].upper(),
        "ssid":     data["ssid"],
        "floor":    int(data["floor"]),
        "label":    data.get("label", ""),
        "rssi":     int(data.get("rssi", -70)),
        "status":   data.get("status", "active"),
        "created_at": datetime.utcnow()
    }
    result = access_points_col.insert_one(doc)
    log.info(f"Created new access point {data['bssid']}")
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201