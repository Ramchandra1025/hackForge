"""
HackForge - Supabase Storage Service
Complete file upload, download, management with signed URLs
"""

import os
import io
import uuid
import logging
import mimetypes
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from supabase import create_client, Client

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv('SUPABASE_STORAGE_BUCKET', 'hackforge-files')
MAX_FILE_SIZE = int(os.getenv('MAX_UPLOAD_SIZE_MB', 100)) * 1024 * 1024  # bytes

ALLOWED_MIME_TYPES = {
    # Images
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
    # Documents
    'application/pdf', 'text/plain', 'text/markdown',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    # Code
    'text/html', 'text/css', 'text/javascript', 'application/json',
    'text/x-python', 'text/x-java', 'text/x-c', 'text/x-cpp',
    # Archives
    'application/zip', 'application/x-tar', 'application/gzip',
    # Media
    'video/mp4', 'video/webm', 'audio/mpeg', 'audio/wav',
    # Data
    'text/csv',
    'application/octet-stream',  # Generic binary fallback
}

ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'pdf', 'doc', 'docx', 'txt',
    'md', 'py', 'js', 'ts', 'html', 'css', 'json', 'zip', 'tar', 'gz',
    'mp4', 'mp3', 'csv', 'xlsx', 'java', 'cpp', 'c', 'h', 'rb', 'go',
    'rs', 'php', 'yaml', 'yml', 'xml', 'sh', 'sql', 'env', 'toml', 'ini'
}


class StorageService:
    """Supabase Storage Service for HackForge"""
    
    def __init__(self):
        self._client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        if self._client is None:
            url = os.getenv('SUPABASE_URL', '')
            key = os.getenv('SUPABASE_SERVICE_KEY', '') or os.getenv('SUPABASE_KEY', '')
            if url and key:
                self._client = create_client(url, key)
        return self._client
    
    def build_path(self, team_id: str, project_id: str = None, 
                   folder_path: str = None, file_id: str = None, 
                   filename: str = None) -> str:
        """Build storage path with tenant isolation"""
        parts = ['teams', team_id]
        
        if project_id:
            parts.extend(['projects', project_id])
        
        if folder_path:
            parts.append(folder_path.strip('/'))
        
        if file_id:
            parts.append(file_id)
        
        if filename:
            parts.append(filename)
        
        return '/'.join(parts)
    
    def validate_file(self, filename: str, content_type: str, size_bytes: int) -> Tuple[bool, str]:
        """Validate file before upload"""
        # Check extension
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File extension '.{ext}' is not allowed"
        
        # Check file size
        if size_bytes > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE // (1024 * 1024)
            return False, f"File size exceeds maximum allowed ({max_mb}MB)"
        
        # Validate MIME type
        guessed_type = mimetypes.guess_type(filename)[0]
        if content_type not in ALLOWED_MIME_TYPES and guessed_type not in ALLOWED_MIME_TYPES:
            # Be lenient with text-based files
            if not content_type.startswith('text/'):
                return False, f"MIME type '{content_type}' is not allowed"
        
        return True, None
    
    def upload_file(self, file_data: bytes, storage_path: str, 
                    content_type: str = 'application/octet-stream') -> dict:
        """Upload file to Supabase Storage"""
        if not self.client:
            raise RuntimeError("Storage client not initialized")
        
        try:
            result = self.client.storage.from_(BUCKET_NAME).upload(
                storage_path,
                file_data,
                file_options={
                    'content-type': content_type,
                    'upsert': 'false'
                }
            )
            
            return {
                'path': storage_path,
                'full_path': result.full_path if hasattr(result, 'full_path') else storage_path
            }
            
        except Exception as e:
            logger.error(f"Upload error to {storage_path}: {e}")
            raise
    
    def upload_file_version(self, file_data: bytes, storage_path: str,
                             version: int, content_type: str) -> str:
        """Upload a new version of a file"""
        version_path = f"{storage_path}.v{version}"
        
        try:
            self.client.storage.from_(BUCKET_NAME).upload(
                version_path,
                file_data,
                file_options={'content-type': content_type, 'upsert': 'true'}
            )
            return version_path
        except Exception as e:
            logger.error(f"Version upload error: {e}")
            raise
    
    def download_file(self, storage_path: str) -> bytes:
        """Download file from Supabase Storage"""
        if not self.client:
            raise RuntimeError("Storage client not initialized")
        
        try:
            return self.client.storage.from_(BUCKET_NAME).download(storage_path)
        except Exception as e:
            logger.error(f"Download error from {storage_path}: {e}")
            raise
    
    def create_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Create signed URL for private file access"""
        if not self.client:
            raise RuntimeError("Storage client not initialized")
        
        try:
            result = self.client.storage.from_(BUCKET_NAME).create_signed_url(
                storage_path, expires_in
            )
            return result.get('signedURL') or result.get('signed_url', '')
        except Exception as e:
            logger.error(f"Signed URL error for {storage_path}: {e}")
            raise
    
    def create_signed_upload_url(self, storage_path: str) -> dict:
        """Create signed URL for direct upload"""
        if not self.client:
            raise RuntimeError("Storage client not initialized")
        
        try:
            result = self.client.storage.from_(BUCKET_NAME).create_signed_upload_url(storage_path)
            return result
        except Exception as e:
            logger.error(f"Signed upload URL error: {e}")
            raise
    
    def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage"""
        if not self.client:
            raise RuntimeError("Storage client not initialized")
        
        try:
            self.client.storage.from_(BUCKET_NAME).remove([storage_path])
            return True
        except Exception as e:
            logger.error(f"Delete error for {storage_path}: {e}")
            return False
    
    def delete_folder(self, folder_path: str) -> bool:
        """Delete all files in a folder"""
        if not self.client:
            return False
        
        try:
            files = self.list_files(folder_path)
            if files:
                paths = [f['name'] for f in files]
                self.client.storage.from_(BUCKET_NAME).remove(paths)
            return True
        except Exception as e:
            logger.error(f"Delete folder error for {folder_path}: {e}")
            return False
    
    def list_files(self, folder_path: str = '', limit: int = 100) -> List[dict]:
        """List files in a folder"""
        if not self.client:
            return []
        
        try:
            result = self.client.storage.from_(BUCKET_NAME).list(
                folder_path,
                {'limit': limit, 'offset': 0}
            )
            return result or []
        except Exception as e:
            logger.error(f"List files error for {folder_path}: {e}")
            return []
    
    def move_file(self, from_path: str, to_path: str) -> bool:
        """Move/rename a file"""
        if not self.client:
            return False
        
        try:
            self.client.storage.from_(BUCKET_NAME).move(from_path, to_path)
            return True
        except Exception as e:
            logger.error(f"Move error from {from_path} to {to_path}: {e}")
            return False
    
    def copy_file(self, from_path: str, to_path: str) -> bool:
        """Copy a file"""
        if not self.client:
            return False
        
        try:
            self.client.storage.from_(BUCKET_NAME).copy(from_path, to_path)
            return True
        except Exception as e:
            logger.error(f"Copy error: {e}")
            return False
    
    def get_public_url(self, storage_path: str) -> str:
        """Get public URL (only for public buckets)"""
        if not self.client:
            return ''
        
        try:
            result = self.client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
            return result
        except:
            return ''
    
    def ensure_bucket_exists(self) -> bool:
        """Ensure the storage bucket exists"""
        if not self.client:
            return False
        
        try:
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            if BUCKET_NAME not in bucket_names:
                self.client.storage.create_bucket(
                    BUCKET_NAME,
                    options={
                        'public': False,
                        'file_size_limit': MAX_FILE_SIZE,
                        'allowed_mime_types': list(ALLOWED_MIME_TYPES)
                    }
                )
                logger.info(f"Created storage bucket: {BUCKET_NAME}")
            
            return True
            
        except Exception as e:
            logger.error(f"Bucket setup error: {e}")
            return False


# Singleton instance
storage_service = StorageService()