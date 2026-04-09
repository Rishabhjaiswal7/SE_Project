# 📡 Z-Traces — Wi-Fi Indoor Positioning System

> **Team:** ALPHACODERS  
> **Stack:** Python · Flask · MongoDB · KNN · Vanilla JS  
> **Tested at:** Room 311, DU Campus

Z-Traces is a Wi-Fi fingerprinting-based **Indoor Positioning System (IPS)** that uses RSSI signals from nearby access points and a K-Nearest Neighbours algorithm to determine a user's real-time indoor location — no GPS required.

---

## 🚀 Features

- 🔐 **Role-based authentication** — Admin, Operator, and User roles with JWT
- 📍 **Real-time localization** — KNN matching against a pre-built fingerprint database
- 🗺️ **Live floor map** — User location shown on an interactive floor plan
- 🛠️ **Operator tools** — Register access points, collect & manage Wi-Fi fingerprints
- 📊 **Admin dashboard** — View all users' location history and system statistics
- 🪟 **Windows WiFi Agent** — Native `netsh` scanner that sees ALL routers (not just the connected one)
- 🧠 **Fingerprint cache** — Backend caches fingerprint DB for fast KNN lookups

---

## 🗂️ Project Structure

```
z-traces/
│
├── app.py                    # Flask app factory, blueprint registration
├── config.py                 # App configuration (Mongo URI, JWT secret, debug)
├── requirements.txt          # Python dependencies
├── wifiagent.py              # Standalone Windows Wi-Fi scanner (Port 5001)
├── collect_fingerprints.py   # CLI tool for fingerprint collection (Room 311)
│
├── api/                      # Route blueprints
│   ├── __init__.py           # Error handler registration
│   ├── auth_routes.py        # /api/login, /api/register, /api/seed
│   ├── admin_routes.py       # /api/admin/* (Admin only)
│   ├── location_routes.py    # /api/localize, /api/location-history
│   └── data_routes.py        # /api/access-points, /api/fingerprints
│
├── core/                     # Shared utilities
│   ├── auth.py               # JWT token generation & verification helpers
│   ├── database.py           # PyMongo init, index creation
│   ├── limiter.py            # Flask-Limiter setup
│   ├── logger.py             # Centralized logging
│   ├── ml_engine.py          # KNN localization engine (fingerprint matching)
│   └── utils.py              # Common helper functions
│
├── index.html                # Login page (role selector + JWT auth)
├── user_dashboard.html       # Scan & locate UI with floor map
├── operator_dashboard.html   # AP management + fingerprint collection UI
└── admin_dashboard.html      # Full system overview + location history
```

---

## ⚙️ Prerequisites

- Python 3.9+
- MongoDB running locally on port `27017`
- Windows OS (for live Wi-Fi scanning via `netsh`)

---

## 📦 Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/z-traces.git
cd z-traces

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start MongoDB
mongod --dbpath ./data/db

# 4. Seed default users and sample data
# (Run after starting the Flask server)
curl -X POST http://localhost:5000/api/seed
```

---

## ▶️ Running the App

### Start the main Flask backend (Port 5000)
```bash
python app.py
```

### Start the Windows Wi-Fi scanner agent (Port 5001)
> Required for live scanning in the browser. Run in a **separate terminal**.
```bash
python wifiagent.py
```

Then open **http://localhost:5000** in your browser.

---

## 🔑 Default Login Credentials

> ⚠️ For development only. Change before any deployment.

| Role     | Username   | Password  |
|----------|------------|-----------|
| Admin    | `admin`    | `admin123`|
| Operator | `operator` | `op123`   |
| User     | `user`     | `user123` |

---

## 🗄️ Database Schema (MongoDB — `ztrace_db`)

| Collection      | Purpose                                      |
|-----------------|----------------------------------------------|
| `users`         | User accounts with roles                     |
| `access_points` | Registered Wi-Fi APs with floor coordinates  |
| `fingerprints`  | RSSI readings per location point (KNN data)  |
| `locations`     | Per-user location history with raw signals   |

See [`DB_SCHEMA.md`](./DB_SCHEMA.md) for full field definitions and indexes.

---

## 🌐 API Reference

| Method | Endpoint                      | Auth       | Description                  |
|--------|-------------------------------|------------|------------------------------|
| POST   | `/api/login`                  | Public     | Authenticate, returns JWT    |
| POST   | `/api/register`               | Public     | Create new user account      |
| POST   | `/api/seed`                   | Public     | Seed dev users & sample data |
| POST   | `/api/localize`               | Any        | KNN locate + save to history |
| GET    | `/api/location-history`       | Any        | Own location history         |
| GET    | `/api/admin/location-history` | Admin      | All users' history           |
| GET    | `/api/admin/stats`            | Admin      | System usage statistics      |
| GET    | `/api/admin/users`            | Admin      | List all users               |
| GET    | `/api/access-points`          | Any        | List registered APs          |
| POST   | `/api/access-points`          | Op/Admin   | Register a new AP            |
| PUT    | `/api/access-points/:id`      | Op/Admin   | Update AP details            |
| DELETE | `/api/access-points/:id`      | Op/Admin   | Remove an AP                 |
| GET    | `/api/fingerprints`           | Any        | List all fingerprints        |
| POST   | `/api/fingerprints`           | Op/Admin   | Add a fingerprint record     |
| DELETE | `/api/fingerprints/:id`       | Op/Admin   | Delete a fingerprint         |
| POST   | `/api/floor-mapping`          | Op/Admin   | Save AP positions on map     |

---

## 🧭 How It Works

1. **Fingerprint Collection** — An operator walks to predefined points in a building and records the RSSI from each known access point. These readings are stored as fingerprints in MongoDB.

2. **Localization** — When a user wants to find their location, the browser (via the WiFi Agent) scans nearby BSSIDs and RSSIs. The backend runs **K-Nearest Neighbours** against the fingerprint database to find the closest matching position.

3. **Result** — The estimated `(x, y, floor, area)` is returned and plotted on the floor map in real time.

---

## 🪟 Windows WiFi Agent

The `wifiagent.py` microservice runs on port `5001` and uses `netsh wlan show networks mode=bssid` to enumerate **all** visible access points (not just the connected one). It converts Windows' signal percentage to dBm and serves results at `GET /scan`.

```bash
python wifiagent.py
# → http://127.0.0.1:5001/scan
```

---

## 📝 Fingerprint Collection CLI

Use `collect_fingerprints.py` to walk through predefined points in a room and record RSSI readings interactively.

```bash
# 1. Get your JWT token from the browser console after admin login:
#    localStorage.getItem('zt_token')

# 2. Paste it into the TOKEN variable at the top of the script

# 3. Run the collector
python collect_fingerprints.py
```

The script guides you point-by-point, scans 3 times per position, and saves averaged readings via the REST API.

---

## 🔧 Environment Variables

| Variable    | Default                          | Description              |
|-------------|----------------------------------|--------------------------|
| `MONGO_URI` | `mongodb://localhost:27017`      | MongoDB connection string|
| `JWT_SECRET`| `ztrace_secret_change_in_prod`   | JWT signing secret       |

Set these in a `.env` file or export before running:

```bash
export JWT_SECRET="your-strong-secret-here"
export MONGO_URI="mongodb://localhost:27017"
```

---

## 🛡️ Security Notes

- JWT tokens expire after **8 hours**
- Passwords are hashed with **bcrypt**
- Rate limiting is applied via Flask-Limiter
- **Change `JWT_SECRET` and default passwords before any production or public deployment**

---

## 👥 Team

**ALPHACODERS** — Built as part of a university project on indoor positioning systems.

---

## 📄 License

This project is for academic/educational use. Not licensed for commercial deployment.