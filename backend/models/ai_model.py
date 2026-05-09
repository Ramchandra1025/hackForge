"""AI Model and AI-related operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class AIModel:
    @staticmethod
    def create_memory(user_id, team_id, content, context=""):
        """Create AI memory entry"""
        try:
            response = supabase.table("ai_memory").insert({
                "user_id": user_id,
                "team_id": team_id,
                "content": content,
                "context": context,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating AI memory: {e}")
            return None

    @staticmethod
    def get_user_memories(user_id, limit=50):
        """Get AI memories for user"""
        try:
            response = supabase.table("ai_memory").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"Error getting AI memories: {e}")
            return []

    @staticmethod
    def create_action(user_id, action_type, status, description=""):
        """Create AI action request"""
        try:
            response = supabase.table("ai_actions").insert({
                "user_id": user_id,
                "action_type": action_type,
                "status": status,
                "description": description,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating AI action: {e}")
            return None

    @staticmethod
    def get_pending_actions():
        """Get pending AI actions"""
        try:
            response = supabase.table("ai_actions").select("*").eq("status", "pending").order("created_at", desc=False).execute()
            return response.data
        except Exception as e:
            print(f"Error getting pending AI actions: {e}")
            return []

    @staticmethod
    def update_action(action_id, updates):
        """Update AI action"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("ai_actions").update(updates).eq("id", action_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating AI action: {e}")
            return None
