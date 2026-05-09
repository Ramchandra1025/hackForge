"""File data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class FileModel:
    @staticmethod
    def create_file(project_id, name, file_type, size, mime_type, uploaded_by):
        """Create a new file record"""
        try:
            response = supabase.table("files").insert({
                "project_id": project_id,
                "name": name,
                "file_type": file_type,
                "size": size,
                "mime_type": mime_type,
                "uploaded_by": uploaded_by,
                "storage_path": f"teams/projects/{project_id}/{name}",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating file record: {e}")
            return None

    @staticmethod
    def get_file_by_id(file_id):
        """Get file by ID"""
        try:
            response = supabase.table("files").select("*").eq("id", file_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting file: {e}")
            return None

    @staticmethod
    def get_project_files(project_id):
        """Get all files in a project"""
        try:
            response = supabase.table("files").select("*").eq("project_id", project_id).execute()
            return response.data
        except Exception as e:
            print(f"Error getting project files: {e}")
            return []

    @staticmethod
    def update_file(file_id, updates):
        """Update file metadata"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("files").update(updates).eq("id", file_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating file: {e}")
            return None

    @staticmethod
    def delete_file(file_id):
        """Delete file record"""
        try:
            supabase.table("files").delete().eq("id", file_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

    @staticmethod
    def create_version(file_id, version_number, size, uploaded_by):
        """Create file version"""
        try:
            response = supabase.table("file_versions").insert({
                "file_id": file_id,
                "version_number": version_number,
                "size": size,
                "uploaded_by": uploaded_by,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating file version: {e}")
            return None

    @staticmethod
    def get_file_versions(file_id):
        """Get all versions of a file"""
        try:
            response = supabase.table("file_versions").select("*").eq("file_id", file_id).order("version_number", desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error getting file versions: {e}")
            return []
