"""HackForge — Meeting Service"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)

JITSI_DOMAIN = "meet.jit.si"


class MeetingService:

    def __init__(self):
        self.supabase = get_supabase()

    def create_meeting(self, team_id: str, project_id: str, creator_id: str,
                       data: Dict) -> Dict[str, Any]:
        import secrets
        room_id = data.get("room_id") or f"hackforge-{secrets.token_hex(8)}"

        meeting = {
            "team_id": team_id,
            "project_id": project_id,
            "creator_id": creator_id,
            "title": data["title"],
            "description": data.get("description", ""),
            "room_id": room_id,
            "jitsi_url": f"https://{JITSI_DOMAIN}/{room_id}",
            "meeting_type": data.get("meeting_type", "video"),
            "scheduled_at": data.get("scheduled_at"),
            "duration_minutes": data.get("duration_minutes", 60),
            "status": "scheduled",
            "is_recurring": data.get("is_recurring", False),
            "agenda": data.get("agenda", ""),
            "created_at": datetime.utcnow().isoformat()
        }

        result = self.supabase.table("meetings").insert(meeting).execute()
        if not result.data:
            raise RuntimeError("Failed to create meeting")

        created = result.data[0]

        # Add creator as participant
        self.supabase.table("meeting_participants").insert({
            "meeting_id": created["id"],
            "user_id": creator_id,
            "role": "host",
            "joined_at": None
        }).execute()

        return created

    def get_meeting(self, meeting_id: str) -> Optional[Dict]:
        result = self.supabase.table("meetings").select(
            "*, creator:creator_id(id,username,full_name,avatar_url)"
        ).eq("id", meeting_id).execute()
        return result.data[0] if result.data else None

    def get_team_meetings(self, team_id: str, upcoming_only: bool = False) -> List[Dict]:
        q = self.supabase.table("meetings").select("*").eq("team_id", team_id)
        if upcoming_only:
            q = q.gte("scheduled_at", datetime.utcnow().isoformat())
        result = q.order("scheduled_at", desc=not upcoming_only).limit(50).execute()
        return result.data or []

    def join_meeting(self, meeting_id: str, user_id: str) -> Dict:
        # Upsert participant
        self.supabase.table("meeting_participants").upsert({
            "meeting_id": meeting_id,
            "user_id": user_id,
            "role": "participant",
            "joined_at": datetime.utcnow().isoformat()
        }, on_conflict="meeting_id,user_id").execute()

        meeting = self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError("Meeting not found")

        return {
            "meeting": meeting,
            "jitsi_url": meeting["jitsi_url"],
            "room_id": meeting["room_id"],
            "jitsi_domain": JITSI_DOMAIN
        }

    def end_meeting(self, meeting_id: str, user_id: str) -> bool:
        self.supabase.table("meetings").update({
            "status": "ended",
            "ended_at": datetime.utcnow().isoformat()
        }).eq("id", meeting_id).execute()
        return True

    def get_participants(self, meeting_id: str) -> List[Dict]:
        result = self.supabase.table("meeting_participants").select(
            "*, user:user_id(id,username,full_name,avatar_url)"
        ).eq("meeting_id", meeting_id).execute()
        return result.data or []

    def start_instant_meeting(self, team_id: str, creator_id: str,
                               title: str = "Instant Meeting") -> Dict:
        return self.create_meeting(team_id, None, creator_id, {
            "title": title,
            "meeting_type": "video",
            "status": "active"
        })