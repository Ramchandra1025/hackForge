"""Audit logging model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class AuditModel:
    @staticmethod
    def log_action(user_id, team_id, action_type, resource_type, resource_id, changes=None):
        """Log an audit action"""
        try:
            response = supabase.table("audit_logs").insert({
                "user_id": user_id,
                "team_id": team_id,
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "changes": changes or {},
                "ip_address": None,
                "user_agent": None,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error logging audit action: {e}")
            return None

    @staticmethod
    def get_team_audit_logs(team_id, limit=100):
        """Get audit logs for a team"""
        try:
            response = supabase.table("audit_logs").select("*").eq("team_id", team_id).order("created_at", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"Error getting audit logs: {e}")
            return []

    @staticmethod
    def get_user_audit_logs(user_id, limit=50):
        """Get audit logs for a user"""
        try:
            response = supabase.table("audit_logs").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"Error getting user audit logs: {e}")
            return []
