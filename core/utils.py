from bson import ObjectId
from datetime import datetime

def serialize(obj):
    if isinstance(obj, list):
        return [serialize(o) for o in obj]
    if isinstance(obj, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    v.isoformat() if isinstance(v, datetime) else
                    serialize(v)) for k, v in obj.items()}
    return obj
