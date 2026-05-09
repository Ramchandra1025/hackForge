"""HackForge — Analytics Routes"""
from flask import Blueprint, request, jsonify
from backend.utils.error_handlers import success, error, validate_required, get_pagination_params
from backend.utils.security import require_auth
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)
analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/dashboard', methods=['GET'])
@require_auth
def get_analytics_dashboard(current_user):
    """Get analytics dashboard data"""
    try:
        user_id = current_user.get('id')
        supabase = get_supabase()
        
        # Get user activity stats
        result = supabase.table('activities').select('*').eq('user_id', user_id).limit(100).execute()
        
        return success({
            'total_activities': len(result.data) if result.data else 0,
            'activities': result.data
        }, 'Analytics retrieved')
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return error('Failed to get analytics', 'ANALYTICS_ERROR'), 500


@analytics_bp.route('/team/<team_id>', methods=['GET'])
@require_auth
def get_team_analytics(current_user, team_id):
    """Get team analytics"""
    try:
        supabase = get_supabase()
        
        # Verify user is part of team
        membership = supabase.table('memberships').select('*').eq('team_id', team_id).eq('user_id', current_user.get('id')).execute()
        if not membership.data:
            return error('Not authorized', 'UNAUTHORIZED'), 403
        
        # Get team stats
        result = supabase.table('activities').select('*').eq('team_id', team_id).limit(500).execute()
        
        return success({
            'team_id': team_id,
            'total_activities': len(result.data) if result.data else 0,
            'activities': result.data
        }, 'Team analytics retrieved')
    except Exception as e:
        logger.error(f"Team analytics error: {e}")
        return error('Failed to get team analytics', 'ANALYTICS_ERROR'), 500


@analytics_bp.route('/project/<project_id>', methods=['GET'])
@require_auth
def get_project_analytics(current_user, project_id):
    """Get project analytics"""
    try:
        supabase = get_supabase()
        
        # Get project stats
        result = supabase.table('activities').select('*').eq('project_id', project_id).limit(500).execute()
        
        return success({
            'project_id': project_id,
            'total_activities': len(result.data) if result.data else 0,
            'activities': result.data
        }, 'Project analytics retrieved')
    except Exception as e:
        logger.error(f"Project analytics error: {e}")
        return error('Failed to get project analytics', 'ANALYTICS_ERROR'), 500
