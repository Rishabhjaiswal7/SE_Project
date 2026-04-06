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

@bp.route("/api/access-points/<ap_id>", methods=["PUT"])
@require_auth(roles=["operator", "admin"])
def update_ap(ap_id):
    data = request.get_json()
    update_fields = {k: data[k] for k in ["ssid", "floor", "label", "rssi", "status"] if k in data}
    if "floor" in update_fields:
        update_fields["floor"] = int(update_fields["floor"])
    if "rssi" in update_fields:
        update_fields["rssi"] = int(update_fields["rssi"])
    access_points_col.update_one({"_id": ObjectId(ap_id)}, {"$set": update_fields})
    return jsonify({"success": True})

@bp.route("/api/access-points/<ap_id>", methods=["DELETE"])
@require_auth(roles=["operator", "admin"])
def delete_ap(ap_id):
    access_points_col.delete_one({"_id": ObjectId(ap_id)})
    return jsonify({"success": True})

@bp.route("/api/fingerprints", methods=["GET"])
@require_auth()
def list_fingerprints():
    floor_filter = request.args.get("floor")
    query = {}
    if floor_filter:
        query["floor"] = int(floor_filter)
    fps = list(fingerprints_col.find(query).limit(500))
    return jsonify(serialize(fps))

@bp.route("/api/fingerprints", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def create_fingerprint():
    data = request.get_json()
    required = ["bssid", "rssi", "floor"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}", "code": 400}), 400
    ap = access_points_col.find_one({"bssid": data["bssid"]})
    if not ap:
        return jsonify({"error": "BSSID not found in access points", "code": 404}), 404
        
    if not MAC_REGEX.match(data["bssid"]):
        return jsonify({"error": "Invalid BSSID format", "code": 400}), 400

    doc = {
        "bssid":  data["bssid"].upper(),
        "rssi":   int(data["rssi"]),
        "floor":  int(data["floor"]),
        "area":   data.get("area", ""),
        "x":      int(data.get("x", 300)),
        "y":      int(data.get("y", 120)),
        "created_at": datetime.utcnow()
    }
    result = fingerprints_col.insert_one(doc)
    log.info(f"Recorded new fingerprint at x:{doc['x']} y:{doc['y']}")
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201