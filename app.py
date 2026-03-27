"""
Z-Traces Backend API
Team: ALPHACODERS
Stack: Python Flask + PyMongo (MongoDB)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import bcrypt
import jwt
import os
import numpy as np
from functools import wraps

# ─── App & Config ────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
JWT_SECRET = os.environ.get("JWT_SECRET", "ztrace_secret_change_in_prod")
JWT_EXPIRY_HOURS = 8

# ─── MongoDB Connection ───────────────────────────────────────────
client = MongoClient(MONGO_URI)
db = client["ztrace_db"]

# Collections
users_col        = db["users"]
access_points_col = db["access_points"]
fingerprints_col  = db["fingerprints"]
locations_col     = db["locations"]

# Indexes
users_col.create_index("username", unique=True)
access_points_col.create_index("bssid", unique=True)
fingerprints_col.create_index([("bssid", 1), ("floor", 1)])
locations_col.create_index([("user_id", 1), ("timestamp", -1)])


# ─── Helpers ─────────────────────────────────────────────────────
def serialize(obj):
    """Convert MongoDB document to JSON-serializable dict."""
    if isinstance(obj, list):
        return [serialize(o) for o in obj]
    if isinstance(obj, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    v.isoformat() if isinstance(v, datetime) else
                    serialize(v)) for k, v in obj.items()}
    return obj


def make_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(roles=None):
    """Decorator: JWT auth + optional role guard."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "Missing token"}), 401
            payload = decode_token(auth.split(" ", 1)[1])
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            request.user_id = payload["sub"]
            request.user_role = payload["role"]
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─── Serve Frontend ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)


# ═══════════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    role     = data.get("role", "user")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400

    user = users_col.find_one({"username": username})
    if not user:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"]):
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    if user["role"] != role:
        return jsonify({"success": False, "message": f"Account is not a {role}"}), 403

    token = make_token(str(user["_id"]), user["role"])
    return jsonify({
        "success": True,
        "token": token,
        "role": user["role"],
        "user": {"name": user["name"], "email": user.get("email", ""), "role": user["role"]}
    })


@app.route("/api/register", methods=["POST"])
def register():
    """Admin/operator endpoint to create users."""
    data = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    name     = data.get("name", "")
    email    = data.get("email", "")
    role     = data.get("role", "user")

    if not all([username, password, name]):
        return jsonify({"error": "username, password, name required"}), 400
    if role not in ("user", "admin", "operator"):
        return jsonify({"error": "Invalid role"}), 400

    if users_col.find_one({"username": username}):
        return jsonify({"error": "Username already taken"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    result  = users_col.insert_one({
        "username": username,
        "password_hash": pw_hash,
        "name": name,
        "email": email,
        "role": role,
        "created_at": datetime.utcnow()
    })
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201



# ═══════════════════════════════════════════════════════════════════
#  LOCALIZATION  (KNN fingerprinting)
# ═══════════════════════════════════════════════════════════════════

def knn_localize(scan_signals: list[dict], k: int = 3) -> dict:
    """
    KNN-based Wi-Fi fingerprint matching (FR-07).

    scan_signals: [{"bssid": "AA:BB:...", "rssi": -55}, ...]
    Returns: {"floor": int, "x": int, "y": int, "area": str}
    """
    scan_map = {s["bssid"]: s["rssi"] for s in scan_signals}
    fingerprints = list(fingerprints_col.find({}))

    if not fingerprints:
        return {"floor": 1, "x": 300, "y": 120, "area": "Unknown"}

    # Group fingerprints by area+floor → reference points
    ref_points: dict[tuple, dict] = {}
    for fp in fingerprints:
        key = (fp["floor"], fp.get("area", "?"))
        if key not in ref_points:
            ref_points[key] = {"floor": fp["floor"], "area": fp.get("area", "?"),
                                "x": fp.get("x", 300), "y": fp.get("y", 120), "signals": {}}
        ref_points[key]["signals"][fp["bssid"]] = fp["rssi"]

    distances = []
    for key, rp in ref_points.items():
        common = set(scan_map) & set(rp["signals"])
        if not common:
            continue
        dist = np.sqrt(sum((scan_map[b] - rp["signals"][b])**2 for b in common))
        distances.append((dist, rp))

    if not distances:
        return {"floor": 1, "x": 300, "y": 120, "area": "Unknown"}

    distances.sort(key=lambda d: d[0])
    top_k = distances[:k]

    # Weighted average (1/distance)
    total_w = sum(1 / (d[0] + 1e-6) for d, _ in top_k)
    floor_votes: dict[int, float] = {}
    area_votes: dict[str, float] = {}
    wx, wy = 0.0, 0.0

    for dist, rp in top_k:
        w = (1 / (dist + 1e-6)) / total_w
        floor_votes[rp["floor"]] = floor_votes.get(rp["floor"], 0) + w
        area_votes[rp["area"]]   = area_votes.get(rp["area"], 0) + w
        wx += w * rp.get("x", 300)
        wy += w * rp.get("y", 120)

    best_floor = max(floor_votes, key=floor_votes.get)
    best_area  = max(area_votes, key=area_votes.get)

    return {"floor": best_floor, "x": int(wx), "y": int(wy), "area": best_area}


@app.route("/api/localize", methods=["POST"])
@require_auth()
def localize():
    """
    Main localization endpoint — called by user dashboard 'Scan & Locate'.
    Runs KNN on submitted signals, saves result to DB, returns location.
    """
    data    = request.get_json() or {}
    signals = data.get("signals", [])

    if not signals:
        return jsonify({"error": "No signals provided"}), 400

    loc = knn_localize(signals)

    # Save to location history only for role=user
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


@app.route("/api/admin/live-users", methods=["GET"])
@require_auth(["admin"])
def get_live_users():
    users = list(users_col.find({"role": "user"}))  # only users

    result = []

    for u in users:
        last_loc = locations_col.find_one(
            {"user_id": u["_id"]},
            sort=[("timestamp", -1)]
        )

        if last_loc:
            result.append({
                "name": u["name"],
                "user_id": str(u["_id"]),
                "floor": last_loc.get("floor"),
                "x": last_loc.get("x"),
                "y": last_loc.get("y"),
                "area": last_loc.get("area"),
                "timestamp": last_loc.get("timestamp")
            })

    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════
#  LOCATION HISTORY  (FR-03)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/location-history", methods=["GET"])
@require_auth()
def get_location_history():
    limit = int(request.args.get("limit", 50))
    records = list(
        locations_col.find({"user_id": ObjectId(request.user_id)})
        .sort("timestamp", -1).limit(limit)
    )
    return jsonify(serialize(records))


@app.route("/api/location-history", methods=["POST"])
@require_auth()
def post_location_history():
    """Allow client to manually POST a location record."""
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


@app.route("/api/user/heartbeat", methods=["POST"])
@require_auth()
def user_heartbeat():
    """
    Called automatically every 30s from user dashboard.
    ONLY saves location for role=user accounts — admin/operator ignored.
    """
    # Block admin and operator from polluting location data
    if request.user_role != "user":
        return jsonify({"success": False, "message": "Heartbeat only for users"}), 403
    data = request.get_json() or {}
    signals = data.get("signals", [])

    # If signals provided, run KNN localization
    if signals:
        loc = knn_localize(signals)
    else:
        # Use last known location if no signals
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
        "signals":   signals,
        "timestamp": datetime.utcnow()
    })
    return jsonify({"success": True, "location": loc})


@app.route("/api/admin/location-history", methods=["GET"])
@require_auth(roles=["admin"])
def admin_location_history():
    """Admin: only USERS' (role=user) location history with optional filters."""
    floor_filter  = request.args.get("floor")
    user_filter   = request.args.get("user_id")
    limit = int(request.args.get("limit", 100))

    # Get only user-role accounts
    user_ids = [u["_id"] for u in users_col.find({"role": "user"}, {"_id": 1})]

    query = {"user_id": {"$in": user_ids}}
    if floor_filter:
        query["floor"] = int(floor_filter)
    if user_filter:
        try:
            query["user_id"] = ObjectId(user_filter)
        except Exception:
            pass

    records = list(locations_col.find(query).sort("timestamp", -1).limit(limit))
    # Enrich with user info
    for r in records:
        u = users_col.find_one({"_id": r["user_id"]}, {"name": 1})
        r["user_name"] = u["name"] if u else "Unknown"

    return jsonify(serialize(records))


# ═══════════════════════════════════════════════════════════════════
#  ADMIN: STATISTICS  (FR-04)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/admin/stats", methods=["GET"])
@require_auth(roles=["admin"])
def admin_stats():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users        = users_col.count_documents({})
    localizations_today = locations_col.count_documents({"timestamp": {"$gte": today_start}})
    active_aps         = access_points_col.count_documents({"status": "active"})

    # Simple avg rpm (last 10 min)
    ten_min_ago  = datetime.utcnow() - timedelta(minutes=10)
    recent_count = locations_col.count_documents({"timestamp": {"$gte": ten_min_ago}})
    avg_rpm      = round(recent_count / 10, 1)

    return jsonify({
        "total_users": total_users,
        "localizations_today": localizations_today,
        "active_aps": active_aps,
        "avg_rpm": avg_rpm
    })


@app.route("/api/admin/live-locations", methods=["GET"])
@require_auth(roles=["admin"])
def admin_live_locations():
    """
    Returns the LATEST location of USERS only (role=user).
    Admin dashboard polls this every 5s for live tracking.
    """
    all_users = list(users_col.find({"role": "user"}, {"password_hash": 0}))
    result = []
    for u in all_users:
        latest = locations_col.find_one(
            {"user_id": u["_id"]},
            sort=[("timestamp", -1)]
        )
        if not latest:
            continue
        result.append({
            "user_id":   str(u["_id"]),
            "user_name": u.get("name", u.get("username", "Unknown")),
            "role":      u.get("role", "user"),
            "floor":     latest.get("floor", 1),
            "x":         latest.get("x", 0),
            "y":         latest.get("y", 0),
            "area":      latest.get("area", "—"),
            "timestamp": latest["timestamp"].isoformat() if latest.get("timestamp") else None,
        })
    return jsonify(result)


@app.route("/api/admin/users", methods=["GET"])
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


# ═══════════════════════════════════════════════════════════════════
#  ACCESS POINTS  (FR-05 / FR-06)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/access-points", methods=["GET"])
@require_auth()
def list_aps():
    floor_filter = request.args.get("floor")
    query = {}
    if floor_filter:
        query["floor"] = int(floor_filter)
    aps = list(access_points_col.find(query))
    return jsonify(serialize(aps))


@app.route("/api/access-points", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def create_ap():
    data = request.get_json()
    required = ["bssid", "ssid", "floor"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    if access_points_col.find_one({"bssid": data["bssid"]}):
        return jsonify({"error": "BSSID already exists"}), 409

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
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


@app.route("/api/access-points/<ap_id>", methods=["PUT"])
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


@app.route("/api/access-points/<ap_id>", methods=["DELETE"])
@require_auth(roles=["operator", "admin"])
def delete_ap(ap_id):
    access_points_col.delete_one({"_id": ObjectId(ap_id)})
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════
#  FINGERPRINTS  (FR-06, FR-07)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/fingerprints", methods=["GET"])
@require_auth()
def list_fingerprints():
    floor_filter = request.args.get("floor")
    query = {}
    if floor_filter:
        query["floor"] = int(floor_filter)
    fps = list(fingerprints_col.find(query).limit(500))
    return jsonify(serialize(fps))


@app.route("/api/fingerprints", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def create_fingerprint():
    data = request.get_json()
    required = ["bssid", "rssi", "floor"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    # Verify AP exists
    ap = access_points_col.find_one({"bssid": data["bssid"]})
    if not ap:
        return jsonify({"error": "BSSID not found in access points"}), 404

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
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


@app.route("/api/fingerprints/<fp_id>", methods=["DELETE"])
@require_auth(roles=["operator", "admin"])
def delete_fingerprint(fp_id):
    fingerprints_col.delete_one({"_id": ObjectId(fp_id)})
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════
#  FLOOR MAPPING  (FR-05)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/floor-mapping", methods=["POST"])
@require_auth(roles=["operator", "admin"])
def save_floor_mapping():
    data = request.get_json()
    floor     = int(data.get("floor", 1))
    positions = data.get("positions", [])  # [{bssid, x, y}, ...]

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


# ═══════════════════════════════════════════════════════════════════
#  SEED DATA (dev only)
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/seed", methods=["POST"])
def seed_db():
    """Insert default users and sample APs for development."""
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

    # Sample APs
    sample_aps = [
        {"bssid": "AA:BB:CC:11:22:33", "ssid": "CampusNet-5G", "floor": 1, "label": "LAB-101", "rssi": -42, "status": "active", "x": 140, "y": 70},
        {"bssid": "AA:BB:CC:44:55:66", "ssid": "CampusNet-2G", "floor": 1, "label": "LOBBY",   "rssi": -58, "status": "active", "x": 280, "y": 180},
        {"bssid": "DD:EE:FF:77:88:99", "ssid": "LibraryWiFi",  "floor": 2, "label": "LIBRARY", "rssi": -65, "status": "active", "x": 200, "y": 160},
        {"bssid": "11:22:33:AA:BB:CC", "ssid": "Admin-Net",    "floor": 3, "label": "STAFF",   "rssi": -72, "status": "active", "x": 480, "y": 70},
    ]
    for ap in sample_aps:
        if not access_points_col.find_one({"bssid": ap["bssid"]}):
            access_points_col.insert_one({**ap, "created_at": datetime.utcnow()})

    # Sample fingerprints for KNN
    sample_fps = [
        {"bssid": "AA:BB:CC:11:22:33", "rssi": -42, "floor": 1, "area": "LAB-101", "x": 90, "y": 70},
        {"bssid": "AA:BB:CC:44:55:66", "rssi": -75, "floor": 1, "area": "LAB-101", "x": 90, "y": 70},
        {"bssid": "AA:BB:CC:44:55:66", "rssi": -50, "floor": 1, "area": "LOBBY",   "x": 280, "y": 180},
        {"bssid": "AA:BB:CC:11:22:33", "rssi": -70, "floor": 1, "area": "LOBBY",   "x": 280, "y": 180},
        {"bssid": "DD:EE:FF:77:88:99", "rssi": -55, "floor": 2, "area": "LIBRARY", "x": 200, "y": 160},
        {"bssid": "11:22:33:AA:BB:CC", "rssi": -60, "floor": 3, "area": "STAFF",   "x": 480, "y": 70},
    ]
    for fp in sample_fps:
        fingerprints_col.insert_one({**fp, "created_at": datetime.utcnow()})

    return jsonify({"success": True, "users_created": created})


# ─── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)