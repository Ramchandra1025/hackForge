"""
HackForge - Socket.IO Event Handler Service (Production)
"""

import logging
from flask_socketio import emit, join_room, leave_room
from flask import request

from backend.utils.security import decode_jwt
from backend.utils.db import get_db
from backend.utils.redis_client import get_redis
from backend.utils.helpers import generate_id, now_iso

logger = logging.getLogger(__name__)


def get_user_from_socket():
    """
    Authenticate socket connection via JWT cookie or query param.
    """
    token = request.cookies.get("hackforge_token") or request.args.get("token")

    if not token:
        return None

    try:
        payload = decode_jwt(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        db = get_db()
        if not db:
            return None

        result = db.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            return None

        user = result.data[0]
        if not user.get("is_active", True):
            return None

        return user

    except Exception as e:
        logger.error(f"Socket auth error: {e}")
        return None


def safe_hget(redis_client, key, field):
    """Safe hget for fallback redis."""
    try:
        return redis_client.hget(key, field)
    except Exception:
        data = redis_client.get(key)
        if isinstance(data, dict):
            return data.get(field)
        return None


def safe_hset(redis_client, key, mapping):
    """Safe hset for fallback redis."""
    try:
        redis_client.hset(key, mapping=mapping)
    except Exception:
        redis_client.set(key, mapping)


def register_socket_handlers(socketio):
    """Register all Socket.IO handlers."""

    @socketio.on("connect", namespace="/")
    def on_connect(auth=None):
        """Socket connection handler."""
        user = get_user_from_socket()

        if not user:
            logger.warning("Socket authentication failed")
            return False

        sid = request.sid
        r = get_redis()

        try:
            safe_hset(
                r,
                f"socket:user:{sid}",
                {
                    "user_id": user["id"],
                    "username": user["username"],
                    "connected_at": now_iso(),
                },
            )

            safe_hset(
                r,
                "online:sids",
                {
                    sid: user["id"]
                },
            )

            try:
                r.sadd("online:users", user["id"])
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Redis socket tracking error: {e}")

        logger.info(f"Socket connected: {user['username']} ({sid})")

        emit(
            "connected",
            {
                "user_id": user["id"],
                "message": "Connected to HackForge",
            },
        )

        return True

    @socketio.on("disconnect", namespace="/")
    def on_disconnect(reason=None):
        """Socket disconnect handler."""
        sid = request.sid
        r = get_redis()

        try:
            user_id = safe_hget(r, "online:sids", sid)

            if user_id:
                try:
                    r.srem("online:users", user_id)
                except Exception:
                    pass

                try:
                    r.hdel("online:sids", sid)
                except Exception:
                    pass

                try:
                    r.delete(f"socket:user:{sid}")
                except Exception:
                    pass

                try:
                    db = get_db()
                    if db:
                        db.table("presence").upsert(
                            {
                                "user_id": user_id,
                                "status": "offline",
                                "last_seen": now_iso(),
                            }
                        ).execute()
                except Exception as e:
                    logger.error(f"Presence update error: {e}")

                logger.info(f"Socket disconnected: {user_id}")

        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    @socketio.on("join_room")
    def on_join_room(data):
        user = get_user_from_socket()
        if not user:
            return

        room = data.get("room")
        if not room:
            return

        join_room(room)
        emit("room_joined", {"room": room, "user": user}, to=room)

    @socketio.on("leave_room")
    def on_leave_room(data):
        user = get_user_from_socket()
        if not user:
            return

        room = data.get("room")
        if not room:
            return

        leave_room(room)
        emit("room_left", {"room": room, "user_id": user["id"]}, to=room)

    logger.info("Socket.IO handlers registered")