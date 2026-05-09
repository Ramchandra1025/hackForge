"""HackForge - Chat Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth, audit_log
from backend.utils.error_handlers import success, error, validate_required, get_pagination_params
from backend.utils.helpers import generate_id, now_iso

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)


def verify_team_member(user_id, team_id):
    db = get_db()
    m = db.table('memberships').select('role').eq('user_id', user_id).eq('team_id', team_id).eq('is_active', True).execute()
    return m.data[0] if m.data else None


@chat_bp.route('/rooms', methods=['GET'])
@require_auth
def list_rooms():
    team_id = request.args.get('team_id')
    if not team_id:
        return error('team_id required')

    if not verify_team_member(g.user['id'], team_id):
        return error('Access denied', 403)

    db = get_db()
    result = db.table('chat_rooms').select('*').eq('team_id', team_id).eq('is_archived', False).order('created_at').execute()
    return success(data=result.data or [])


@chat_bp.route('/rooms', methods=['POST'])
@require_auth
def create_room():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'name'])
    if not ok:
        return error(msg)

    membership = verify_team_member(g.user['id'], data['team_id'])
    if not membership:
        return error('Not a team member', 403)

    db = get_db()
    room = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'name': data['name'][:50],
        'description': data.get('description', '')[:200],
        'type': data.get('type', 'public'),
        'created_by': g.user['id'],
        'is_archived': False
    }
    result = db.table('chat_rooms').insert(room).execute()
    return success(data=result.data[0] if result.data else room, status=201)


@chat_bp.route('/rooms/<room_id>/messages', methods=['GET'])
@require_auth
def get_messages(room_id):
    db = get_db()
    room = db.table('chat_rooms').select('team_id').eq('id', room_id).single().execute()
    if not room.data:
        return error('Room not found', 404)

    if not verify_team_member(g.user['id'], room.data['team_id']):
        return error('Access denied', 403)

    page, per_page = get_pagination_params()
    before = request.args.get('before')  # cursor-based pagination

    query = db.table('chat_messages').select(
        '*, users(id,username,full_name,avatar_url)'
    ).eq('room_id', room_id).eq('is_deleted', False).order('created_at', desc=True).limit(per_page)

    if before:
        query = query.lt('created_at', before)

    result = query.execute()
    messages = list(reversed(result.data or []))
    return success(data=messages)


@chat_bp.route('/rooms/<room_id>/messages', methods=['POST'])
@require_auth
def send_message(room_id):
    data = request.get_json(silent=True) or {}
    if not data.get('content') and not data.get('file_id'):
        return error('Message content or file required')

    db = get_db()
    room = db.table('chat_rooms').select('team_id').eq('id', room_id).single().execute()
    if not room.data:
        return error('Room not found', 404)

    if not verify_team_member(g.user['id'], room.data['team_id']):
        return error('Access denied', 403)

    msg = {
        'id': generate_id(),
        'room_id': room_id,
        'user_id': g.user['id'],
        'content': data.get('content', '')[:4000],
        'message_type': data.get('type', 'text'),
        'thread_id': data.get('thread_id'),
        'file_id': data.get('file_id'),
        'mentions': data.get('mentions', []),
        'is_deleted': False
    }
    result = db.table('chat_messages').insert(msg).execute()
    if not result.data:
        return error('Failed to send message', 500)

    # Notify mentioned users
    for uid in data.get('mentions', []):
        try:
            db.table('notifications').insert({
                'id': generate_id(),
                'user_id': uid,
                'type': 'mention',
                'title': f"{g.user.get('username', 'Someone')} mentioned you",
                'body': data.get('content', '')[:100],
                'data': {'room_id': room_id, 'message_id': msg['id']},
                'is_read': False
            }).execute()
        except Exception:
            pass

    return success(data=result.data[0], status=201)


@chat_bp.route('/messages/<msg_id>/reactions', methods=['POST'])
@require_auth
def add_reaction(msg_id):
    data = request.get_json(silent=True) or {}
    if not data.get('emoji'):
        return error('emoji required')

    db = get_db()
    # Toggle reaction
    existing = db.table('message_reactions').select('id').eq('message_id', msg_id).eq('user_id', g.user['id']).eq('emoji', data['emoji']).execute()

    if existing.data:
        db.table('message_reactions').delete().eq('id', existing.data[0]['id']).execute()
        return success(message='Reaction removed')
    else:
        db.table('message_reactions').insert({
            'id': generate_id(),
            'message_id': msg_id,
            'user_id': g.user['id'],
            'emoji': data['emoji'][:10]
        }).execute()
        return success(message='Reaction added')


@chat_bp.route('/messages/<msg_id>', methods=['DELETE'])
@require_auth
def delete_message(msg_id):
    db = get_db()
    msg = db.table('chat_messages').select('user_id').eq('id', msg_id).single().execute()
    if not msg.data:
        return error('Message not found', 404)
    if msg.data['user_id'] != g.user['id']:
        return error('Cannot delete others messages', 403)

    db.table('chat_messages').update({'is_deleted': True, 'content': '[deleted]'}).eq('id', msg_id).execute()
    return success(message='Message deleted')