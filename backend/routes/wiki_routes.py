"""HackForge - Wiki Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id, slugify

wiki_bp = Blueprint('wiki', __name__)
logger = logging.getLogger(__name__)


@wiki_bp.route('/', methods=['GET'])
@require_auth
def list_pages():
    team_id = request.args.get('team_id')
    project_id = request.args.get('project_id')
    if not team_id:
        return error('team_id required')

    db = get_db()
    q = db.table('wiki_pages').select('id,title,slug,parent_id,order_index,created_at,updated_at,created_by').eq('team_id', team_id).eq('is_deleted', False)
    if project_id:
        q = q.eq('project_id', project_id)
    result = q.order('order_index').execute()
    return success(data=result.data or [])


@wiki_bp.route('/', methods=['POST'])
@require_auth
def create_page():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'title'])
    if not ok:
        return error(msg)

    db = get_db()
    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', data['team_id']).eq('is_active', True).execute()
    if not m.data:
        return error('Not a team member', 403)

    page = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'project_id': data.get('project_id'),
        'title': data['title'][:200],
        'slug': slugify(data['title']) + '-' + generate_id()[:6],
        'content': data.get('content', ''),
        'parent_id': data.get('parent_id'),
        'order_index': data.get('order_index', 0),
        'created_by': g.user['id'],
        'is_deleted': False
    }
    result = db.table('wiki_pages').insert(page).execute()
    if not result.data:
        return error('Failed to create page', 500)

    # Save initial revision
    db.table('wiki_revisions').insert({
        'id': generate_id(),
        'page_id': page['id'],
        'content': page['content'],
        'edited_by': g.user['id'],
        'version': 1,
        'change_summary': 'Initial version'
    }).execute()

    return success(data=result.data[0], status=201)


@wiki_bp.route('/<page_id>', methods=['GET'])
@require_auth
def get_page(page_id):
    db = get_db()
    result = db.table('wiki_pages').select('*').eq('id', page_id).eq('is_deleted', False).single().execute()
    if not result.data:
        return error('Page not found', 404)
    return success(data=result.data)


@wiki_bp.route('/<page_id>', methods=['PATCH'])
@require_auth
def update_page(page_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    allowed = ['title', 'content', 'parent_id', 'order_index']
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        return error('No valid fields')

    result = db.table('wiki_pages').update(update).eq('id', page_id).execute()

    # Save revision if content changed
    if 'content' in update:
        prev = db.table('wiki_revisions').select('version').eq('page_id', page_id).order('version', desc=True).limit(1).execute()
        version = (prev.data[0]['version'] + 1) if prev.data else 1
        db.table('wiki_revisions').insert({
            'id': generate_id(),
            'page_id': page_id,
            'content': update['content'],
            'edited_by': g.user['id'],
            'version': version,
            'change_summary': data.get('change_summary', 'Updated')
        }).execute()

    return success(data=result.data[0] if result.data else {})


@wiki_bp.route('/<page_id>', methods=['DELETE'])
@require_auth
def delete_page(page_id):
    db = get_db()
    db.table('wiki_pages').update({'is_deleted': True}).eq('id', page_id).execute()
    return success(message='Page deleted')


@wiki_bp.route('/<page_id>/revisions', methods=['GET'])
@require_auth
def get_revisions(page_id):
    db = get_db()
    result = db.table('wiki_revisions').select('id,version,edited_by,change_summary,created_at').eq('page_id', page_id).order('version', desc=True).execute()
    return success(data=result.data or [])