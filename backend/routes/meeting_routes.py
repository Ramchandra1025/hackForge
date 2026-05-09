"""HackForge - Meeting Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id

meeting_bp = Blueprint('meetings', __name__)
logger = logging.getLogger(__name__)


@meeting_bp.route('/', methods=['GET'])
@require_auth
def list_meetings():
    team_id = request.args.get('team_id')
    if not team_id:
        return error('team_id required')
    db = get_db()
    result = db.table('meetings').select('*').eq('team_id', team_id).order('scheduled_at', desc=True).limit(20).execute()
    return success(data=result.data or [])


@meeting_bp.route('/', methods=['POST'])
@require_auth
def create_meeting():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'title'])
    if not ok:
        return error(msg)

    db = get_db()
    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', data['team_id']).eq('is_active', True).execute()
    if not m.data:
        return error('Not a team member', 403)

    room_id = generate_id()
    meeting = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'title': data['title'][:200],
        'description': data.get('description', ''),
        'scheduled_at': data.get('scheduled_at'),
        'duration_minutes': data.get('duration_minutes', 60),
        'jitsi_room_id': room_id,
        'jitsi_room_url': f"https://meet.jit.si/hackforge-{room_id}",
        'created_by': g.user['id'],
        'status': 'scheduled'
    }
    result = db.table('meetings').insert(meeting).execute()
    if not result.data:
        return error('Failed to create meeting', 500)

    meet = result.data[0]
    # Add creator as participant
    db.table('meeting_participants').insert({
        'id': generate_id(),
        'meeting_id': meet['id'],
        'user_id': g.user['id'],
        'role': 'host'
    }).execute()

    return success(data=meet, status=201)


@meeting_bp.route('/<meeting_id>', methods=['GET'])
@require_auth
def get_meeting(meeting_id):
    db = get_db()
    result = db.table('meetings').select('*').eq('id', meeting_id).single().execute()
    if not result.data:
        return error('Meeting not found', 404)
    participants = db.table('meeting_participants').select('*, users(username,full_name,avatar_url)').eq('meeting_id', meeting_id).execute()
    data = result.data
    data['participants'] = participants.data or []
    return success(data=data)


@meeting_bp.route('/<meeting_id>/join', methods=['POST'])
@require_auth
def join_meeting(meeting_id):
    db = get_db()
    meeting = db.table('meetings').select('jitsi_room_url,team_id').eq('id', meeting_id).single().execute()
    if not meeting.data:
        return error('Meeting not found', 404)

    m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', meeting.data['team_id']).eq('is_active', True).execute()
    if not m.data:
        return error('Access denied', 403)

    db.table('meeting_participants').upsert({
        'id': generate_id(),
        'meeting_id': meeting_id,
        'user_id': g.user['id'],
        'role': 'attendee',
        'joined_at': 'now()'
    }).execute()

    return success(data={'jitsi_room_url': meeting.data['jitsi_room_url']})


@meeting_bp.route('/<meeting_id>', methods=['DELETE'])
@require_auth
def cancel_meeting(meeting_id):
    db = get_db()
    db.table('meetings').update({'status': 'cancelled'}).eq('id', meeting_id).execute()
    return success(message='Meeting cancelled')