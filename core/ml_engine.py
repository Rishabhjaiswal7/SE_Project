import time
import numpy as np
from core.database import fingerprints_col
from core.logger import log

FP_CACHE = {"data": [], "last_updated": 0}

def get_fingerprints_cached():
    now = time.time()
    if now - FP_CACHE["last_updated"] > 60:
        FP_CACHE["data"] = list(fingerprints_col.find({}))
        FP_CACHE["last_updated"] = now
        log.info(f"Refreshed fingerprint cache with {len(FP_CACHE['data'])} records.")
    return FP_CACHE["data"]

def knn_localize(scan_signals: list[dict], k: int = 3) -> dict:
    scan_map = {s["bssid"]: s["rssi"] for s in scan_signals if s["rssi"] >= -90}
    fingerprints = get_fingerprints_cached()
    
    if not fingerprints or not scan_map:
        return {"floor": None, "x": None, "y": None, "area": "Out of Range"}

    fp_bssids = set(fp["bssid"] for fp in fingerprints)
    if not set(scan_map.keys()).intersection(fp_bssids):
        # The scanner picked up completely unrelated networks
        return {"floor": None, "x": None, "y": None, "area": "Out of Range"}

    ref_points = {}
    for fp in fingerprints:
        key = (fp["floor"], fp.get("area", "?"))
        if key not in ref_points:
            ref_points[key] = {
                "floor": fp["floor"], "area": fp.get("area", "?"),
                "x": fp.get("x", 300), "y": fp.get("y", 120), "signals": {}
            }
        bssid = fp["bssid"]
        if bssid not in ref_points[key]["signals"]:
            ref_points[key]["signals"][bssid] = []
        ref_points[key]["signals"][bssid].append(fp["rssi"])
        
    for rp in ref_points.values():
        for bssid, rssi_list in rp["signals"].items():
            rp["signals"][bssid] = sum(rssi_list) / len(rssi_list)

    distances = []
    for key, rp in ref_points.items():
        all_bssids = set(scan_map.keys()) | set(rp["signals"].keys())
        if not all_bssids:
            continue
        dist_sq = 0.0
        for b in all_bssids:
            s_rssi = scan_map.get(b, -100)
            rp_rssi = rp["signals"].get(b, -100)
            dist_sq += (s_rssi - rp_rssi) ** 2
        distances.append((np.sqrt(dist_sq), rp))

    if not distances:
        return {"floor": None, "x": None, "y": None, "area": "Out of Range"}

    distances.sort(key=lambda d: d[0])
    top_k = distances[:k]

    floor_votes = {}
    for dist, rp in top_k:
        w = 1 / (dist + 1e-6)
        floor_votes[rp["floor"]] = floor_votes.get(rp["floor"], 0) + w
        
    best_floor = max(floor_votes, key=floor_votes.get)
    valid_neighbors = [(d, rp) for d, rp in top_k if rp["floor"] == best_floor]
    
    total_w = sum(1 / (d + 1e-6) for d, _ in valid_neighbors)
    area_votes = {}
    wx, wy = 0.0, 0.0

    for dist, rp in valid_neighbors:
        w = (1 / (dist + 1e-6)) / total_w
        area_votes[rp["area"]] = area_votes.get(rp["area"], 0) + w
        wx += w * rp.get("x", 300)
        wy += w * rp.get("y", 120)

    best_area = max(area_votes, key=area_votes.get) if area_votes else "Unknown"
    return {"floor": best_floor, "x": int(wx), "y": int(wy), "area": best_area}
