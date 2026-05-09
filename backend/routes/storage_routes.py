"""Storage routes mounted at /api/storage."""

import mimetypes

from flask import Blueprint, request, g

from backend.services.supabase_storage_service import storage_service
from backend.services.upload_service import process_upload, get_download_url, delete_file_record
from backend.utils.db import get_db
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id, now_iso, format_file_size
from backend.utils.security import require_auth, get_membership, audit_log


storage_bp = Blueprint('storage', __name__)


def _membership(team_id):
    if not team_id:
        return None
    return get_membership(g.user['id'], team_id)


def _resolve_team(team_id=None, project_id=None):
    db = get_db()
    if not team_id and project_id:
        project = db.table('projects').select('team_id').eq('id', project_id).single().execute()
        if project.data:
            team_id = project.data['team_id']
    if not team_id:
        return None, error('team_id is required', 400)
    if not _membership(team_id):
        return None, error('Not a team member', 403)
    if project_id:
        project = db.table('projects').select('id').eq('id', project_id).eq('team_id', team_id).single().execute()
        if not project.data:
            return None, error('Project not found in team', 404)
    return team_id, None


def _chunk_prefix(team_id, project_id, upload_id):
    return f"teams/{team_id}/projects/{project_id or 'shared'}/uploads/{upload_id}"


def _finalize_chunked_upload(upload_id, team_id, project_id, folder_id, filename, content_type, total_chunks):
    db = get_db()
    prefix = _chunk_prefix(team_id, project_id, upload_id)
    assembled = bytearray()
    for index in range(total_chunks):
        assembled.extend(storage_service.download_file(f"{prefix}/chunk-{index:05d}"))

    file_record, upload_error = process_upload(bytes(assembled), filename, content_type, g.user['id'], team_id, project_id, folder_id)
    if upload_error:
        return None, upload_error

    for index in range(total_chunks):
        storage_service.delete_file(f"{prefix}/chunk-{index:05d}")

    try:
        db.table('storage_upload_sessions').update({'status': 'completed', 'final_file_id': file_record['id'], 'updated_at': now_iso()}).eq('id', upload_id).execute()
    except Exception:
        pass

    return file_record, None


@storage_bp.route('/upload', methods=['POST'])
@require_auth
def upload_file():
    if 'file' not in request.files:
        return error('No file provided', 400)

    file_obj = request.files['file']
    team_id = request.form.get('team_id') or request.form.get('teamId')
    project_id = request.form.get('project_id') or request.form.get('projectId')
    folder_id = request.form.get('folder_id') or request.form.get('folderId')

    resolved_team_id, team_error = _resolve_team(team_id, project_id)
    if team_error:
        return team_error

    file_data = file_obj.read()
    if not file_data:
        return error('Uploaded file is empty', 400)

    content_type = file_obj.mimetype or mimetypes.guess_type(file_obj.filename or '')[0] or 'application/octet-stream'
    file_record, upload_error = process_upload(file_data, file_obj.filename or 'upload.bin', content_type, g.user['id'], resolved_team_id, project_id, folder_id)
    if upload_error:
        return error(upload_error, 400)

    audit_log(g.user['id'], 'storage_upload', 'file', file_record['id'], resolved_team_id)
    return success(data={'file': file_record}, message='File uploaded', status_code=201)


@storage_bp.route('/upload/chunk', methods=['POST'])
@require_auth
def upload_chunk():
    if 'file' not in request.files:
        return error('No file chunk provided', 400)

    chunk = request.files['file']
    upload_id = request.form.get('uploadId') or generate_id()
    chunk_index = request.form.get('chunkIndex', type=int)
    total_chunks = request.form.get('totalChunks', type=int)
    team_id = request.form.get('team_id') or request.form.get('teamId')
    project_id = request.form.get('project_id') or request.form.get('projectId')
    folder_id = request.form.get('folder_id') or request.form.get('folderId')
    filename = request.form.get('fileName') or chunk.filename or 'upload.bin'

    if chunk_index is None or total_chunks is None:
        return error('Missing chunk metadata', 400)

    resolved_team_id, team_error = _resolve_team(team_id, project_id)
    if team_error:
        return team_error

    content_type = chunk.mimetype or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    prefix = _chunk_prefix(resolved_team_id, project_id, upload_id)
    storage_service.upload_file(chunk.read(), f"{prefix}/chunk-{chunk_index:05d}", content_type)

    db = get_db()
    try:
        db.table('storage_upload_sessions').upsert({
            'id': upload_id,
            'team_id': resolved_team_id,
            'project_id': project_id,
            'folder_id': folder_id,
            'file_name': filename,
            'content_type': content_type,
            'total_chunks': total_chunks,
            'uploaded_chunks': chunk_index + 1,
            'status': 'uploading',
            'created_by': g.user['id'],
            'updated_at': now_iso(),
        }).execute()
    except Exception:
        pass

    if chunk_index + 1 == total_chunks:
        file_record, upload_error = _finalize_chunked_upload(upload_id, resolved_team_id, project_id, folder_id, filename, content_type, total_chunks)
        if upload_error:
            return error(upload_error, 400)

        audit_log(g.user['id'], 'storage_upload', 'file', file_record['id'], resolved_team_id)
        return success(data={'file': file_record, 'uploadId': upload_id, 'completed': True}, message='Chunked upload completed')

    return success(data={'uploadId': upload_id, 'chunkIndex': chunk_index, 'totalChunks': total_chunks, 'progress': round(((chunk_index + 1) / total_chunks) * 100, 2)}, message='Chunk uploaded')


@storage_bp.route('/upload/session', methods=['POST'])
@require_auth
def create_upload_session():
    data = request.get_json(silent=True) or {}
    ok, message = validate_required(data, ['team_id', 'filename'])
    if not ok:
        return error(message, 400)

    resolved_team_id, team_error = _resolve_team(data['team_id'], data.get('project_id'))
    if team_error:
        return team_error

    session = {
        'id': data.get('upload_id') or generate_id(),
        'team_id': resolved_team_id,
        'project_id': data.get('project_id'),
        'folder_id': data.get('folder_id'),
        'file_name': data['filename'],
        'content_type': data.get('content_type', 'application/octet-stream'),
        'total_chunks': data.get('total_chunks', 1),
        'uploaded_chunks': 0,
        'status': 'pending',
        'created_by': g.user['id'],
        'updated_at': now_iso(),
    }
    try:
        get_db().table('storage_upload_sessions').upsert(session).execute()
    except Exception:
        pass

    return success(data=session, message='Upload session created', status_code=201)


@storage_bp.route('/files', methods=['GET'])
@require_auth
def list_files():
    project_id = request.args.get('projectId') or request.args.get('project_id')
    team_id = request.args.get('teamId') or request.args.get('team_id')
    folder_id = request.args.get('folderId') or request.args.get('folder_id')
    resolved_team_id, team_error = _resolve_team(team_id, project_id)
    if team_error:
        return team_error

    db = get_db()
    query = db.table('files').select('*').eq('team_id', resolved_team_id).eq('is_deleted', False)
    if project_id:
        query = query.eq('project_id', project_id)
    if folder_id:
        query = query.eq('folder_id', folder_id)
    result = query.order('created_at', desc=True).execute()
    return success(data=result.data or [])


@storage_bp.route('/files/<file_id>', methods=['GET'])
@require_auth
def get_file(file_id):
    db = get_db()
    result = db.table('files').select('*').eq('id', file_id).single().execute()
    if not result.data:
        return error('File not found', 404)
    if not _membership(result.data['team_id']):
        return error('Not a team member', 403)
    return success(data=result.data)


@storage_bp.route('/files/<file_id>/download', methods=['GET'])
@require_auth
def download_file(file_id):
    db = get_db()
    result = db.table('files').select('team_id').eq('id', file_id).single().execute()
    if not result.data:
        return error('File not found', 404)
    if not _membership(result.data['team_id']):
        return error('Not a team member', 403)
    signed_url, download_error = get_download_url(file_id, g.user['id'], result.data['team_id'])
    if download_error:
        return error(download_error, 400)
    return success(data={'url': signed_url})


@storage_bp.route('/files/<file_id>/signed-url', methods=['GET'])
@require_auth
def file_signed_url(file_id):
    db = get_db()
    result = db.table('files').select('team_id,storage_path').eq('id', file_id).single().execute()
    if not result.data:
        return error('File not found', 404)
    if not _membership(result.data['team_id']):
        return error('Not a team member', 403)
    expiry = request.args.get('expiry', default=3600, type=int)
    return success(data={'signedUrl': storage_service.create_signed_url(result.data['storage_path'], expires_in=expiry), 'expiresIn': expiry})


@storage_bp.route('/files/<file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    db = get_db()
    result = db.table('files').select('*').eq('id', file_id).single().execute()
    if not result.data:
        return error('File not found', 404)
    if not _membership(result.data['team_id']):
        return error('Not a team member', 403)
    delete_error = delete_file_record(file_id, g.user['id'], result.data['team_id'])
    if delete_error:
        return error(delete_error, 400)
    audit_log(g.user['id'], 'storage_delete', 'file', file_id, result.data['team_id'])
    return success(message='File deleted')


@storage_bp.route('/files/<file_id>/version', methods=['POST'])
@require_auth
def create_version(file_id):
    if 'file' not in request.files:
        return error('No file provided', 400)

    file_obj = request.files['file']
    db = get_db()
    result = db.table('files').select('*').eq('id', file_id).single().execute()
    if not result.data:
        return error('File not found', 404)
    if not _membership(result.data['team_id']):
        return error('Not a team member', 403)

    file_bytes = file_obj.read()
    version_number = int(result.data.get('version', 1)) + 1
    content_type = file_obj.mimetype or mimetypes.guess_type(file_obj.filename or '')[0] or 'application/octet-stream'
    version_path = storage_service.upload_file_version(file_bytes, result.data['storage_path'], version_number, content_type)
    payload = {
        'id': generate_id(),
        'file_id': file_id,
        'version_number': version_number,
        'storage_path': version_path,
        'created_by': g.user['id'],
        'created_at': now_iso(),
        'mime_type': content_type,
        'file_name': file_obj.filename or result.data.get('name'),
        'size_bytes': len(file_bytes),
    }
    try:
        db.table('file_versions').insert(payload).execute()
        db.table('files').update({'version': version_number, 'updated_at': now_iso()}).eq('id', file_id).execute()
    except Exception:
        pass
    return success(data=payload, status_code=201)


@storage_bp.route('/folders', methods=['GET'])
@require_auth
def list_folders():
    team_id = request.args.get('teamId') or request.args.get('team_id')
    project_id = request.args.get('projectId') or request.args.get('project_id')
    resolved_team_id, team_error = _resolve_team(team_id, project_id)
    if team_error:
        return team_error
    db = get_db()
    query = db.table('folders').select('*').eq('team_id', resolved_team_id)
    if project_id:
        query = query.eq('project_id', project_id)
    result = query.order('created_at', desc=True).execute()
    return success(data=result.data or [])


@storage_bp.route('/folders', methods=['POST'])
@require_auth
def create_folder():
    data = request.get_json(silent=True) or {}
    ok, message = validate_required(data, ['team_id', 'name'])
    if not ok:
        return error(message, 400)
    resolved_team_id, team_error = _resolve_team(data['team_id'], data.get('project_id'))
    if team_error:
        return team_error
    folder = {
        'id': generate_id(),
        'team_id': resolved_team_id,
        'project_id': data.get('project_id'),
        'parent_id': data.get('parent_id'),
        'name': data['name'],
        'path': data.get('path'),
        'created_by': g.user['id'],
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }
    result = get_db().table('folders').insert(folder).execute()
    if not result.data:
        return error('Failed to create folder', 500)
    return success(data=result.data[0], status_code=201)


@storage_bp.route('/quota/<team_id>', methods=['GET'])
@require_auth
def quota(team_id):
    if not _membership(team_id):
        return error('Not a team member', 403)
    db = get_db()
    result = db.table('files').select('size_bytes').eq('team_id', team_id).eq('is_deleted', False).execute()
    items = result.data or []
    used_bytes = sum((item.get('size_bytes') or 0) for item in items)
    return success(data={'team_id': team_id, 'used_bytes': used_bytes, 'used_label': format_file_size(used_bytes), 'limit_bytes': 1000 * 1024 * 1024, 'limit_mb': 1000, 'file_count': len(items)})
