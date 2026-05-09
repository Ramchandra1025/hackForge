"""HackForge — Audit Service"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AuditService:

    def __init__(self):
        self.supabase = get_supabase()

    def log(self, user_id: str, action: str, resource_type: str,
            resource_id: str = None, team_id: str = None,
            metadata: dict = None, ip_address: str = None,
            severity: str = "info") -> None:
        try:
            self.supabase.table("audit_logs").insert({
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "team_id": team_id,
                "metadata": metadata or {},
                "ip_address": ip_address,
                "severity": severity,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Audit log failed: {e}")

    def get_logs(self, team_id: str = None, user_id: str = None,
                 action: str = None, resource_type: str = None,
                 page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        q = self.supabase.table("audit_logs").select("*, users(username, full_name, avatar_url)")

        if team_id:
            q = q.eq("team_id", team_id)
        if user_id:
            q = q.eq("user_id", user_id)
        if action:
            q = q.eq("action", action)
        if resource_type:
            q = q.eq("resource_type", resource_type)

        offset = (page - 1) * per_page
        result = q.order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        count_result = self.supabase.table("audit_logs").select("id", count="exact").execute()

        return {
            "logs": result.data or [],
            "total": count_result.count or 0,
            "page": page,
            "per_page": per_page
        }