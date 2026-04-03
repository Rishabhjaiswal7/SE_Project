from pymongo import MongoClient
from config import Config
from core.logger import log

client = MongoClient(Config.MONGO_URI)
db = client["ztrace_db"]

users_col        = db["users"]
access_points_col = db["access_points"]
fingerprints_col  = db["fingerprints"]
locations_col     = db["locations"]

def init_db():
    log.info("Initializing Database Indexes...")
    users_col.create_index("username", unique=True)
    access_points_col.create_index("bssid", unique=True)
    fingerprints_col.create_index([("bssid", 1), ("floor", 1)])
    locations_col.create_index([("user_id", 1), ("timestamp", -1)])
