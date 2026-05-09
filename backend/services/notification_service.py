"""HackForge — Notification Service"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:

    def __init__(self):
        self.supabase = get_supabase()

    def create(self, user_id: str, title: str, body: str,
               notif_type: str = "info", link: str = None,
               team_id: str = None, actor_id: str = None,
               metadata: dict = None) -> Dict[str, Any]:
        data = {
            "user_id": user_id,
            "title": title,
            "body": body,
            "type": notif_type,
            "link": link,
            "team_id": team_id,
            "actor_id": actor_id,
            "metadata": metadata or {},
            "is_read": False,
            "created_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("notifications").insert(data).execute()
        return result.data[0] if result.data else data

    def create_for_team(self, team_id: str, title: str, body: str,
                        notif_type: str = "info", exclude_user: str = None,
                        link: str = None, actor_id: str = None) -> List[Dict]:
        members = self.supabase.table("memberships").select("user_id").eq(
            "team_id", team_id
        ).execute()

        notifications = []
        for m in (members.data or []):
            uid = m["user_id"]
            if uid == exclude_user:
                continue
            notif = self.create(uid, title, body, notif_type, link, team_id, actor_id)
            notifications.append(notif)
        return notifications

    def mark_read(self, notification_id: str, user_id: str) -> bool:
        result = self.supabase.table("notifications").update(
            {"is_read": True, "read_at": datetime.utcnow().isoformat()}
        ).eq("id", notification_id).eq("user_id", user_id).execute()
        return bool(result.data)

    def mark_all_read(self, user_id: str, team_id: str = None) -> int:
        q = self.supabase.table("notifications").update(
            {"is_read": True, "read_at": datetime.utcnow().isoformat()}
        ).eq("user_id", user_id).eq("is_read", False)
        if team_id:
            q = q.eq("team_id", team_id)
        result = q.execute()
        return len(result.data or [])

    def get_user_notifications(self, user_id: str, team_id: str = None,
                               unread_only: bool = False,
                               page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        q = self.supabase.table("notifications").select("*").eq("user_id", user_id)
        if team_id:
            q = q.eq("team_id", team_id)
        if unread_only:
            q = q.eq("is_read", False)

        offset = (page - 1) * per_page
        result = q.order("created_at", desc=True).range(offset, offset + per_page - 1).execute()

        unread_count = self.supabase.table("notifications").select(
            "id", count="exact"
        ).eq("user_id", user_id).eq("is_read", False).execute()

        return {
            "notifications": result.data or [],
            "unread_count": unread_count.count or 0,
            "page": page,
            "per_page": per_page
        }

    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        result = self.supabase.table("notifications").delete().eq(
            "id", notification_id
        ).eq("user_id", user_id).execute()
        return bool(result.data)

    def get_unread_count(self, user_id: str) -> int:
        result = self.supabase.table("notifications").select(
            "id", count="exact"
        ).eq("user_id", user_id).eq("is_read", False).execute()
        return result.count or 0