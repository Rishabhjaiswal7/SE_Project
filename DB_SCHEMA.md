# Z-Traces — MongoDB Schema Documentation
**Database:** `ztrace_db`  
**Team:** ALPHACODERS | Version 1.1

---

## Collections

### 1. `users`
Stores all system users (Admin, User, Operator). Maps to **Section 5.1.1** of SRS.

```json
{
  "_id":           ObjectId,
  "username":      String,       // unique, lowercase
  "password_hash": BinData,      // bcrypt hash
  "name":          String,
  "email":         String,
  "role":          String,       // "user" | "admin" | "operator"
  "created_at":    Date
}
```
**Indexes:** `username` (unique)

---

### 2. `access_points`
Wi-Fi access points used for localization. Maps to **Section 5.1.2** of SRS.

```json
{
  "_id":        ObjectId,
  "bssid":      String,    // unique MAC address, PK
  "ssid":       String,    // network name
  "floor":      Number,    // floor number
  "label":      String,    // area/room description
  "rssi":       Number,    // reference signal strength
  "status":     String,    // "active" | "inactive"
  "x":          Number,    // x coordinate on floor map
  "y":          Number,    // y coordinate on floor map
  "created_at": Date
}
```
**Indexes:** `bssid` (unique)

---

### 3. `fingerprints`
Wi-Fi signal fingerprints for KNN matching. Maps to **Section 5.1.4** of SRS.

```json
{
  "_id":        ObjectId,
  "bssid":      String,    // FK → access_points.bssid
  "rssi":       Number,    // stored signal strength at this position
  "floor":      Number,
  "area":       String,    // e.g. "LAB-101", "LOBBY"
  "x":          Number,    // indoor x coordinate (metres)
  "y":          Number,    // indoor y coordinate (metres)
  "created_at": Date
}
```
**Indexes:** `(bssid, floor)` compound

---

### 4. `locations`
Location history for each user. Maps to **Section 5.1.3** of SRS.

```json
{
  "_id":       ObjectId,
  "user_id":   ObjectId,  // FK → users._id
  "floor":     Number,
  "x":         Number,
  "y":         Number,
  "area":      String,
  "signals":   Array,     // raw scan: [{bssid, rssi}, ...]
  "timestamp": Date
}
```
**Indexes:** `(user_id, timestamp DESC)`

---

## Relationships (SRS Section 5.1.5)

```
users (1) ────────── (*) locations
access_points (1) ── (*) fingerprints
```

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB (local)
mongod --dbpath ./data/db

# Seed default users & sample data
curl -X POST http://localhost:5000/api/seed

# Run Flask
python app.py
```

### Default Login Credentials (dev only)

| Role     | Username   | Password   |
|----------|------------|------------|
| Admin    | admin      | admin123   |
| Operator | operator   | op123      |
| User     | user       | user123    |

---

## API Endpoints Summary

| Method | Endpoint                        | Auth       | Description                  |
|--------|---------------------------------|------------|------------------------------|
| POST   | /api/login                      | Public     | Authenticate user            |
| POST   | /api/register                   | Public     | Create new account           |
| POST   | /api/localize                   | Any        | KNN localize + save history  |
| GET    | /api/location-history           | Any        | Own location history         |
| POST   | /api/location-history           | Any        | Manual location record       |
| GET    | /api/admin/location-history     | Admin      | All users' history           |
| GET    | /api/admin/stats                | Admin      | Usage statistics             |
| GET    | /api/admin/users                | Admin      | List users                   |
| GET    | /api/access-points              | Any        | List access points           |
| POST   | /api/access-points              | Op/Admin   | Register new AP              |
| PUT    | /api/access-points/:id          | Op/Admin   | Update AP                    |
| DELETE | /api/access-points/:id          | Op/Admin   | Remove AP                    |
| GET    | /api/fingerprints               | Any        | List fingerprints            |
| POST   | /api/fingerprints               | Op/Admin   | Add fingerprint              |
| DELETE | /api/fingerprints/:id           | Op/Admin   | Remove fingerprint           |
| POST   | /api/floor-mapping              | Op/Admin   | Save AP positions on floor   |
| POST   | /api/seed                       | Public     | Seed dev data                |
