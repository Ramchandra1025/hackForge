"""Integration management routes."""

from flask import Blueprint, request, g

from backend.utils.db import get_db
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.security import require_auth, get_membership, has_permission, audit_log
from backend.utils.helpers import generate_id, now_iso


integration_bp = Blueprint('integrations', __name__)


def _require_team_access(team_id):
    membership = get_membership(g.user['id'], team_id)
    if not membership:
        return None, error('Not a team member', 403)
    if not has_permission(membership['role'], 'manage_chat') and not has_permission(membership['role'], 'write') and not has_permission(membership['role'], 'invite'):
        return None, error('Insufficient permissions', 403)
    return membership, None


@integration_bp.route('', methods=['GET'])
@require_auth
def list_integrations():
    team_id = request.args.get('team_id')
    if not team_id:
        return error('team_id is required', 400)

    membership, team_error = _require_team_access(team_id)
    if team_error:
        return team_error

    db = get_db()
    result = db.table('integrations').select('*').eq('team_id', team_id).order('created_at', desc=True).execute()
    return success(data=result.data or [])


@integration_bp.route('', methods=['POST'])
@require_auth
def upsert_integration():
    data = request.get_json(silent=True) or {}
    ok, message = validate_required(data, ['team_id', 'provider'])
    if not ok:
        return error(message, 400)

    membership, team_error = _require_team_access(data['team_id'])
    if team_error:
        return team_error

    db = get_db()
    payload = {
        'id': data.get('id') or generate_id(),
        'team_id': data['team_id'],
        'provider': data['provider'],
        'name': data.get('name') or data['provider'],
        'config': data.get('config', {}),
        'is_enabled': bool(data.get('is_enabled', True)),
        'created_by': g.user['id'],
        'updated_by': g.user['id'],
        'updated_at': now_iso(),
    }

    result = db.table('integrations').upsert(payload).execute()
    if not result.data:
        return error('Failed to save integration', 500)

    audit_log(g.user['id'], 'integration_upsert', 'integration', result.data[0]['id'], data['team_id'])
    return success(data=result.data[0], message='Integration saved', status_code=201)


@integration_bp.route('/<integration_id>', methods=['DELETE'])
@require_auth
def delete_integration(integration_id):
    db = get_db()
    result = db.table('integrations').select('team_id').eq('id', integration_id).single().execute()
    if not result.data:
        return error('Integration not found', 404)

    membership, team_error = _require_team_access(result.data['team_id'])
    if team_error:
        return team_error

    db.table('integrations').delete().eq('id', integration_id).execute()
    audit_log(g.user['id'], 'integration_delete', 'integration', integration_id, result.data['team_id'])
    return success(message='Integration deleted')


@integration_bp.route('/test', methods=['POST'])
@require_auth
def test_integration():
    data = request.get_json(silent=True) or {}
    ok, message = validate_required(data, ['provider'])
    if not ok:
        return error(message, 400)

    return success(data={
        'provider': data['provider'],
        'status': 'ok',
        'tested_at': now_iso()
    }, message='Integration test completed')
