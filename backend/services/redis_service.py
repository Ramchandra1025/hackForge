"""HackForge — Redis Service with in-memory fallback"""
import os
import json
import time
from typing import Any, Optional
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_redis_client = None
_memory_store: dict = {}
_memory_expiry: dict = {}
_use_memory = False


def _get_redis():
    global _redis_client, _use_memory
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        password = os.getenv("REDIS_PASSWORD") or None
        _redis_client = redis.from_url(url, password=password, decode_responses=True, socket_timeout=3)
        _redis_client.ping()
        logger.info("Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
        _use_memory = True
        return None


class RedisService:

    def __init__(self):
        self.r = _get_redis()

    def set(self, key: str, value: Any, ex: int = None) -> bool:
        try:
            if self.r and not _use_memory:
                serialized = json.dumps(value) if not isinstance(value, str) else value
                if ex:
                    self.r.setex(key, ex, serialized)
                else:
                    self.r.set(key, serialized)
                return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")

        # Memory fallback
        _memory_store[key] = json.dumps(value) if not isinstance(value, str) else value
        if ex:
            _memory_expiry[key] = time.time() + ex
        return True

    def get(self, key: str) -> Optional[Any]:
        try:
            if self.r and not _use_memory:
                val = self.r.get(key)
                if val:
                    try:
                        return json.loads(val)
                    except Exception:
                        return val
                return None
        except Exception as e:
            logger.error(f"Redis GET error: {e}")

        # Memory fallback
        if key in _memory_expiry and time.time() > _memory_expiry[key]:
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)
            return None
        val = _memory_store.get(key)
        if val:
            try:
                return json.loads(val)
            except Exception:
                return val
        return None

    def delete(self, key: str) -> bool:
        try:
            if self.r and not _use_memory:
                self.r.delete(key)
                return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
        _memory_store.pop(key, None)
        _memory_expiry.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        val = self.get(key)
        return val is not None

    def incr(self, key: str, ex: int = None) -> int:
        try:
            if self.r and not _use_memory:
                val = self.r.incr(key)
                if ex and val == 1:
                    self.r.expire(key, ex)
                return val
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")

        current = int(_memory_store.get(key, "0"))
        new_val = current + 1
        _memory_store[key] = str(new_val)
        if ex and new_val == 1:
            _memory_expiry[key] = time.time() + ex
        return new_val

    def hset(self, name: str, key: str, value: Any) -> bool:
        try:
            if self.r and not _use_memory:
                self.r.hset(name, key, json.dumps(value) if not isinstance(value, str) else value)
                return True
        except Exception:
            pass
        bucket = _memory_store.get(f"h:{name}", {})
        bucket[key] = value
        _memory_store[f"h:{name}"] = bucket
        return True

    def hget(self, name: str, key: str) -> Optional[Any]:
        try:
            if self.r and not _use_memory:
                val = self.r.hget(name, key)
                if val:
                    try:
                        return json.loads(val)
                    except Exception:
                        return val
                return None
        except Exception:
            pass
        return _memory_store.get(f"h:{name}", {}).get(key)

    def hgetall(self, name: str) -> dict:
        try:
            if self.r and not _use_memory:
                data = self.r.hgetall(name)
                result = {}
                for k, v in data.items():
                    try:
                        result[k] = json.loads(v)
                    except Exception:
                        result[k] = v
                return result
        except Exception:
            pass
        return _memory_store.get(f"h:{name}", {})

    def hdel(self, name: str, key: str) -> bool:
        try:
            if self.r and not _use_memory:
                self.r.hdel(name, key)
                return True
        except Exception:
            pass
        bucket = _memory_store.get(f"h:{name}", {})
        bucket.pop(key, None)
        _memory_store[f"h:{name}"] = bucket
        return True

    def expire(self, key: str, seconds: int) -> bool:
        try:
            if self.r and not _use_memory:
                self.r.expire(key, seconds)
                return True
        except Exception:
            pass
        _memory_expiry[key] = time.time() + seconds
        return True

    def publish(self, channel: str, message: Any) -> bool:
        try:
            if self.r and not _use_memory:
                self.r.publish(channel, json.dumps(message) if not isinstance(message, str) else message)
                return True
        except Exception as e:
            logger.error(f"Redis PUBLISH error: {e}")
        return False

    def setex(self, key: str, seconds: int, value: Any) -> bool:
        return self.set(key, value, ex=seconds)

    def ttl(self, key: str) -> int:
        try:
            if self.r and not _use_memory:
                return self.r.ttl(key)
        except Exception:
            pass
        if key in _memory_expiry:
            remaining = int(_memory_expiry[key] - time.time())
            return max(0, remaining)
        return -1