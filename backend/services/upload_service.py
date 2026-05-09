"""HackForge - Upload Service"""
import os
import uuid
import hashlib
import logging
import mimetypes
from typing import Optional, Tuple
from backend.services.supabase_storage_service import storage_service
from backend.utils.db import get_db
from backend.utils.helpers import generate_id, now_iso, format_file_size

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = int(os.getenv('MAX_UPLOAD_SIZE_MB', 100)) * 1024 * 1024


def process_upload(file_data: bytes, filename: str, content_type: str,
                   user_id: str, team_id: str, project_id: str = None,
                   folder_id: str = None) -> Tuple[dict, Optional[str]]:
    """
    Process a complete file upload:
    1. Validate
    2. Upload to Supabase Storage
    3. Save metadata to DB
    Returns (file_record, error_message)
    """
    # Validate
    valid, err = storage_service.validate_file(filename, content_type, len(file_data))
    if not valid:
        return None, err

    # Generate unique file ID
    file_id = generate_id()
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Build storage path
    storage_path = storage_service.build_path(team_id, project_id, None, file_id, filename)

    # Compute checksum
    checksum = hashlib.md5(file_data).hexdigest()

    try:
        # Upload to storage
        storage_result = storage_service.upload_file(file_data, storage_path, content_type)
    except Exception as e:
        logger.error(f"Storage upload failed: {e}")
        return None, f"Storage upload failed: {str(e)}"

    # Save metadata to database
    db = get_db()
    file_record = {
        'id': file_id,
        'name': filename,
        'original_name': filename,
        'storage_path': storage_path,
        'file_type': ext,
        'mime_type': content_type,
        'size_bytes': len(file_data),
        'checksum': checksum,
        'team_id': team_id,
        'project_id': project_id,
        'folder_id': folder_id,
        'uploaded_by': user_id,
        'version': 1,
        'is_deleted': False,
        'metadata': {
            'original_name': filename,
            'upload_size': format_file_size(len(file_data))
        }
    }

    try:
        result = db.table('files').insert(file_record).execute()
        if not result.data:
            return None, 'Failed to save file metadata'

        # Create storage_objects entry
        db.table('storage_objects').insert({
            'id': generate_id(),
            'file_id': file_id,
            'storage_path': storage_path,
            'bucket_name': os.getenv('SUPABASE_STORAGE_BUCKET', 'hackforge-files'),
            'size_bytes': len(file_data),
            'mime_type': content_type,
            'checksum': checksum,
            'team_id': team_id
        }).execute()

        # Audit log
        db.table('storage_access_logs').insert({
            'id': generate_id(),
            'file_id': file_id,
            'user_id': user_id,
            'team_id': team_id,
            'action': 'upload',
            'file_size': len(file_data),
            'ip_address': None
        }).execute()

        return result.data[0], None

    except Exception as e:
        logger.error(f"DB save error: {e}")
        # Try to clean up storage
        try:
            storage_service.delete_file(storage_path)
        except Exception:
            pass
        return None, 'Failed to save file record'


def get_download_url(file_id: str, user_id: str, team_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Get a signed download URL for a file."""
    db = get_db()
    file = db.table('files').select('*').eq('id', file_id).eq('team_id', team_id).eq('is_deleted', False).single().execute()
    if not file.data:
        return None, 'File not found'

    try:
        url = storage_service.create_signed_url(file.data['storage_path'], expires_in=3600)
        # Log access
        db.table('storage_access_logs').insert({
            'id': generate_id(),
            'file_id': file_id,
            'user_id': user_id,
            'team_id': team_id,
            'action': 'download'
        }).execute()
        return url, None
    except Exception as e:
        return None, str(e)


def delete_file_record(file_id: str, user_id: str, team_id: str) -> Optional[str]:
    """Soft-delete a file and clean up storage."""
    db = get_db()
    file = db.table('files').select('*').eq('id', file_id).eq('team_id', team_id).eq('is_deleted', False).single().execute()
    if not file.data:
        return 'File not found'

    # Soft delete DB record
    db.table('files').update({'is_deleted': True}).eq('id', file_id).execute()

    # Delete from storage
    try:
        storage_service.delete_file(file.data['storage_path'])
    except Exception as e:
        logger.error(f"Storage delete error: {e}")

    # Audit log
    db.table('storage_access_logs').insert({
        'id': generate_id(),
        'file_id': file_id,
        'user_id': user_id,
        'team_id': team_id,
        'action': 'delete'
    }).execute()

    return None