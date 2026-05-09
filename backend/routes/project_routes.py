"""HackForge - Project Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth, require_team_member, audit_log
from backend.utils.error_handlers import success, error, validate_required, get_pagination_params
from backend.utils.helpers import generate_id, now_iso, slugify
from backend.utils.constants import PROJECT_STATUSES

project_bp = Blueprint('projects', __name__)
logger = logging.getLogger(__name__)


@project_bp.route('/', methods=['GET'])
@require_auth
def list_projects():
    team_id = request.args.get('team_id')
    if not team_id:
        return error('team_id required')

    db = get_db()
    # Verify membership
    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', team_id).eq('is_active', True).execute()
    if not m.data:
        return error('Not a team member', 403)

    result = db.table('projects').select('*').eq('team_id', team_id).eq('is_archived', False).order('created_at', desc=True).execute()
    return success(data=result.data or [])


@project_bp.route('/', methods=['POST'])
@require_auth
def create_project():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'name'])
    if not ok:
        return error(msg)

    db = get_db()
    m = db.table('memberships').select('role').eq('user_id', g.user['id']).eq('team_id', data['team_id']).eq('is_active', True).single().execute()
    if not m.data:
        return error('Not a team member', 403)
    if m.data['role'] not in ['owner', 'admin', 'developer']:
        return error('Insufficient permissions', 403)

    project = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'name': data['name'][:100],
        'description': data.get('description', '')[:500],
        'slug': slugify(data['name']),
        'color': data.get('color', '#6366f1'),
        'status': 'planning',
        'tech_stack': data.get('tech_stack', []),
        'created_by': g.user['id'],
        'is_archived': False
    }
    result = db.table('projects').insert(project).execute()
    if not result.data:
        return error('Failed to create project', 500)

    # Add creator as project member
    db.table('project_members').insert({
        'project_id': project['id'],
        'user_id': g.user['id'],
        'role': 'lead'
    }).execute()

    audit_log(g.user['id'], 'project_create', 'project', project['id'], data['team_id'])
    return success(data=result.data[0], message='Project created', status=201)


@project_bp.route('/<project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    db = get_db()
    result = db.table('projects').select('*').eq('id', project_id).single().execute()
    if not result.data:
        return error('Project not found', 404)
    
    # Verify team membership
    proj = result.data
    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', proj['team_id']).eq('is_active', True).execute()
    if not m.data:
        return error('Access denied', 403)

    return success(data=proj)


@project_bp.route('/<project_id>', methods=['PATCH'])
@require_auth
def update_project(project_id):
    db = get_db()
    proj = db.table('projects').select('team_id').eq('id', project_id).single().execute()
    if not proj.data:
        return error('Project not found', 404)

    m = db.table('memberships').select('role').eq('user_id', g.user['id']).eq('team_id', proj.data['team_id']).eq('is_active', True).single().execute()
    if not m.data or m.data['role'] not in ['owner', 'admin', 'developer']:
        return error('Insufficient permissions', 403)

    data = request.get_json(silent=True) or {}
    allowed = ['name', 'description', 'color', 'status', 'tech_stack', 'github_url', 'deploy_url', 'deadline']
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        return error('No valid fields')

    if 'status' in update and update['status'] not in PROJECT_STATUSES:
        return error(f'Invalid status. Must be one of: {", ".join(PROJECT_STATUSES)}')

    result = db.table('projects').update(update).eq('id', project_id).execute()
    return success(data=result.data[0] if result.data else {}, message='Project updated')


@project_bp.route('/<project_id>', methods=['DELETE'])
@require_auth
def delete_project(project_id):
    db = get_db()
    proj = db.table('projects').select('team_id').eq('id', project_id).single().execute()
    if not proj.data:
        return error('Project not found', 404)

    m = db.table('memberships').select('role').eq('user_id', g.user['id']).eq('team_id', proj.data['team_id']).eq('is_active', True).single().execute()
    if not m.data or m.data['role'] not in ['owner', 'admin']:
        return error('Insufficient permissions', 403)

    db.table('projects').update({'is_archived': True}).eq('id', project_id).execute()
    audit_log(g.user['id'], 'project_delete', 'project', project_id, proj.data['team_id'])
    return success(message='Project archived')


@project_bp.route('/<project_id>/members', methods=['GET'])
@require_auth
def get_project_members(project_id):
    db = get_db()
    result = db.table('project_members').select('*, users(id,username,full_name,avatar_url)').eq('project_id', project_id).execute()
    return success(data=result.data or [])


@project_bp.route('/<project_id>/members', methods=['POST'])
@require_auth
def add_project_member(project_id):
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['user_id'])
    if not ok:
        return error(msg)

    db = get_db()
    db.table('project_members').upsert({
        'project_id': project_id,
        'user_id': data['user_id'],
        'role': data.get('role', 'member')
    }).execute()
    return success(message='Member added')


@project_bp.route('/<project_id>/stats', methods=['GET'])
@require_auth
def project_stats(project_id):
    db = get_db()
    tasks = db.table('tasks').select('status').eq('project_id', project_id).execute()
    task_data = tasks.data or []
    stats = {
        'total': len(task_data),
        'by_status': {}
    }
    for t in task_data:
        s = t.get('status', 'unknown')
        stats['by_status'][s] = stats['by_status'].get(s, 0) + 1
    return success(data=stats)