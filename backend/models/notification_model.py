"""Notification data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class NotificationModel:
    @staticmethod
    def create_notification(user_id, notification_type, title, message, data=None, is_read=False):
        """Create a notification"""
        try:
            response = supabase.table("notifications").insert({
                "user_id": user_id,
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "data": data or {},
                "is_read": is_read,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating notification: {e}")
            return None

    @staticmethod
    def get_user_notifications(user_id, limit=50, is_read=False):
        """Get notifications for user"""
        try:
            query = supabase.table("notifications").select("*").eq("user_id", user_id)
            if is_read is not None:
                query = query.eq("is_read", is_read)
            response = query.order("created_at", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []

    @staticmethod
    def mark_as_read(notification_id):
        """Mark notification as read"""
        try:
            response = supabase.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return None

    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for user"""
        try:
            response = supabase.table("notifications").update({"is_read": True}).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"Error marking all as read: {e}")
            return False

    @staticmethod
    def delete_notification(notification_id):
        """Delete a notification"""
        try:
            supabase.table("notifications").delete().eq("id", notification_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting notification: {e}")
            return False
