"""Wiki/Documentation model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class WikiModel:
    @staticmethod
    def create_page(team_id, title, content, created_by):
        """Create a wiki page"""
        try:
            response = supabase.table("wiki_pages").insert({
                "team_id": team_id,
                "title": title,
                "content": content,
                "created_by": created_by,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating wiki page: {e}")
            return None

    @staticmethod
    def get_page_by_id(page_id):
        """Get wiki page by ID"""
        try:
            response = supabase.table("wiki_pages").select("*").eq("id", page_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting wiki page: {e}")
            return None

    @staticmethod
    def get_team_pages(team_id):
        """Get all wiki pages for a team"""
        try:
            response = supabase.table("wiki_pages").select("*").eq("team_id", team_id).order("updated_at", desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error getting team wiki pages: {e}")
            return []

    @staticmethod
    def update_page(page_id, content, updated_by):
        """Update wiki page"""
        try:
            response = supabase.table("wiki_pages").update({
                "content": content,
                "updated_by": updated_by,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", page_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating wiki page: {e}")
            return None

    @staticmethod
    def delete_page(page_id):
        """Delete wiki page"""
        try:
            supabase.table("wiki_pages").delete().eq("id", page_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting wiki page: {e}")
            return False
