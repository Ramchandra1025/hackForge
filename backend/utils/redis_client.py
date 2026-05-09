"""Redis client utilities"""
import redis
import os
import json
import time
from backend.utils.logger import get_logger

logger = get_logger(__name__)
redis_client = None


class InMemoryRedis:
    """A lightweight in-memory Redis-compatible fallback for local development and tests.

    Implements a subset of the redis-py API used by the project so code can
    operate against a dict-backed store when a real Redis server is not available.
    """

    def __init__(self):
        self.store = {}
        self._expires = {}

    # ── EXPIRY HELPERS ─────────────────────
    def _purge_expired(self, key=None):
        now = time.time()
        keys = [key] if key else list(self._expires.keys())
        for k in keys:
            exp = self._expires.get(k)
            if exp is not None and exp <= now:
                self.store.pop(k, None)
                self._expires.pop(k, None)

    # ── BASIC KV ─────────────────────────────
    def ping(self):
        return True

    def get(self, key):
        self._purge_expired(key)
        return self.store.get(key)

    def set(self, key, value):
        # mirror redis-py: store raw value
        self.store[key] = value
        self._expires.pop(key, None)

    def setex(self, key, ttl, value):
        self.store[key] = value
        if ttl is not None:
            self._expires[key] = time.time() + int(ttl)
        else:
            self._expires.pop(key, None)

    def delete(self, key):
        existed = self.store.pop(key, None) is not None
        self._expires.pop(key, None)
        return 1 if existed else 0

    def exists(self, key):
        self._purge_expired(key)
        return 1 if key in self.store else 0

    def ttl(self, key):
        self._purge_expired(key)
        if key not in self.store:
            return -2
        exp = self._expires.get(key)
        if exp is None:
            return -1
        return max(0, int(exp - time.time()))

    def flushdb(self):
        self.store.clear()
        self._expires.clear()
        return True

    # ── HASH SUPPORT ─────────────────────────
    def hget(self, name, field):
        self._purge_expired(name)
        bucket = self.store.get(name)
        if isinstance(bucket, dict):
            return bucket.get(field)
        return None

    def hset(self, name, key=None, value=None, mapping=None):
        # Support both hset(name, key, value) and hset(name, mapping=mapping)
        if mapping is not None:
            if name not in self.store or not isinstance(self.store.get(name), dict):
                self.store[name] = {}
            for k, v in mapping.items():
                self.store[name][k] = v
            return True
        if name not in self.store or not isinstance(self.store.get(name), dict):
            self.store[name] = {}
        self.store[name][key] = value
        return True

    def hdel(self, name, field):
        bucket = self.store.get(name)
        if isinstance(bucket, dict) and field in bucket:
            bucket.pop(field, None)
            return 1
        return 0

    # ── SETS ─────────────────────────────────
    def sadd(self, name, *values):
        if name not in self.store or not isinstance(self.store.get(name), set):
            self.store[name] = set()
        added = 0
        for v in values:
            if v not in self.store[name]:
                self.store[name].add(v)
                added += 1
        return added

    def srem(self, name, *values):
        if name not in self.store or not isinstance(self.store.get(name), set):
            return 0
        removed = 0
        for v in values:
            if v in self.store[name]:
                self.store[name].remove(v)
                removed += 1
        return removed

    # ── OPTIONAL SAFETY ───────────────────────
    def delete_key(self, key):
        return self.delete(key)


def init_redis(app):
    """Initialize Redis client"""
    global redis_client
    redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Will use in-memory fallback.")
        redis_client = InMemoryRedis()


def get_redis():
    """Get Redis client"""
    return redis_client


def cache_set(key: str, value, ttl: int = 3600):
    """Set value in cache with TTL (seconds)"""
    try:
        if redis_client:
            # Convert value to JSON if not a string
            if not isinstance(value, str):
                value = json.dumps(value)
            redis_client.setex(key, ttl, value)
            return True
    except Exception as e:
        logger.debug(f"Cache set error: {e}")
    return False


def cache_get(key: str):
    """Get value from cache"""
    try:
        if redis_client:
            value = redis_client.get(key)
            if value:
                # Try to parse as JSON
                try:
                    return json.loads(value)
                except:
                    return value
    except Exception as e:
        logger.debug(f"Cache get error: {e}")
    return None


def cache_delete(key: str):
    """Delete value from cache"""
    try:
        if redis_client:
            redis_client.delete(key)
            return True
    except Exception as e:
        logger.debug(f"Cache delete error: {e}")
    return False


def cache_clear():
    """Clear all cache"""
    try:
        if redis_client:
            redis_client.flushdb()
            return True
    except Exception as e:
        logger.debug(f"Cache clear error: {e}")
    return False

