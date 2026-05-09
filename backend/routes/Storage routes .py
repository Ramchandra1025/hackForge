"""
HackForge - Storage Routes
Complete file upload/download with chunk support
"""

import os
import io
import uuid
import logging
import hashlib
import mimetypes
from flask import Blueprint, request, g, send_file, jsonify
from backend.utils.db import get_db
from backend.utils.security import require_auth, get_membership, has_permission, audit_log
from backend.utils.error_handlers import success, error, get_pagination_params
from backend.services.supabase_storage_service import storage_service
from backend.utils.redis_client import get_redis

storage_bp = Blueprint('storage', __name__)
logger = logging.getLogger(__name__)


def verify_team_access(team_id, user_id, permission=None):
    """Verify user has access to team's storage"""
    membership = get_membership(user_id, team_id)
    if not membership:
        return None
    if permission and not has_permission(membership['role'], permission):
        return None
    return membership


@storage_bp.route('/upload', methods=['POST'])
@require_auth
def upload_file():
    """Upload a file to storage"""
    team_id = request.form.get('team_id')
    project_id = request.form.get('project_id')
    folder_id = request.form.get('folder_id')
    
    if not team_id:
        return error("team_id required", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    if 'file' not in request.files:
        return error("No file provided", 400)
    
    file = request.files['file']
    if not file.filename:
        return error("No filename", 400)
    
    file_data = file.read()
    file_size = len(file_data)
    content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
    
    # Validate file
    valid, msg = storage_service.validate_file(file.filename, content_type, file_size)
    if not valid:
        return error(msg, 400)
    
    # Check storage quota
    db = get_db()
    try:
        team_result = db.table('teams').select('storage_used_mb, storage_quota_mb').eq('id', team_id).single().execute()
        if team_result.data:
            team = team_result.data
            used_bytes = float(team['storage_used_mb'] or 0) * 1024 * 1024
            quota_bytes = int(team['storage_quota_mb'] or 5120) * 1024 * 1024
            if used_bytes + file_size > quota_bytes:
                return error("Storage quota exceeded", 413)
    except Exception as e:
        logger.error(f"Quota check error: {e}")
    
    try:
        file_id = str(uuid.uuid4())
        
        # Clean filename
        safe_name = file.filename.replace(' ', '_').replace('..', '_')
        
        # Build storage path
        storage_path = storage_service.build_path(
            team_id, project_id,
            file_id=file_id,
            filename=safe_name
        )
        
        # Upload to Supabase Storage
        upload_result = storage_service.upload_file(file_data, storage_path, content_type)
        
        # Compute checksum
        checksum = hashlib.md5(file_data).hexdigest()
        
        # Save metadata to database
        file_record = {
            'id': file_id,
            'team_id': team_id,
            'project_id': project_id,
            'folder_id': folder_id,
            'name': safe_name,
            'original_name': file.filename,
            'storage_path': storage_path,
            'mime_type': content_type,
            'size_bytes': file_size,
            'checksum': checksum,
            'uploaded_by': g.user['id'],
            'version': 1,
            'metadata': {
                'original_name': file.filename,
                'upload_source': 'web'
            }
        }
        
        db_result = db.table('files').insert(file_record).execute()
        
        if not db_result.data:
            # Cleanup storage on DB failure
            storage_service.delete_file(storage_path)
            return error("Failed to save file metadata", 500)
        
        saved_file = db_result.data[0]
        
        # Create first version record
        db.table('file_versions').insert({
            'file_id': file_id,
            'version': 1,
            'storage_path': storage_path,
            'size_bytes': file_size,
            'uploaded_by': g.user['id'],
            'change_note': 'Initial upload'
        }).execute()
        
        # Log storage access
        db.table('storage_access_logs').insert({
            'file_id': file_id,
            'user_id': g.user['id'],
            'team_id': team_id,
            'action': 'upload',
            'ip_address': request.remote_addr,
            'metadata': {'size_bytes': file_size, 'content_type': content_type}
        }).execute()
        
        # Activity log
        db.table('activities').insert({
            'team_id': team_id,
            'project_id': project_id,
            'user_id': g.user['id'],
            'type': 'file_uploaded',
            'entity_type': 'file',
            'entity_id': file_id,
            'description': f"Uploaded file: {file.filename}"
        }).execute()
        
        # Add to search index
        db.table('search_index').insert({
            'team_id': team_id,
            'entity_type': 'file',
            'entity_id': file_id,
            'title': file.filename,
            'content': f"{content_type} file",
            'tags': [content_type.split('/')[0]]
        }).execute()
        
        audit_log(g.user['id'], 'file_uploaded', 'file', file_id, team_id)
        
        return success({'file': saved_file}, "File uploaded successfully", 201)
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return error(f"Upload failed: {str(e)}", 500)


@storage_bp.route('/upload/chunk', methods=['POST'])
@require_auth
def upload_chunk():
    """Upload a file chunk (chunked upload for large files)"""
    team_id = request.form.get('team_id')
    session_id = request.form.get('session_id')
    chunk_index = request.form.get('chunk_index', type=int)
    total_chunks = request.form.get('total_chunks', type=int)
    
    if not all([team_id, session_id, chunk_index is not None, total_chunks]):
        return error("Missing chunked upload parameters", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    if 'chunk' not in request.files:
        return error("No chunk data", 400)
    
    chunk_data = request.files['chunk'].read()
    
    redis = get_redis()
    chunk_key = f"upload_chunk:{session_id}:{chunk_index}"
    
    # Store chunk in Redis temporarily (5 minute TTL per chunk)
    redis.setex(chunk_key, 300, chunk_data.hex())
    
    db = get_db()
    
    try:
        # Update session
        db.table('storage_upload_sessions').update({
            'chunks_received': chunk_index + 1,
            'uploaded_bytes': len(chunk_data) * (chunk_index + 1)
        }).eq('id', session_id).execute()
        
        # If last chunk, assemble and upload
        if chunk_index == total_chunks - 1:
            # Collect all chunks
            chunks = []
            for i in range(total_chunks):
                key = f"upload_chunk:{session_id}:{i}"
                hex_data = redis.get(key)
                if not hex_data:
                    return error(f"Chunk {i} missing", 400)
                chunks.append(bytes.fromhex(hex_data))
            
            file_data = b''.join(chunks)
            
            # Get session info
            session_result = db.table('storage_upload_sessions').select('*').eq('id', session_id).single().execute()
            session = session_result.data
            
            content_type = session['mime_type'] or 'application/octet-stream'
            filename = session['file_name']
            
            file_id = str(uuid.uuid4())
            storage_path = storage_service.build_path(team_id, None, file_id=file_id, filename=filename)
            
            upload_result = storage_service.upload_file(file_data, storage_path, content_type)
            
            db_result = db.table('files').insert({
                'id': file_id,
                'team_id': team_id,
                'name': filename,
                'original_name': filename,
                'storage_path': storage_path,
                'mime_type': content_type,
                'size_bytes': len(file_data),
                'uploaded_by': g.user['id'],
                'version': 1
            }).execute()
            
            # Update session status
            db.table('storage_upload_sessions').update({
                'status': 'completed',
                'storage_path': storage_path
            }).eq('id', session_id).execute()
            
            # Clean up Redis chunks
            for i in range(total_chunks):
                redis.delete(f"upload_chunk:{session_id}:{i}")
            
            return success({'file': db_result.data[0] if db_result.data else {}, 'complete': True})
        
        return success({'chunk': chunk_index, 'complete': False})
        
    except Exception as e:
        logger.error(f"Chunk upload error: {e}")
        return error("Chunk upload failed", 500)


@storage_bp.route('/upload/session', methods=['POST'])
@require_auth
def create_upload_session():
    """Create chunked upload session"""
    data = request.get_json()
    
    team_id = data.get('team_id')
    file_name = data.get('file_name')
    total_size = data.get('total_size', 0)
    mime_type = data.get('mime_type', 'application/octet-stream')
    chunk_count = data.get('chunk_count', 1)
    
    if not team_id or not file_name:
        return error("team_id and file_name required", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        session_id = str(uuid.uuid4())
        
        db.table('storage_upload_sessions').insert({
            'id': session_id,
            'team_id': team_id,
            'user_id': g.user['id'],
            'file_name': file_name,
            'mime_type': mime_type,
            'total_size_bytes': total_size,
            'chunk_count': chunk_count,
            'status': 'pending'
        }).execute()
        
        return success({'session_id': session_id})
        
    except Exception as e:
        return error("Failed to create upload session", 500)


@storage_bp.route('/signed-url/<file_id>', methods=['GET'])
@require_auth
def get_signed_url(file_id):
    """Get signed download URL for a file"""
    expires_in = request.args.get('expires', 3600, type=int)
    expires_in = min(expires_in, 86400)  # Max 24 hours
    
    db = get_db()
    
    try:
        file_result = db.table('files').select('*').eq('id', file_id).eq('is_deleted', False).single().execute()
        if not file_result.data:
            return error("File not found", 404)
        
        file = file_result.data
        
        # Verify access
        membership = verify_team_access(file['team_id'], g.user['id'])
        if not membership:
            return error("Access denied", 403)
        
        # Generate signed URL
        signed_url = storage_service.create_signed_url(file['storage_path'], expires_in)
        
        # Log access
        db.table('storage_access_logs').insert({
            'file_id': file_id,
            'user_id': g.user['id'],
            'team_id': file['team_id'],
            'action': 'download',
            'ip_address': request.remote_addr
        }).execute()
        
        return success({
            'url': signed_url,
            'expires_in': expires_in,
            'file': {
                'id': file['id'],
                'name': file['name'],
                'mime_type': file['mime_type'],
                'size_bytes': file['size_bytes']
            }
        })
        
    except Exception as e:
        logger.error(f"Signed URL error: {e}")
        return error("Failed to generate signed URL", 500)


@storage_bp.route('/files', methods=['GET'])
@require_auth
def list_files():
    """List files for a team/project/folder"""
    team_id = request.args.get('team_id')
    project_id = request.args.get('project_id')
    folder_id = request.args.get('folder_id')
    page, per_page = get_pagination_params()
    
    if not team_id:
        return error("team_id required", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        query = db.table('files').select(
            '*, uploader:users!files_uploaded_by_fkey(id, username, display_name, avatar_url)'
        ).eq('team_id', team_id).eq('is_deleted', False)
        
        if project_id:
            query = query.eq('project_id', project_id)
        
        if folder_id:
            query = query.eq('folder_id', folder_id)
        elif folder_id == '':
            query = query.is_('folder_id', 'null')
        
        result = query.order('created_at', desc=True)\
            .range((page-1)*per_page, page*per_page - 1)\
            .execute()
        
        return success({'files': result.data or []})
        
    except Exception as e:
        logger.error(f"List files error: {e}")
        return error("Failed to list files", 500)


@storage_bp.route('/files/<file_id>', methods=['GET'])
@require_auth
def get_file(file_id):
    """Get file metadata"""
    db = get_db()
    
    try:
        result = db.table('files').select('*').eq('id', file_id).eq('is_deleted', False).single().execute()
        if not result.data:
            return error("File not found", 404)
        
        file = result.data
        membership = verify_team_access(file['team_id'], g.user['id'])
        if not membership:
            return error("Access denied", 403)
        
        # Get versions
        versions = db.table('file_versions').select(
            '*, uploader:users!file_versions_uploaded_by_fkey(id, username, display_name)'
        ).eq('file_id', file_id).order('version', desc=True).execute()
        
        file['versions'] = versions.data or []
        
        # Generate signed URL
        try:
            file['download_url'] = storage_service.create_signed_url(file['storage_path'])
        except:
            file['download_url'] = None
        
        return success({'file': file})
        
    except Exception as e:
        logger.error(f"Get file error: {e}")
        return error("Failed to get file", 500)


@storage_bp.route('/files/<file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """Delete a file (soft delete)"""
    db = get_db()
    
    try:
        result = db.table('files').select('*').eq('id', file_id).single().execute()
        if not result.data:
            return error("File not found", 404)
        
        file = result.data
        membership = verify_team_access(file['team_id'], g.user['id'], 'delete')
        
        if not membership and file['uploaded_by'] != g.user['id']:
            return error("Permission denied", 403)
        
        # Soft delete
        db.table('files').update({'is_deleted': True}).eq('id', file_id).execute()
        
        # Log deletion
        db.table('storage_access_logs').insert({
            'file_id': file_id,
            'user_id': g.user['id'],
            'team_id': file['team_id'],
            'action': 'delete',
            'ip_address': request.remote_addr
        }).execute()
        
        # Remove from search index
        db.table('search_index').delete().eq('entity_id', file_id).execute()
        
        audit_log(g.user['id'], 'file_deleted', 'file', file_id, file['team_id'])
        
        return success(None, "File deleted")
        
    except Exception as e:
        logger.error(f"Delete file error: {e}")
        return error("Failed to delete file", 500)


@storage_bp.route('/files/<file_id>/version', methods=['POST'])
@require_auth
def upload_new_version(file_id):
    """Upload a new version of an existing file"""
    db = get_db()
    
    try:
        file_result = db.table('files').select('*').eq('id', file_id).eq('is_deleted', False).single().execute()
        if not file_result.data:
            return error("File not found", 404)
        
        file = file_result.data
        membership = verify_team_access(file['team_id'], g.user['id'])
        if not membership:
            return error("Access denied", 403)
        
        if 'file' not in request.files:
            return error("No file provided", 400)
        
        upload = request.files['file']
        file_data = upload.read()
        content_type = upload.content_type or file['mime_type']
        
        new_version = file['version'] + 1
        
        # Upload new version
        version_path = storage_service.upload_file_version(
            file_data, file['storage_path'], new_version, content_type
        )
        
        change_note = request.form.get('change_note', f'Version {new_version}')
        
        # Create version record
        db.table('file_versions').insert({
            'file_id': file_id,
            'version': new_version,
            'storage_path': version_path,
            'size_bytes': len(file_data),
            'uploaded_by': g.user['id'],
            'change_note': change_note
        }).execute()
        
        # Update current file
        db.table('files').update({
            'version': new_version,
            'size_bytes': len(file_data),
            'storage_path': version_path,
            'mime_type': content_type
        }).eq('id', file_id).execute()
        
        return success({'version': new_version}, "New version uploaded")
        
    except Exception as e:
        logger.error(f"Version upload error: {e}")
        return error("Failed to upload version", 500)


@storage_bp.route('/folders', methods=['GET'])
@require_auth
def list_folders():
    """List folders"""
    team_id = request.args.get('team_id')
    project_id = request.args.get('project_id')
    parent_id = request.args.get('parent_id')
    
    if not team_id:
        return error("team_id required", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        query = db.table('folders').select('*').eq('team_id', team_id)
        
        if project_id:
            query = query.eq('project_id', project_id)
        
        if parent_id:
            query = query.eq('parent_id', parent_id)
        else:
            query = query.is_('parent_id', 'null')
        
        result = query.order('name').execute()
        return success({'folders': result.data or []})
        
    except Exception as e:
        return error("Failed to list folders", 500)


@storage_bp.route('/folders', methods=['POST'])
@require_auth
def create_folder():
    """Create a folder"""
    data = request.get_json()
    
    team_id = data.get('team_id')
    name = data.get('name', '').strip()
    
    if not team_id or not name:
        return error("team_id and name required", 400)
    
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        parent_id = data.get('parent_id')
        
        # Build path
        path = name
        if parent_id:
            parent_result = db.table('folders').select('path').eq('id', parent_id).single().execute()
            if parent_result.data:
                path = f"{parent_result.data['path']}/{name}"
        
        result = db.table('folders').insert({
            'team_id': team_id,
            'project_id': data.get('project_id'),
            'name': name,
            'parent_id': parent_id,
            'created_by': g.user['id'],
            'path': path
        }).execute()
        
        return success({'folder': result.data[0] if result.data else {}}, "Folder created", 201)
        
    except Exception as e:
        logger.error(f"Create folder error: {e}")
        return error("Failed to create folder", 500)


@storage_bp.route('/quota/<team_id>', methods=['GET'])
@require_auth
def get_storage_quota(team_id):
    """Get team storage quota info"""
    membership = verify_team_access(team_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        team_result = db.table('teams').select('storage_used_mb, storage_quota_mb').eq('id', team_id).single().execute()
        
        if not team_result.data:
            return error("Team not found", 404)
        
        team = team_result.data
        
        file_count = db.table('files').select('id').eq('team_id', team_id).eq('is_deleted', False).execute()
        
        return success({
            'used_mb': float(team['storage_used_mb'] or 0),
            'quota_mb': int(team['storage_quota_mb'] or 5120),
            'files_count': len(file_count.data) if file_count.data else 0,
            'percentage': round((float(team['storage_used_mb'] or 0) / int(team['storage_quota_mb'] or 5120)) * 100, 1)
        })
        
    except Exception as e:
        return error("Failed to get quota", 500)