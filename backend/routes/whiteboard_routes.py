"""HackForge - Whiteboard Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id

whiteboard_bp = Blueprint('whiteboards', __name__)
logger = logging.getLogger(__name__)


@whiteboard_bp.route('/', methods=['GET'])
@require_auth
def list_whiteboards():
    project_id = request.args.get('project_id')
    team_id = request.args.get('team_id')
    db = get_db()
    q = db.table('whiteboards').select('id,name,team_id,project_id,created_by,created_at,updated_at,thumbnail_url')
    if project_id:
        q = q.eq('project_id', project_id)
    elif team_id:
        q = q.eq('team_id', team_id)
    result = q.order('updated_at', desc=True).execute()
    return success(data=result.data or [])


@whiteboard_bp.route('/', methods=['POST'])
@require_auth
def create_whiteboard():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'name'])
    if not ok:
        return error(msg)

    db = get_db()
    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', data['team_id']).eq('is_active', True).execute()
    if not m.data:
        return error('Not a team member', 403)

    wb = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'project_id': data.get('project_id'),
        'name': data['name'][:100],
        'created_by': g.user['id'],
        'canvas_data': data.get('canvas_data', {}),
        'width': data.get('width', 3000),
        'height': data.get('height', 2000)
    }
    result = db.table('whiteboards').insert(wb).execute()
    return success(data=result.data[0] if result.data else wb, status=201)


@whiteboard_bp.route('/<wb_id>', methods=['GET'])
@require_auth
def get_whiteboard(wb_id):
    db = get_db()
    result = db.table('whiteboards').select('*').eq('id', wb_id).single().execute()
    if not result.data:
        return error('Whiteboard not found', 404)
    return success(data=result.data)


@whiteboard_bp.route('/<wb_id>', methods=['PATCH'])
@require_auth
def update_whiteboard(wb_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    allowed = ['name', 'canvas_data', 'thumbnail_url']
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        return error('No valid fields')
    result = db.table('whiteboards').update(update).eq('id', wb_id).execute()
    return success(data=result.data[0] if result.data else {})


@whiteboard_bp.route('/<wb_id>', methods=['DELETE'])
@require_auth
def delete_whiteboard(wb_id):
    db = get_db()
    db.table('whiteboards').delete().eq('id', wb_id).execute()
    return success(message='Whiteboard deleted')


@whiteboard_bp.route('/<wb_id>/events', methods=['GET'])
@require_auth
def get_events(wb_id):
    db = get_db()
    since = request.args.get('since')
    q = db.table('whiteboard_events').select('*').eq('whiteboard_id', wb_id).order('created_at').limit(500)
    if since:
        q = q.gt('created_at', since)
    result = q.execute()
    return success(data=result.data or [])


@whiteboard_bp.route('/<wb_id>/events', methods=['POST'])
@require_auth
def save_event(wb_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    event = {
        'id': generate_id(),
        'whiteboard_id': wb_id,
        'user_id': g.user['id'],
        'event_type': data.get('type', 'draw'),
        'event_data': data.get('data', {}),
        'version': data.get('version', 1)
    }
    result = db.table('whiteboard_events').insert(event).execute()
    return success(data=result.data[0] if result.data else event, status=201)