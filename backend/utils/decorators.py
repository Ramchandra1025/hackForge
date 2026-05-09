"""HackForge - Reusable Decorators"""
import logging
from functools import wraps
from flask import request, jsonify, g
from backend.utils.redis_client import get_redis
import time

logger = logging.getLogger(__name__)

def rate_limit(max_calls: int, period: int = 60, key_func=None):
    """Simple rate limiter decorator."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            r = get_redis()
            if key_func:
                rl_key = f"rl:{key_func()}"
            else:
                rl_key = f"rl:{request.remote_addr}:{f.__name__}"
            
            current = r.incr(rl_key)
            if current == 1:
                r.expire(rl_key, period)
            if current > max_calls:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            return f(*args, **kwargs)
        return decorated
    return decorator


def validate_json(*required_fields):
    """Validate that request contains JSON with required fields."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({'error': 'JSON body required'}), 400
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                return jsonify({'error': f"Missing fields: {', '.join(missing)}"}), 400
            g.json = data
            return f(*args, **kwargs)
        return decorated
    return decorator


def log_activity(action: str, resource_type: str = None):
    """Log user activity after successful request."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                if hasattr(g, 'user') and g.user:
                    from backend.utils.db import get_db
                    db = get_db()
                    if db:
                        db.table('activities').insert({
                            'user_id': g.user['id'],
                            'team_id': getattr(g, 'team_id', None),
                            'action': action,
                            'resource_type': resource_type,
                            'ip_address': request.remote_addr
                        }).execute()
            except Exception as e:
                logger.error(f"Activity log error: {e}")
            return result
        return decorated
    return decorator