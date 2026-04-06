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

@bp.route("/api/fingerprints/<fp_id>", methods=["DELETE"])
@require_auth(roles=["operator", "admin"])
def delete_fingerprint(fp_id):
    fingerprints_col.delete_one({"_id": ObjectId(fp_id)})
    return jsonify({"success": True})

@bp.route("/api/floor-mapping", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def save_floor_mapping():
    data = request.get_json()
    floor     = int(data.get("floor", 1))
    positions = data.get("positions", []) 

    for pos in positions:
        if "bssid" in pos:
            access_points_col.update_one(
                {"bssid": pos["bssid"], "floor": floor},
                {"$set": {"x": pos.get("x", 300), "y": pos.get("y", 120)}}
            )
            fingerprints_col.update_many(
                {"bssid": pos["bssid"], "floor": floor},
                {"$set": {"x": pos.get("x", 300), "y": pos.get("y", 120)}}
            )
    return jsonify({"success": True, "floor": floor})

@bp.route("/api/seed", methods=["POST"])
def seed_db():
    default_users = [
        {"username": "admin",    "password": "admin123",    "name": "Admin User",     "role": "admin"},
        {"username": "operator", "password": "op123",       "name": "System Operator","role": "operator"},
        {"username": "user",     "password": "user123",     "name": "Test User",      "role": "user"},
    ]
    created = []
    for u in default_users:
        if not users_col.find_one({"username": u["username"]}):
            pw_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": u["username"],
                "password_hash": pw_hash,
                "name": u["name"],
                "role": u["role"],
                "email": f"{u['username']}@ztrace.local",
                "created_at": datetime.utcnow()
            })
            created.append(u["username"])

    sample_aps = [
        {"bssid": "00:06:AE:C9:D9:A3", "ssid": "MyDU", "floor": 3, "label": "Corridor Router (B1-93)", "rssi": -68, "status": "active", "x": 20, "y": 160},
        {"bssid": "00:06:AE:60:44:AF", "ssid": "MyDU", "floor": 3, "label": "Room 311 Router (B2-44af)", "rssi": -40, "status": "active", "x": 300, "y": 0},
        {"bssid": "00:06:AE:C1:E0:49", "ssid": "MyDU", "floor": 3, "label": "Other Side Router (B3-b3)", "rssi": -63, "status": "active", "x": 300, "y": 320},
    ]
    for ap in sample_aps:
        if not access_points_col.find_one({"bssid": ap["bssid"]}):
            access_points_col.insert_one({**ap, "created_at": datetime.utcnow()})

    sample_fps = [
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -93, "floor": 3, "area": "GATE-311", "x": 20, "y": 160},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -68, "floor": 3, "area": "GATE-311", "x": 20, "y": 160},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -46, "floor": 3, "area": "GATE-311", "x": 20, "y": 160},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -83, "floor": 3, "area": "CORNER-FL-311", "x": 60, "y": 40},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -75, "floor": 3, "area": "CORNER-FL-311", "x": 60, "y": 40},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -75, "floor": 3, "area": "CORNER-FL-311", "x": 60, "y": 40},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -72, "floor": 3, "area": "FRONT-CENTER-311", "x": 300, "y": 40},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -95, "floor": 3, "area": "FRONT-CENTER-311", "x": 300, "y": 40},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -69, "floor": 3, "area": "FRONT-CENTER-311", "x": 300, "y": 40},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -83, "floor": 3, "area": "CORNER-FR-311", "x": 540, "y": 40},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -43, "floor": 3, "area": "CORNER-FR-311", "x": 540, "y": 40},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -81, "floor": 3, "area": "CORNER-FR-311", "x": 540, "y": 40},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -92, "floor": 3, "area": "WALL-LEFT-311", "x": 60, "y": 160},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -40, "floor": 3, "area": "WALL-LEFT-311", "x": 60, "y": 160},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -70, "floor": 3, "area": "WALL-LEFT-311", "x": 60, "y": 160},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -92, "floor": 3, "area": "CENTER-311", "x": 300, "y": 160},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -74, "floor": 3, "area": "CENTER-311", "x": 300, "y": 160},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -80, "floor": 3, "area": "CENTER-311", "x": 300, "y": 160},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -33, "floor": 3, "area": "WALL-RIGHT-311", "x": 540, "y": 160},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -77, "floor": 3, "area": "WALL-RIGHT-311", "x": 540, "y": 160},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -83, "floor": 3, "area": "WALL-RIGHT-311", "x": 540, "y": 160},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -63, "floor": 3, "area": "CORNER-BL-311", "x": 60, "y": 280},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -76, "floor": 3, "area": "CORNER-BL-311", "x": 60, "y": 280},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -69, "floor": 3, "area": "CORNER-BL-311", "x": 60, "y": 280},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -83, "floor": 3, "area": "BACK-CENTER-311", "x": 300, "y": 280},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -33, "floor": 3, "area": "BACK-CENTER-311", "x": 300, "y": 280},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -77, "floor": 3, "area": "BACK-CENTER-311", "x": 300, "y": 280},
        {"bssid": "00:06:AE:C9:D9:A3", "rssi": -63, "floor": 3, "area": "CORNER-BR-311", "x": 540, "y": 280},
        {"bssid": "00:06:AE:60:44:AF", "rssi": -76, "floor": 3, "area": "CORNER-BR-311", "x": 540, "y": 280},
        {"bssid": "00:06:AE:C1:E0:49", "rssi": -76, "floor": 3, "area": "CORNER-BR-311", "x": 540, "y": 280},
    ]
    for fp in sample_fps:
        fingerprints_col.insert_one({
            "bssid": fp["bssid"],
            "rssi": fp["rssi"],
            "floor": fp["floor"],
            "area": fp["area"],
            "x": fp["x"],
            "y": fp["y"],
            "created_at": datetime.utcnow()
        })

    return jsonify({"success": True, "users_created": created})
