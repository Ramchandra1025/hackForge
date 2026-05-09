"""
HackForge - Team Routes (Production - Schema Safe)
"""

import logging
import secrets
from flask import Blueprint, request, g

from slugify import slugify
from backend.utils.db import get_db
from backend.services.supabase_service import filter_fields
from backend.utils.security import (
    require_auth, get_membership, has_permission, audit_log
)
from backend.utils.error_handlers import success, error, validate_required

team_bp = Blueprint('teams', __name__)
logger = logging.getLogger(__name__)


@team_bp.route('', methods=['POST'])
@require_auth
def create_team():
    """Create new team."""
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        
        if not name:
            return error("Team name required", 400)

        db = get_db()
        if not db:
            return error("Database unavailable", 503)

        user_id = g.user['id']
        base_slug = slugify(name)
        slug = base_slug
        counter = 1

        while True:
            existing = db.table('teams').select('id').eq('slug', slug).execute()
            if not existing.data:
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        join_code = secrets.token_urlsafe(6).upper()[:10]

        team_data = {
            'name': name,
            'slug': slug,
            'description': data.get('description', ''),
            'owner_id': user_id,
            'created_by': user_id,
            'join_code': join_code,
            'max_members': data.get('max_members', 10),
            'is_active': True
        }

        filtered = filter_fields('teams', team_data)
        result = db.table('teams').insert(filtered).execute()

        if not result.data:
            return error("Team creation failed", 500)

        team = result.data[0]

        membership_data = {
            'team_id': team['id'],
            'user_id': user_id,
            'role': 'owner',
            'is_active': True
        }
        filtered_mem = filter_fields('memberships', membership_data)
        db.table('memberships').insert(filtered_mem).execute()

        try:
            chat_data = {
                'team_id': team['id'],
                'name': 'general',
                'type': 'channel',
                'is_private': False,
                'created_by': user_id
            }
            filtered_chat = filter_fields('chat_rooms', chat_data)
            db.table('chat_rooms').insert(filtered_chat).execute()
        except Exception as e:
            logger.warning(f"Chat room creation failed: {e}")

        audit_log(user_id, 'team_created', 'team', team['id'], team['id'])
        return success({'team': team}, "Team created", 201)

    except Exception as e:
        logger.error(f"Create team error: {e}")
        return error("Internal server error", 500)


@team_bp.route('', methods=['GET'])
@require_auth
def get_my_teams():
    """Get user's teams."""
    try:
        db = get_db()
        if not db:
            return error("Database unavailable", 503)

        result = db.table('memberships').select(
            '*, teams(*)'
        ).eq('user_id', g.user['id']).eq('is_active', True).execute()

        teams = []
        for m in (result.data or []):
            team = m.get('teams') or {}
            team['my_role'] = m.get('role')
            teams.append(team)

        return success({'teams': teams})

    except Exception as e:
        logger.error(f"Get teams error: {e}")
        return error("Failed to get teams", 500)


@team_bp.route('/<team_id>', methods=['GET'])
@require_auth
def get_team(team_id):
    """Get team details."""
    membership = get_membership(g.user['id'], team_id)
    if not membership:
        return error("Not a team member", 403)

    db = get_db()
    if not db:
        return error("Database unavailable", 503)

    try:
        team_result = db.table('teams').select('*').eq('id', team_id).single().execute()
        if not team_result.data:
            return error("Team not found", 404)

        team = team_result.data
        team['my_role'] = membership['role']

        members_result = db.table('memberships').select('id').eq('team_id', team_id).eq('is_active', True).execute()
        team['member_count'] = len(members_result.data or [])

        return success({'team': team})

    except Exception as e:
        logger.error(f"Get team error: {e}")
        return error("Failed to get team", 500)


@team_bp.route('/<team_id>', methods=['PATCH'])
@require_auth
def update_team(team_id):
    """Update team details."""
    membership = get_membership(g.user['id'], team_id)
    if not membership or not has_permission(membership['role'], 'manage_tasks'):
        return error("Permission denied", 403)

    data = request.get_json() or {}
    allowed = ['name', 'description', 'avatar_url', 'settings']
    update_data = {k: v for k, v in data.items() if k in allowed}

    if not update_data:
        return error("No valid fields", 400)

    db = get_db()
    if not db:
        return error("Database unavailable", 503)

    try:
        filtered = filter_fields('teams', update_data)
        result = db.table('teams').update(filtered).eq('id', team_id).execute()
        audit_log(g.user['id'], 'team_updated', 'team', team_id, team_id)
        return success({'team': result.data[0] if result.data else {}}, "Updated")
    except Exception as e:
        logger.error(f"Update team error: {e}")
        return error("Failed to update team", 500)


@team_bp.route('/<team_id>/invite', methods=['POST'])
@require_auth
def invite_member(team_id):
    """Invite member to team."""
    membership = get_membership(g.user['id'], team_id)
    if not membership or not has_permission(membership['role'], 'invite'):
        return error("Permission denied", 403)

    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    role = data.get('role', 'developer')

    if not email:
        return error("Email required", 400)

    db = get_db()
    if not db:
        return error("Database unavailable", 503)

    try:
        members_count = db.table('memberships').select('id').eq('team_id', team_id).eq('is_active', True).execute()
        team_result = db.table('teams').select('max_members').eq('id', team_id).single().execute()

        if len(members_count.data or []) >= (team_result.data or {}).get('max_members', 10):
            return error("Team full", 400)

        invite_data = {
            'team_id': team_id,
            'email': email,
            'role': role,
            'token': secrets.token_urlsafe(32),
            'invited_by': g.user['id'],
            'is_used': False
        }
        filtered = filter_fields('team_invites', invite_data)
        db.table('team_invites').insert(filtered).execute()

        return success({'invite_token': invite_data['token']}, "Invite sent")

    except Exception as e:
        logger.error(f"Invite error: {e}")
        return error("Failed to invite", 500)


@team_bp.route('/join', methods=['POST'])
@require_auth
def join_team():
    """Join team via code or invite."""
    data = request.get_json() or {}
    join_code = (data.get('join_code') or '').strip().upper()
    invite_token = (data.get('invite_token') or '').strip()

    if not join_code and not invite_token:
        return error("Missing join method", 400)

    db = get_db()
    if not db:
        return error("Database unavailable", 503)

    try:
        team = None
        role = 'developer'

        if join_code:
            res = db.table('teams').select('*').eq('join_code', join_code).eq('is_active', True).execute()
            if not res.data:
                return error("Invalid join code", 400)
            team = res.data[0]

        elif invite_token:
            res = db.table('team_invites').select('*, teams(*)').eq('token', invite_token).eq('is_used', False).execute()
            if not res.data:
                return error("Invalid invite", 400)

            invite = res.data[0]
            team = invite.get('teams')
            role = invite.get('role', 'developer')

            db.table('team_invites').update({'is_used': True}).eq('id', invite['id']).execute()

        if not team:
            return error("Team not found", 404)

        existing = get_membership(g.user['id'], team['id'])
        if existing:
            return error("Already member", 409)

        mem_data = {
            'team_id': team['id'],
            'user_id': g.user['id'],
            'role': role,
            'is_active': True
        }
        filtered = filter_fields('memberships', mem_data)
        db.table('memberships').insert(filtered).execute()

        audit_log(g.user['id'], 'member_joined', 'team', team['id'], team['id'])
        return success({'team': team, 'role': role}, "Joined")

    except Exception as e:
        logger.error(f"Join error: {e}")
        return error("Failed to join", 500)


@team_bp.route('/<team_id>/leave', methods=['POST'])
@require_auth
def leave_team(team_id):
    """Leave team."""
    membership = get_membership(g.user['id'], team_id)
    if not membership:
        return error("Not a team member", 403)

    db = get_db()
    if not db:
        return error("Database unavailable", 503)

    try:
        db.table('memberships').update({'is_active': False}).eq('team_id', team_id).eq('user_id', g.user['id']).execute()
        audit_log(g.user['id'], 'member_left', 'team', team_id, team_id)
        return success(message="Left team")
    except Exception as e:
        logger.error(f"Leave error: {e}")
        return error("Failed to leave team", 500)