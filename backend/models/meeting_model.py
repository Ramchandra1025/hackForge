"""Meeting data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class MeetingModel:
    @staticmethod
    def create_meeting(team_id, title, description="", scheduled_for=None):
        """Create a new meeting"""
        try:
            response = supabase.table("meetings").insert({
                "team_id": team_id,
                "title": title,
                "description": description,
                "scheduled_for": scheduled_for,
                "meeting_url": None,
                "status": "scheduled",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating meeting: {e}")
            return None

    @staticmethod
    def get_meeting_by_id(meeting_id):
        """Get meeting by ID"""
        try:
            response = supabase.table("meetings").select("*").eq("id", meeting_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting meeting: {e}")
            return None

    @staticmethod
    def add_participant(meeting_id, user_id):
        """Add participant to meeting"""
        try:
            response = supabase.table("meeting_participants").insert({
                "meeting_id": meeting_id,
                "user_id": user_id,
                "joined_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding participant: {e}")
            return None

    @staticmethod
    def get_meeting_participants(meeting_id):
        """Get participants in a meeting"""
        try:
            response = supabase.table("meeting_participants").select(
                "user_id, joined_at, users:user_id(username, avatar_url)"
            ).eq("meeting_id", meeting_id).execute()
            return response.data
        except Exception as e:
            print(f"Error getting meeting participants: {e}")
            return []

    @staticmethod
    def update_meeting(meeting_id, updates):
        """Update meeting"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("meetings").update(updates).eq("id", meeting_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating meeting: {e}")
            return None
