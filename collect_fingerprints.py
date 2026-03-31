"""
Z-Traces — Fingerprint Collection Script
Room 311, DU Campus

HOW TO USE:
1. Flask + MongoDB chalu karo (start.bat)
2. Admin se login karo, JWT token copy karo
3. TOKEN variable mein paste karo (line 22)
4. python collect_fingerprints.py
5. Har point pe Enter dabaao — scan automatic hoga

BSSIDs fixed hain:
  Router 1 (Corridor): 00:06:AE:C9:AD:DF
  Router 2 (Room):     00:06:AE:60:44:AF
"""

import subprocess
import requests
import json
import time

# ─── CONFIG — SIRF YAHAN CHANGE KARO ─────────────────
FLASK_URL = "http://localhost:5000"
TOKEN     = "YAHAN_APNA_JWT_TOKEN_PASTE_KARO"  # browser console: localStorage.getItem('zt_token')

# Tumhare 2 fixed routers
ROUTER_CORRIDOR = "00:06:ae:c9:d9:b3"   # Door ke paas wala
ROUTER_ROOM     = "00:06:ae:60:44:af"   # Room ke andar wala

# ─── ROOM 311 KE POINTS ───────────────────────────────
# Map size: 600 x 320 pixels
# Room 311 ko humne CONF-A area mein map kiya hai
# x: 0-600, y: 0-320
#
#  [DOOR]----[AC_LEFT]----[CENTER]----[AC_RIGHT]----[TABLE]
#   x=50       x=150        x=300       x=420        x=530
#   y=160      y=80         y=160       y=80         y=240
#
POINTS = [
    {
        "name":  "DOOR",
        "area":  "DOOR-311",
        "floor": 3,
        "x":     50,
        "y":     160,
        "hint":  "Room ke darwaze pe khade ho jao"
    },
    {
        "name":  "AC_LEFT",
        "area":  "AC-LEFT-311",
        "floor": 3,
        "x":     150,
        "y":     80,
        "hint":  "Left side AC ke neeche khade ho"
    },
    {
        "name":  "CENTER",
        "area":  "CENTER-311",
        "floor": 3,
        "x":     300,
        "y":     160,
        "hint":  "Room ke bilkul beech mein khade ho"
    },
    {
        "name":  "AC_RIGHT",
        "area":  "AC-RIGHT-311",
        "floor": 3,
        "x":     420,
        "y":     80,
        "hint":  "Right side AC ke neeche khade ho"
    },
    {
        "name":  "TABLE",
        "area":  "TABLE-311",
        "floor": 3,
        "x":     530,
        "y":     240,
        "hint":  "Peeche wali tables ke paas khade ho"
    },
]

# ─────────────────────────────────────────────────────


def get_rssi_windows():
    """Get RSSI of currently connected AP"""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore"
        )
        bssid = None
        rssi  = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if "AP BSSID" in line:
                bssid = line.split(":", 1)[1].strip().upper()
            elif line.startswith("Rssi"):
                rssi = int(line.split(":", 1)[1].strip())
        return bssid, rssi
    except Exception as e:
        print(f"  [ERROR] scan failed: {e}")
        return None, None


def scan_point(point):
    """
    Scan current position 3 times and average the RSSI.
    Returns signals list with both BSSIDs.
    """
    print(f"\n  Scanning 3 times...")
    connected_readings = []

    for i in range(3):
        bssid, rssi = get_rssi_windows()
        if bssid and rssi:
            connected_readings.append((bssid, rssi))
            print(f"    Scan {i+1}: {bssid}  {rssi} dBm")
        time.sleep(1)

    if not connected_readings:
        print("  [ERROR] Koi signal nahi mila!")
        return None

    # Connected router ka average
    connected_bssid = connected_readings[0][0]
    avg_rssi = int(sum(r for _, r in connected_readings) / len(connected_readings))

    # Determine which router is connected and which is the other
    if ROUTER_CORRIDOR.upper() in connected_bssid:
        r1_bssid = ROUTER_CORRIDOR.upper()
        r1_rssi  = avg_rssi
        r2_bssid = ROUTER_ROOM.upper()
        # Estimate other router RSSI (will be weaker)
        r2_rssi  = manually_enter_second_rssi(r2_bssid)
    else:
        r2_bssid = ROUTER_ROOM.upper()
        r2_rssi  = avg_rssi
        r1_bssid = ROUTER_CORRIDOR.upper()
        r1_rssi  = manually_enter_second_rssi(r1_bssid)

    signals = [
        {"bssid": r1_bssid, "rssi": r1_rssi},
        {"bssid": r2_bssid, "rssi": r2_rssi},
    ]

    print(f"\n  Final readings:")
    print(f"    Corridor Router ({ROUTER_CORRIDOR}): {r1_rssi} dBm")
    print(f"    Room Router     ({ROUTER_ROOM}):     {r2_rssi} dBm")

    return signals


def manually_enter_second_rssi(bssid):
    """
    Second router connected nahi hai — manually enter karo
    Ya estimate karte hain based on position
    """
    print(f"\n  ⚠️  {bssid} connected nahi hai")
    print(f"  Iska RSSI manually enter karo")
    print(f"  (WiFi Analyzer app se dekho, ya estimate: door hai toh -80 to -90)")
    while True:
        try:
            val = input(f"  RSSI value enter karo (e.g. -75): ").strip()
            rssi = int(val)
            if -100 <= rssi <= -20:
                return rssi
            print("  Valid range: -20 to -100")
        except ValueError:
            print("  Sirf number enter karo jaise -75")


def save_fingerprints(point, signals):
    """Save fingerprints to DB via API"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    saved = 0
    for sig in signals:
        payload = {
            "bssid": sig["bssid"],
            "rssi":  sig["rssi"],
            "floor": point["floor"],
            "area":  point["area"],
            "x":     point["x"],
            "y":     point["y"]
        }
        try:
            res = requests.post(
                f"{FLASK_URL}/api/fingerprints",
                json=payload,
                headers=headers,
                timeout=5
            )
            if res.status_code == 201:
                saved += 1
                print(f"  ✅ Saved: {sig['bssid']} → {point['area']}")
            else:
                print(f"  ❌ Failed: {res.status_code} — {res.text}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    return saved


def setup_access_points():
    """Register the 2 routers as Access Points if not already done"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    aps = [
        {
            "bssid":  ROUTER_CORRIDOR,
            "ssid":   "MyDU",
            "floor":  3,
            "label":  "Corridor Router",
            "rssi":   -70,
            "status": "active",
            "x":      50,
            "y":      160
        },
        {
            "bssid":  ROUTER_ROOM,
            "ssid":   "MyDU",
            "floor":  3,
            "label":  "Room 311 Router",
            "rssi":   -45,
            "status": "active",
            "x":      300,
            "y":      80
        }
    ]

    print("\n[SETUP] Access Points register kar rahe hain...")
    for ap in aps:
        try:
            res = requests.post(
                f"{FLASK_URL}/api/access-points",
                json=ap,
                headers=headers,
                timeout=5
            )
            if res.status_code == 201:
                print(f"  ✅ AP registered: {ap['label']}")
            elif res.status_code == 409:
                print(f"  ℹ️  AP already exists: {ap['label']}")
            else:
                print(f"  ❌ Failed: {ap['label']} — {res.text}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


def clear_old_fingerprints():
    """Optional: Clear old seed fingerprints"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.get(
            f"{FLASK_URL}/api/fingerprints",
            headers=headers,
            timeout=5
        )
        if res.ok:
            fps = res.json()
            print(f"\n  Found {len(fps)} existing fingerprints")
            if fps:
                confirm = input("  Purane fingerprints delete karo? (y/n): ").strip().lower()
                if confirm == 'y':
                    for fp in fps:
                        requests.delete(
                            f"{FLASK_URL}/api/fingerprints/{fp['_id']}",
                            headers=headers,
                            timeout=5
                        )
                    print(f"  ✅ {len(fps)} fingerprints deleted")
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  Z-Traces Fingerprint Collector — Room 311")
    print("=" * 55)

    # Token check
    if TOKEN == "YAHAN_APNA_JWT_TOKEN_PASTE_KARO":
        print("\n❌ TOKEN set nahi kiya!")
        print("   Steps:")
        print("   1. Browser mein admin login karo")
        print("   2. F12 → Console tab kholo")
        print("   3. Yeh type karo: localStorage.getItem('zt_token')")
        print("   4. Jo value aaye woh is script mein TOKEN variable mein paste karo")
        exit(1)

    # Flask check
    try:
        requests.get(f"{FLASK_URL}/api/access-points",
                     headers={"Authorization": f"Bearer {TOKEN}"},
                     timeout=3)
        print("\n✅ Flask server connected")
    except:
        print("\n❌ Flask server nahi chal raha!")
        print("   start.bat chalao pehle")
        exit(1)

    # Step 1: Access Points setup
    setup_access_points()

    # Step 2: Old data clear karne ka option
    clear_old_fingerprints()

    # Step 3: Har point pe scan
    print("\n" + "=" * 55)
    print("  FINGERPRINT COLLECTION SHURU")
    print("  Room 311 mein 5 points pe scan karenge")
    print("=" * 55)

    total_saved = 0

    for i, point in enumerate(POINTS):
        print(f"\n{'─'*55}")
        print(f"  Point {i+1}/{len(POINTS)}: {point['name']}")
        print(f"  Area: {point['area']}")
        print(f"  Map coords: x={point['x']}, y={point['y']}, floor={point['floor']}")
        print(f"\n  👉 {point['hint']}")
        print(f"{'─'*55}")

        input("\n  Sahi jagah pe khade ho jao aur Enter dabaao...")

        signals = scan_point(point)

        if signals:
            confirm = input(f"\n  Yeh data save karo? (y/n): ").strip().lower()
            if confirm == 'y':
                saved = save_fingerprints(point, signals)
                total_saved += saved
                print(f"  ✅ Point {point['name']} done! ({saved} fingerprints saved)")
            else:
                print(f"  ⏭️  Skipped")
        else:
            print(f"  ❌ Scan failed — point skip kar rahe hain")

        print()

    # Summary
    print("\n" + "=" * 55)
    print(f"  COLLECTION COMPLETE!")
    print(f"  Total fingerprints saved: {total_saved}")
    print(f"  Total points covered: {len(POINTS)}")
    print("=" * 55)
    print("\n  Ab user dashboard pe 'Scan & Locate' karo")
    print("  Admin dashboard pe live location dikhni chahiye!")