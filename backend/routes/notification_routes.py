"""HackForge - Notification Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, get_pagination_params
from backend.utils.helpers import generate_id

notification_bp = Blueprint('notifications', __name__)
logger = logging.getLogger(__name__)


@notification_bp.route('/', methods=['GET'])
@require_auth
def list_notifications():
    page, per_page = get_pagination_params()
    unread_only = request.args.get('unread') == 'true'
    db = get_db()
    q = db.table('notifications').select('*').eq('user_id', g.user['id'])
    if unread_only:
        q = q.eq('is_read', False)
    q = q.order('created_at', desc=True).range((page-1)*per_page, page*per_page - 1)
    result = q.execute()
    unread_count = db.table('notifications').select('id', count='exact').eq('user_id', g.user['id']).eq('is_read', False).execute()
    return success(data={
        'notifications': result.data or [],
        'unread_count': unread_count.count or 0
    })


@notification_bp.route('/<notif_id>/read', methods=['POST'])
@require_auth
def mark_read(notif_id):
    db = get_db()
    db.table('notifications').update({'is_read': True}).eq('id', notif_id).eq('user_id', g.user['id']).execute()
    return success(message='Marked as read')


@notification_bp.route('/read-all', methods=['POST'])
@require_auth
def mark_all_read():
    db = get_db()
    db.table('notifications').update({'is_read': True}).eq('user_id', g.user['id']).eq('is_read', False).execute()
    return success(message='All notifications marked as read')


@notification_bp.route('/<notif_id>', methods=['DELETE'])
@require_auth
def delete_notification(notif_id):
    db = get_db()
    db.table('notifications').delete().eq('id', notif_id).eq('user_id', g.user['id']).execute()
    return success(message='Notification deleted')


@notification_bp.route('/', methods=['DELETE'])
@require_auth
def delete_all_notifications():
    db = get_db()
    db.table('notifications').delete().eq('user_id', g.user['id']).eq('is_read', True).execute()
    return success(message='Read notifications deleted')