from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import math
import random

app = Flask(__name__)
app.secret_key = "ztraces_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)

# -------------------------
# DATABASE MODELS
# -------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))  # admin or user
    current_location = db.Column(db.String(100))
    floor = db.Column(db.String(50))
    room = db.Column(db.String(50))

class Fingerprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100))
    floor = db.Column(db.String(50))
    room = db.Column(db.String(50))
    rssi1 = db.Column(db.Integer)
    rssi2 = db.Column(db.Integer)
    rssi3 = db.Column(db.Integer)


# -------------------------
# INITIAL SETUP
# -------------------------

with app.app_context():
    db.create_all()

    # Create default users
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password="admin123", role="admin")
        user = User(username="user", password="user123", role="user")
        db.session.add(admin)
        db.session.add(user)
        db.session.commit()

    # Insert fingerprint demo data
    if not Fingerprint.query.first():
        fp1 = Fingerprint(
            location="Room101",
            floor="1st",
            room="101",
            rssi1=-45,
            rssi2=-50,
            rssi3=-48
        )

        fp2 = Fingerprint(
            location="Lab202",
            floor="2nd",
            room="202",
            rssi1=-55,
            rssi2=-52,
            rssi3=-49
        )

        db.session.add(fp1)
        db.session.add(fp2)
        db.session.commit()


# -------------------------
# LOGIN
# -------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session["user"] = user.username
            session["role"] = user.role

            if user.role == "admin":
                return redirect("/admin")
            else:
                return redirect("/user")

    return render_template("login.html")

# -------------------------
# ADMIN DASHBOARD
# -------------------------

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    searched_user = None

    if request.method == "POST":
        username = request.form["username"]
        searched_user = User.query.filter_by(username=username).first()

    return render_template("admin.html", user=searched_user)

#location

def detect_location():
    # Simulated live RSSI scan
    r1 = random.randint(-60, -40)
    r2 = random.randint(-60, -40)
    r3 = random.randint(-60, -40)

    fingerprints = Fingerprint.query.all()

    min_distance = float("inf")
    best_match = None

    for fp in fingerprints:
        dist = calculate_distance(fp, r1, r2, r3)

        if dist < min_distance:
            min_distance = dist
            best_match = fp

    return best_match

# -------------------------
# USER DASHBOARD
# -------------------------

@app.route("/user")
def user_dashboard():
    if session.get("role") != "user":
        return redirect("/")

    user = User.query.filter_by(username=session["user"]).first()

    location = detect_location()

    if location:
        user.current_location = location.location
        user.floor = location.floor
        user.room = location.room
        db.session.commit()

    return render_template("user.html", user=user)


# -------------------------
# LOGOUT
# -------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------------

if __name__ == "__main__":
    app.run(debug=True)
