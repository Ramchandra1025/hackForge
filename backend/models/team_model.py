"""Team data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class TeamModel:
    @staticmethod
    def create_team(name, owner_id, description=""):
        """Create a new team"""
        try:
            response = supabase.table("teams").insert({
                "name": name,
                "owner_id": owner_id,
                "description": description,
                "avatar_url": None,
                "max_members": 10,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            
            team = response.data[0] if response.data else None
            
            # Add owner as admin member
            if team:
                supabase.table("memberships").insert({
                    "team_id": team["id"],
                    "user_id": owner_id,
                    "role": "owner",
                    "joined_at": datetime.utcnow().isoformat()
                }).execute()
            
            return team
        except Exception as e:
            print(f"Error creating team: {e}")
            return None

    @staticmethod
    def get_team_by_id(team_id):
        """Get team by ID"""
        try:
            response = supabase.table("teams").select("*").eq("id", team_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting team: {e}")
            return None

    @staticmethod
    def get_user_teams(user_id):
        """Get all teams for a user"""
        try:
            response = supabase.table("memberships").select(
                "teams:team_id(*)"
            ).eq("user_id", user_id).execute()
            teams = [m["teams"] for m in response.data if m.get("teams")]
            return teams
        except Exception as e:
            print(f"Error getting user teams: {e}")
            return []

    @staticmethod
    def add_member(team_id, user_id, role="developer"):
        """Add member to team"""
        try:
            response = supabase.table("memberships").insert({
                "team_id": team_id,
                "user_id": user_id,
                "role": role,
                "joined_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding team member: {e}")
            return None

    @staticmethod
    def remove_member(team_id, user_id):
        """Remove member from team"""
        try:
            supabase.table("memberships").delete().eq("team_id", team_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"Error removing team member: {e}")
            return False

    @staticmethod
    def get_team_members(team_id):
        """Get all members in a team"""
        try:
            response = supabase.table("memberships").select(
                "user_id, role, users:user_id(id, username, avatar_url, email)"
            ).eq("team_id", team_id).execute()
            return response.data
        except Exception as e:
            print(f"Error getting team members: {e}")
            return []

    @staticmethod
    def update_member_role(team_id, user_id, role):
        """Update member role"""
        try:
            response = supabase.table("memberships").update({
                "role": role
            }).eq("team_id", team_id).eq("user_id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating member role: {e}")
            return None

    @staticmethod
    def update_team(team_id, updates):
        """Update team data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("teams").update(updates).eq("id", team_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating team: {e}")
            return None
