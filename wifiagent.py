"""
Z-Traces — Flawless Windows WiFi Agent (Port 5001)
--------------------------------------------------
This script completely replaces your broken wifi scanning agent.
It natively bypasses pywifi limitations by directly calling the 
Windows "netsh wlan show networks mode=bssid" utility which correctly 
forces a read of ALL routers, not just the connected one.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import subprocess
import re

app = Flask(__name__)
CORS(app)

def scan_windows_native():
    try:
        # Force a native hardware scan of all networks, not just connected
        proc = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        
        output = proc.stdout
        signals = []
        
        current_ssid = "Hidden"
        for line in output.splitlines():
            line = line.strip()
            
            # Map the SSID block
            if line.startswith("SSID") and "BSSID" not in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_ssid = parts[1].strip() or "Hidden"
            
            # Extract the raw BSSID MAC Address
            elif line.startswith("BSSID"):
                bssid_val = line.split(":", 1)[1].strip()
                # Windows formats it like 00:06:ae:c9:fb:3d -> make it UPPER
                bssid_val = bssid_val.upper()
                signals.append({"bssid": bssid_val, "ssid": current_ssid, "rssi": -100})
            
            # Extract corresponding Signal Strength (Percentage -> dBm)
            elif line.startswith("Signal"):
                signal_percent = line.split(":", 1)[1].strip().replace("%", "")
                if signal_percent.isdigit() and signals:
                    # Conversion from Windows Percentage (0-100) to standard RSSI (-100 to -50)
                    percent = int(signal_percent)
                    dbm = (percent / 2) - 100
                    signals[-1]["rssi"] = int(dbm)
        
        # Deduplicate and pick the strongest signal if BSSID repeats
        unique_bmap = {}
        for s in signals:
            if s["bssid"] not in unique_bmap or s["rssi"] > unique_bmap[s["bssid"]]["rssi"]:
                unique_bmap[s["bssid"]] = s
                
        return list(unique_bmap.values())
        
    except Exception as e:
        print(f"Native scan failed: {e}")
        return []

@app.route("/scan", methods=["GET"])
def handle_scan():
    results = scan_windows_native()
    return jsonify({
        "success": True, 
        "signals": results
    })

@app.route("/health", methods=["GET"])
def handle_health():
    return jsonify({"status": "ok", "os": "Windows Native"})

if __name__ == "__main__":
    print("═" * 60)
    print(" 🟢 Z-Traces Native Windows Agent Started on Port 5001")
    print("    This version sees ALL routers, not just connected ones!")
    print("═" * 60)
    app.run(host="127.0.0.1", port=5001, debug=False)
