"""Project data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class ProjectModel:
    @staticmethod
    def create_project(team_id, name, description="", repo_url=""):
        """Create a new project"""
        try:
            response = supabase.table("projects").insert({
                "team_id": team_id,
                "name": name,
                "description": description,
                "repo_url": repo_url,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "is_archived": False
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating project: {e}")
            return None

    @staticmethod
    def get_project_by_id(project_id):
        """Get project by ID"""
        try:
            response = supabase.table("projects").select("*").eq("id", project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting project: {e}")
            return None

    @staticmethod
    def get_team_projects(team_id):
        """Get all projects in a team"""
        try:
            response = supabase.table("projects").select("*").eq("team_id", team_id).eq("is_archived", False).execute()
            return response.data
        except Exception as e:
            print(f"Error getting team projects: {e}")
            return []

    @staticmethod
    def update_project(project_id, updates):
        """Update project data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("projects").update(updates).eq("id", project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating project: {e}")
            return None

    @staticmethod
    def archive_project(project_id):
        """Archive a project"""
        return ProjectModel.update_project(project_id, {"is_archived": True})

    @staticmethod
    def delete_project(project_id):
        """Delete a project"""
        try:
            supabase.table("projects").delete().eq("id", project_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting project: {e}")
            return False
