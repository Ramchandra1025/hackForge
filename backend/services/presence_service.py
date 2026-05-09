"""HackForge — Presence Service"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from backend.services.redis_service import RedisService
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)

PRESENCE_TTL = 60  # seconds


class PresenceService:

    def __init__(self):
        self.redis = RedisService()
        self.supabase = get_supabase()

    def set_online(self, user_id: str, team_id: str, metadata: dict = None) -> None:
        key = f"presence:{team_id}:{user_id}"
        data = {
            "user_id": user_id,
            "team_id": team_id,
            "status": "online",
            "last_seen": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.redis.setex(key, PRESENCE_TTL, json.dumps(data))

        # Update DB
        try:
            self.supabase.table("users").update({
                "last_seen": datetime.utcnow().isoformat(),
                "is_online": True
            }).eq("id", user_id).execute()
        except Exception as e:
            logger.error(f"DB presence update failed: {e}")

    def set_offline(self, user_id: str, team_id: str = None) -> None:
        if team_id:
            key = f"presence:{team_id}:{user_id}"
            self.redis.delete(key)
        else:
            # Remove from all teams
            try:
                memberships = self.supabase.table("memberships").select("team_id").eq(
                    "user_id", user_id
                ).execute()
                for m in (memberships.data or []):
                    self.redis.delete(f"presence:{m['team_id']}:{user_id}")
            except Exception as e:
                logger.error(f"Batch offline failed: {e}")

        try:
            self.supabase.table("users").update({
                "last_seen": datetime.utcnow().isoformat(),
                "is_online": False
            }).eq("id", user_id).execute()
        except Exception:
            pass

    def get_online_members(self, team_id: str) -> List[Dict]:
        try:
            memberships = self.supabase.table("memberships").select(
                "user_id, role, users(id, username, full_name, avatar_url)"
            ).eq("team_id", team_id).execute()

            online = []
            for m in (memberships.data or []):
                uid = m["user_id"]
                key = f"presence:{team_id}:{uid}"
                presence_data = self.redis.get(key)
                if presence_data:
                    p = json.loads(presence_data) if isinstance(presence_data, str) else presence_data
                    user_info = m.get("users", {}) or {}
                    online.append({
                        "user_id": uid,
                        "username": user_info.get("username"),
                        "full_name": user_info.get("full_name"),
                        "avatar_url": user_info.get("avatar_url"),
                        "role": m.get("role"),
                        "status": p.get("status", "online"),
                        "last_seen": p.get("last_seen"),
                        "metadata": p.get("metadata", {})
                    })
            return online
        except Exception as e:
            logger.error(f"Get online members failed: {e}")
            return []

    def heartbeat(self, user_id: str, team_id: str) -> None:
        key = f"presence:{team_id}:{user_id}"
        existing = self.redis.get(key)
        if existing:
            data = json.loads(existing) if isinstance(existing, str) else existing
            data["last_seen"] = datetime.utcnow().isoformat()
            self.redis.setex(key, PRESENCE_TTL, json.dumps(data))
        else:
            self.set_online(user_id, team_id)

    def set_cursor(self, user_id: str, room_id: str,
                   x: float, y: float, color: str = None) -> None:
        key = f"cursor:{room_id}:{user_id}"
        self.redis.setex(key, 10, json.dumps({
            "user_id": user_id,
            "x": x, "y": y,
            "color": color,
            "updated": datetime.utcnow().isoformat()
        }))

    def get_cursors(self, room_id: str) -> List[Dict]:
        # Pattern scan would need full Redis; use team members approach
        return []