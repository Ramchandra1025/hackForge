"""HackForge - User Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth, audit_log
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.redis_client import cache_set, cache_get, cache_delete

user_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)


@user_bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    return success(data=g.user)


@user_bp.route('/me', methods=['PATCH'])
@require_auth
def update_me():
    data = request.get_json(silent=True) or {}
    allowed = ['full_name', 'username', 'bio', 'avatar_url', 'github_url',
               'portfolio_url', 'skills', 'timezone', 'preferences']
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        return error('No valid fields to update')

    db = get_db()
    result = db.table('users').update(update).eq('id', g.user['id']).execute()
    if not result.data:
        return error('Update failed', 500)

    cache_delete(f"user:{g.user['id']}")
    audit_log(g.user['id'], 'profile_update')
    return success(data=result.data[0], message='Profile updated')


@user_bp.route('/me/password', methods=['PUT'])
@require_auth
def change_password():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['current_password', 'new_password'])
    if not ok:
        return error(msg)

    from backend.utils.security import verify_password, hash_password, validate_password
    db = get_db()
    user_result = db.table('users').select('password_hash').eq('id', g.user['id']).single().execute()
    if not user_result.data:
        return error('User not found', 404)

    if not verify_password(data['current_password'], user_result.data['password_hash']):
        return error('Current password is incorrect', 401)

    valid, msg = validate_password(data['new_password'])
    if not valid:
        return error(msg)

    new_hash = hash_password(data['new_password'])
    db.table('users').update({'password_hash': new_hash}).eq('id', g.user['id']).execute()
    audit_log(g.user['id'], 'password_change')
    return success(message='Password changed successfully')


@user_bp.route('/me/sessions', methods=['GET'])
@require_auth
def get_sessions():
    db = get_db()
    result = db.table('login_sessions').select('id,device_info,ip_address,created_at,last_active').eq('user_id', g.user['id']).eq('is_active', True).order('created_at', desc=True).execute()
    return success(data=result.data or [])


@user_bp.route('/me/sessions/<session_id>', methods=['DELETE'])
@require_auth
def revoke_session(session_id):
    db = get_db()
    db.table('login_sessions').update({'is_active': False}).eq('id', session_id).eq('user_id', g.user['id']).execute()
    return success(message='Session revoked')


@user_bp.route('/me/sessions', methods=['DELETE'])
@require_auth
def revoke_all_sessions():
    db = get_db()
    db.table('login_sessions').update({'is_active': False}).eq('user_id', g.user['id']).execute()
    return success(message='All sessions revoked')


@user_bp.route('/search', methods=['GET'])
@require_auth
def search_users():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return error('Query too short')

    db = get_db()
    result = db.table('users').select('id,username,full_name,avatar_url,bio').ilike('username', f'%{q}%').limit(10).execute()
    return success(data=result.data or [])


@user_bp.route('/<user_id>/profile', methods=['GET'])
@require_auth
def get_profile(user_id):
    db = get_db()
    result = db.table('users').select(
        'id,username,full_name,avatar_url,bio,skills,github_url,portfolio_url,created_at'
    ).eq('id', user_id).single().execute()
    if not result.data:
        return error('User not found', 404)
    return success(data=result.data)


@user_bp.route('/me/notifications/settings', methods=['GET'])
@require_auth
def get_notification_settings():
    db = get_db()
    result = db.table('settings').select('value').eq('user_id', g.user['id']).eq('key', 'notifications').single().execute()
    defaults = {
        'email_mentions': True, 'email_tasks': True,
        'push_mentions': True, 'push_tasks': True,
        'sound_enabled': True
    }
    return success(data=result.data['value'] if result.data else defaults)


@user_bp.route('/me/notifications/settings', methods=['PUT'])
@require_auth
def update_notification_settings():
    data = request.get_json(silent=True) or {}
    db = get_db()
    db.table('settings').upsert({
        'user_id': g.user['id'],
        'key': 'notifications',
        'value': data
    }).execute()
    return success(message='Notification settings updated')