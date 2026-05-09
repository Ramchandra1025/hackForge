"""Deployment data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class DeploymentModel:
    @staticmethod
    def create_deployment(project_id, platform, status="pending"):
        """Create a new deployment"""
        try:
            response = supabase.table("deployments").insert({
                "project_id": project_id,
                "platform": platform,
                "status": status,
                "deployment_url": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating deployment: {e}")
            return None

    @staticmethod
    def get_deployment_by_id(deployment_id):
        """Get deployment by ID"""
        try:
            response = supabase.table("deployments").select("*").eq("id", deployment_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting deployment: {e}")
            return None

    @staticmethod
    def get_project_deployments(project_id):
        """Get all deployments for a project"""
        try:
            response = supabase.table("deployments").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error getting project deployments: {e}")
            return []

    @staticmethod
    def update_deployment(deployment_id, updates):
        """Update deployment"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("deployments").update(updates).eq("id", deployment_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating deployment: {e}")
            return None

    @staticmethod
    def add_deployment_log(deployment_id, log_message, log_type="info"):
        """Add log to deployment"""
        try:
            response = supabase.table("deployment_logs").insert({
                "deployment_id": deployment_id,
                "message": log_message,
                "log_type": log_type,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding deployment log: {e}")
            return None

    @staticmethod
    def get_deployment_logs(deployment_id):
        """Get logs for a deployment"""
        try:
            response = supabase.table("deployment_logs").select("*").eq("deployment_id", deployment_id).order("created_at", desc=False).execute()
            return response.data
        except Exception as e:
            print(f"Error getting deployment logs: {e}")
            return []
