from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Isolated limiter instance to avoid circular imports in Blueprints.
# Global default is generous (2000 per hour), but we will enforce strict limits on specific endpoints.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per hour", "200 per minute"],
    storage_uri="memory://"
)