"""Notification Worker for background notifications"""
import os
from datetime import datetime
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class NotificationWorker:
    @staticmethod
    def send_pending_notifications():
        """Send pending notifications"""
        try:
            # Get all pending notifications
            response = supabase.table("notifications").select("*").eq("is_read", False).execute()
            notifications = response.data
            
            for notification in notifications:
                NotificationWorker.send_notification(notification)
                
        except Exception as e:
            print(f"Error sending notifications: {e}")

    @staticmethod
    def send_notification(notification):
        """Send a single notification"""
        try:
            user_id = notification.get("user_id")
            notification_type = notification.get("notification_type")
            title = notification.get("title")
            message = notification.get("message")
            
            # Here you would integrate with Socket.IO to send real-time notifications
            print(f"Sending notification to {user_id}: {title}")
            
        except Exception as e:
            print(f"Error sending notification: {e}")

if __name__ == "__main__":
    NotificationWorker.send_pending_notifications()
