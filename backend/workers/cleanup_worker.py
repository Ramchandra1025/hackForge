"""Cleanup Worker for maintenance tasks"""
import os
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class CleanupWorker:
    @staticmethod
    def cleanup():
        """Run cleanup tasks"""
        try:
            CleanupWorker.clean_expired_otps()
            CleanupWorker.clean_expired_sessions()
            CleanupWorker.clean_old_notifications()
            print("Cleanup completed successfully")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    @staticmethod
    def clean_expired_otps():
        """Remove expired OTP codes"""
        try:
            expiry_time = datetime.utcnow() - timedelta(minutes=5)
            supabase.table("otp_codes").delete().lt("created_at", expiry_time.isoformat()).execute()
        except Exception as e:
            print(f"Error cleaning OTPs: {e}")

    @staticmethod
    def clean_expired_sessions():
        """Remove expired sessions"""
        try:
            expiry_time = datetime.utcnow() - timedelta(days=7)
            supabase.table("login_sessions").delete().lt("created_at", expiry_time.isoformat()).execute()
        except Exception as e:
            print(f"Error cleaning sessions: {e}")

    @staticmethod
    def clean_old_notifications():
        """Remove old read notifications"""
        try:
            old_date = datetime.utcnow() - timedelta(days=30)
            supabase.table("notifications").delete().eq("is_read", True).lt("created_at", old_date.isoformat()).execute()
        except Exception as e:
            print(f"Error cleaning notifications: {e}")

if __name__ == "__main__":
    CleanupWorker.cleanup()
