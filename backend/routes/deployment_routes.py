"""HackForge - Deployment Routes"""
import logging, os, requests
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth, audit_log
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id, now_iso
from backend.utils.constants import DEPLOY_STATUSES

deployment_bp = Blueprint('deployments', __name__)
logger = logging.getLogger(__name__)


@deployment_bp.route('/', methods=['GET'])
@require_auth
def list_deployments():
    project_id = request.args.get('project_id')
    team_id = request.args.get('team_id')
    db = get_db()
    q = db.table('deployments').select('*')
    if project_id:
        q = q.eq('project_id', project_id)
    if team_id:
        q = q.eq('team_id', team_id)
    result = q.order('created_at', desc=True).limit(50).execute()
    return success(data=result.data or [])


@deployment_bp.route('/', methods=['POST'])
@require_auth
def create_deployment():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['team_id', 'project_id', 'provider'])
    if not ok:
        return error(msg)

    if data['provider'] not in ['netlify', 'railway', 'github_pages', 'manual']:
        return error('Invalid provider')

    db = get_db()
    m = db.table('memberships').select('role').eq('user_id', g.user['id']).eq('team_id', data['team_id']).eq('is_active', True).single().execute()
    if not m.data or m.data['role'] not in ['owner', 'admin', 'developer']:
        return error('Insufficient permissions', 403)

    deployment = {
        'id': generate_id(),
        'team_id': data['team_id'],
        'project_id': data['project_id'],
        'provider': data['provider'],
        'environment': data.get('environment', 'production'),
        'branch': data.get('branch', 'main'),
        'status': 'pending',
        'deployed_by': g.user['id'],
        'config': data.get('config', {}),
        'logs': []
    }
    result = db.table('deployments').insert(deployment).execute()
    if not result.data:
        return error('Failed to create deployment', 500)

    dep = result.data[0]

    # Trigger deployment based on provider
    try:
        if data['provider'] == 'netlify':
            _trigger_netlify(dep, data.get('config', {}))
        elif data['provider'] == 'railway':
            _trigger_railway(dep, data.get('config', {}))
    except Exception as e:
        logger.error(f"Deploy trigger error: {e}")
        db.table('deployments').update({'status': 'failed', 'error_message': str(e)}).eq('id', dep['id']).execute()

    audit_log(g.user['id'], 'deployment_create', 'deployment', dep['id'], data['team_id'])
    return success(data=dep, status=201)


def _trigger_netlify(deployment: dict, config: dict):
    token = os.getenv('NETLIFY_TOKEN', config.get('token', ''))
    if not token:
        return
    site_id = config.get('site_id', '')
    if not site_id:
        return
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    resp = requests.post(f'https://api.netlify.com/api/v1/sites/{site_id}/deploys', headers=headers, json={}, timeout=15)
    db = get_db()
    status = 'building' if resp.status_code in [200, 201] else 'failed'
    update = {'status': status}
    if resp.status_code in [200, 201]:
        deploy_data = resp.json()
        update['deploy_url'] = deploy_data.get('deploy_ssl_url') or deploy_data.get('deploy_url', '')
        update['provider_deploy_id'] = deploy_data.get('id', '')
    db.table('deployments').update(update).eq('id', deployment['id']).execute()


def _trigger_railway(deployment: dict, config: dict):
    token = os.getenv('RAILWAY_TOKEN', config.get('token', ''))
    if not token:
        return
    # Railway GraphQL API
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    project_id = config.get('railway_project_id', '')
    if not project_id:
        return
    query = """
    mutation DeploymentCreate($input: DeploymentCreateInput!) {
        deploymentCreate(input: $input) { id status }
    }"""
    resp = requests.post('https://backboard.railway.app/graphql/v2', headers=headers,
                         json={'query': query, 'variables': {'input': {'projectId': project_id}}}, timeout=15)
    db = get_db()
    status = 'building' if resp.status_code == 200 else 'failed'
    db.table('deployments').update({'status': status}).eq('id', deployment['id']).execute()


@deployment_bp.route('/<deploy_id>', methods=['GET'])
@require_auth
def get_deployment(deploy_id):
    db = get_db()
    result = db.table('deployments').select('*').eq('id', deploy_id).single().execute()
    if not result.data:
        return error('Deployment not found', 404)
    return success(data=result.data)


@deployment_bp.route('/<deploy_id>/logs', methods=['GET'])
@require_auth
def get_logs(deploy_id):
    db = get_db()
    result = db.table('deployment_logs').select('*').eq('deployment_id', deploy_id).order('created_at').execute()
    return success(data=result.data or [])


@deployment_bp.route('/<deploy_id>/cancel', methods=['POST'])
@require_auth
def cancel_deployment(deploy_id):
    db = get_db()
    dep = db.table('deployments').select('status,team_id').eq('id', deploy_id).single().execute()
    if not dep.data:
        return error('Not found', 404)
    if dep.data['status'] not in ['pending', 'building']:
        return error('Deployment cannot be cancelled')
    db.table('deployments').update({'status': 'cancelled'}).eq('id', deploy_id).execute()
    return success(message='Deployment cancelled')