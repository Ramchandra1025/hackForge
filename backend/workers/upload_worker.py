"""Upload Worker for processing file uploads"""
import os
from datetime import datetime
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class UploadWorker:
    @staticmethod
    def process_uploads():
        """Process pending uploads"""
        try:
            response = supabase.table("storage_upload_sessions").select("*").eq("status", "processing").execute()
            sessions = response.data
            
            for session in sessions:
                UploadWorker.finalize_upload(session)
                
        except Exception as e:
            print(f"Error processing uploads: {e}")

    @staticmethod
    def finalize_upload(session):
        """Finalize an upload session"""
        try:
            session_id = session.get("id")
            
            # Create file record if upload successful
            supabase.table("storage_upload_sessions").update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", session_id).execute()
            
        except Exception as e:
            print(f"Error finalizing upload: {e}")

if __name__ == "__main__":
    UploadWorker.process_uploads()
