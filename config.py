import os

class Config:
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    JWT_SECRET = os.environ.get("JWT_SECRET", "ztrace_secret_change_in_prod")
    JWT_EXPIRY_HOURS = 8     
    DEBUG = True
