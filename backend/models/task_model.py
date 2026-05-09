"""Task data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class TaskModel:
    @staticmethod
    def create_task(project_id, title, description="", priority="medium", assigned_to=None):
        """Create a new task"""
        try:
            response = supabase.table("tasks").insert({
                "project_id": project_id,
                "title": title,
                "description": description,
                "priority": priority,
                "status": "todo",
                "assigned_to": assigned_to,
                "due_date": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating task: {e}")
            return None

    @staticmethod
    def get_task_by_id(task_id):
        """Get task by ID"""
        try:
            response = supabase.table("tasks").select("*").eq("id", task_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting task: {e}")
            return None

    @staticmethod
    def get_project_tasks(project_id):
        """Get all tasks in a project"""
        try:
            response = supabase.table("tasks").select("*").eq("project_id", project_id).execute()
            return response.data
        except Exception as e:
            print(f"Error getting project tasks: {e}")
            return []

    @staticmethod
    def update_task(task_id, updates):
        """Update task data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("tasks").update(updates).eq("id", task_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating task: {e}")
            return None

    @staticmethod
    def add_comment(task_id, user_id, content):
        """Add comment to task"""
        try:
            response = supabase.table("task_comments").insert({
                "task_id": task_id,
                "user_id": user_id,
                "content": content,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding task comment: {e}")
            return None

    @staticmethod
    def get_task_comments(task_id):
        """Get all comments for a task"""
        try:
            response = supabase.table("task_comments").select(
                "id, content, user_id, created_at, users:user_id(username, avatar_url)"
            ).eq("task_id", task_id).order("created_at", desc=False).execute()
            return response.data
        except Exception as e:
            print(f"Error getting task comments: {e}")
            return []

    @staticmethod
    def delete_task(task_id):
        """Delete a task"""
        try:
            supabase.table("tasks").delete().eq("id", task_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting task: {e}")
            return False
