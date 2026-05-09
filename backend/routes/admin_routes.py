"""HackForge - Admin Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, get_pagination_params

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user.get('is_admin'):
            return error('Admin access required', 403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@require_auth
@require_admin
def list_users():
    page, per_page = get_pagination_params()
    db = get_db()
    result = db.table('users').select('id,username,email,full_name,is_active,created_at').order('created_at', desc=True).range((page-1)*per_page, page*per_page-1).execute()
    return success(data=result.data or [])


@admin_bp.route('/users/<user_id>/toggle', methods=['POST'])
@require_auth
@require_admin
def toggle_user(user_id):
    db = get_db()
    user = db.table('users').select('is_active').eq('id', user_id).single().execute()
    if not user.data:
        return error('User not found', 404)
    new_state = not user.data['is_active']
    db.table('users').update({'is_active': new_state}).eq('id', user_id).execute()
    return success(message=f"User {'activated' if new_state else 'deactivated'}")


@admin_bp.route('/teams', methods=['GET'])
@require_auth
@require_admin
def list_teams():
    db = get_db()
    result = db.table('teams').select('*').order('created_at', desc=True).limit(100).execute()
    return success(data=result.data or [])


@admin_bp.route('/audit-logs', methods=['GET'])
@require_auth
@require_admin
def audit_logs():
    page, per_page = get_pagination_params()
    db = get_db()
    result = db.table('audit_logs').select('*, users(username)').order('created_at', desc=True).range((page-1)*per_page, page*per_page-1).execute()
    return success(data=result.data or [])


@admin_bp.route('/stats', methods=['GET'])
@require_auth
@require_admin
def platform_stats():
    db = get_db()
    users = db.table('users').select('id', count='exact').execute()
    teams = db.table('teams').select('id', count='exact').execute()
    tasks = db.table('tasks').select('id', count='exact').execute()
    files = db.table('files').select('id', count='exact').execute()
    return success(data={
        'users': users.count or 0,
        'teams': teams.count or 0,
        'tasks': tasks.count or 0,
        'files': files.count or 0
    })


@admin_bp.route('/feature-flags', methods=['GET'])
@require_auth
@require_admin
def get_feature_flags():
    db = get_db()
    result = db.table('feature_flags').select('*').execute()
    return success(data=result.data or [])


@admin_bp.route('/feature-flags/<flag_name>', methods=['PATCH'])
@require_auth
@require_admin
def toggle_flag(flag_name):
    data = request.get_json(silent=True) or {}
    db = get_db()
    db.table('feature_flags').upsert({
        'name': flag_name,
        'enabled': data.get('enabled', False),
        'description': data.get('description', '')
    }).execute()
    return success(message='Feature flag updated')