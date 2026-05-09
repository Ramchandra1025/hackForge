"""
HackForge - Task Routes (Kanban, Comments, Sprints)
"""

import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth, get_membership, has_permission, audit_log
from backend.utils.error_handlers import success, error, validate_required, get_pagination_params
from backend.utils.redis_client import cache_delete

task_bp = Blueprint('tasks', __name__)
logger = logging.getLogger(__name__)


def verify_project_access(project_id, user_id):
    """Verify user has access to project's team"""
    db = get_db()
    try:
        result = db.table('projects').select('team_id').eq('id', project_id).single().execute()
        if not result.data:
            return None, None
        team_id = result.data['team_id']
        membership = get_membership(user_id, team_id)
        return team_id, membership
    except:
        return None, None


# ── Tasks ────────────────────────────────────────────────────

@task_bp.route('', methods=['GET'])
@require_auth
def get_tasks():
    """Get tasks for a project"""
    project_id = request.args.get('project_id')
    team_id = request.args.get('team_id')
    sprint_id = request.args.get('sprint_id')
    status = request.args.get('status')
    assignee_id = request.args.get('assignee_id')
    
    if not project_id and not team_id:
        return error("project_id or team_id required", 400)
    
    db = get_db()
    
    try:
        if project_id:
            t_id, membership = verify_project_access(project_id, g.user['id'])
            if not membership:
                return error("Access denied", 403)
        else:
            membership = get_membership(g.user['id'], team_id)
            if not membership:
                return error("Access denied", 403)
        
        query = db.table('tasks').select(
            '*, assignee:users!tasks_assignee_id_fkey(id, username, display_name, avatar_url), '
            'reporter:users!tasks_reporter_id_fkey(id, username, display_name, avatar_url)'
        )
        
        if project_id:
            query = query.eq('project_id', project_id)
        elif team_id:
            query = query.eq('team_id', team_id)
        
        if sprint_id:
            query = query.eq('sprint_id', sprint_id)
        if status:
            query = query.eq('status', status)
        if assignee_id:
            query = query.eq('assignee_id', assignee_id)
        
        result = query.order('position').order('created_at').execute()
        
        return success({'tasks': result.data or []})
        
    except Exception as e:
        logger.error(f"Get tasks error: {e}")
        return error("Failed to get tasks", 500)


@task_bp.route('', methods=['POST'])
@require_auth
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    valid, msg = validate_required(data, ['title', 'project_id'])
    if not valid:
        return error(msg, 400)
    
    project_id = data['project_id']
    team_id, membership = verify_project_access(project_id, g.user['id'])
    
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        # Get max position for status column
        status = data.get('status', 'backlog')
        pos_result = db.table('tasks').select('position').eq('project_id', project_id).eq('status', status).order('position', desc=True).limit(1).execute()
        position = (pos_result.data[0]['position'] + 1) if pos_result.data else 0
        
        task_result = db.table('tasks').insert({
            'project_id': project_id,
            'team_id': team_id,
            'sprint_id': data.get('sprint_id'),
            'title': data['title'],
            'description': data.get('description', ''),
            'status': status,
            'priority': data.get('priority', 'medium'),
            'type': data.get('type', 'feature'),
            'assignee_id': data.get('assignee_id'),
            'reporter_id': g.user['id'],
            'labels': data.get('labels', []),
            'story_points': data.get('story_points'),
            'due_date': data.get('due_date'),
            'position': position,
            'parent_task_id': data.get('parent_task_id')
        }).execute()
        
        task = task_result.data[0] if task_result.data else {}
        
        # Index for search
        db.table('search_index').insert({
            'team_id': team_id,
            'entity_type': 'task',
            'entity_id': task['id'],
            'title': task['title'],
            'content': task.get('description', ''),
            'tags': task.get('labels', [])
        }).execute()
        
        # Create activity
        db.table('activities').insert({
            'team_id': team_id,
            'project_id': project_id,
            'user_id': g.user['id'],
            'type': 'task_created',
            'entity_type': 'task',
            'entity_id': task['id'],
            'description': f"Created task: {task['title']}"
        }).execute()
        
        # Notify assignee if different from creator
        if task.get('assignee_id') and task['assignee_id'] != g.user['id']:
            db.table('notifications').insert({
                'user_id': task['assignee_id'],
                'team_id': team_id,
                'type': 'task_assigned',
                'title': 'Task Assigned',
                'body': f"You've been assigned: {task['title']}",
                'link': f"/task/{task['id']}",
                'metadata': {'task_id': task['id'], 'project_id': project_id}
            }).execute()
        
        return success({'task': task}, "Task created", 201)
        
    except Exception as e:
        logger.error(f"Create task error: {e}")
        return error("Failed to create task", 500)


@task_bp.route('/<task_id>', methods=['GET'])
@require_auth
def get_task(task_id):
    """Get task details"""
    db = get_db()
    
    try:
        result = db.table('tasks').select(
            '*, assignee:users!tasks_assignee_id_fkey(id, username, display_name, avatar_url, email), '
            'reporter:users!tasks_reporter_id_fkey(id, username, display_name, avatar_url)'
        ).eq('id', task_id).single().execute()
        
        if not result.data:
            return error("Task not found", 404)
        
        task = result.data
        
        # Verify access
        membership = get_membership(g.user['id'], task['team_id'])
        if not membership:
            return error("Access denied", 403)
        
        # Get comments
        comments = db.table('task_comments').select(
            '*, user:users(id, username, display_name, avatar_url)'
        ).eq('task_id', task_id).order('created_at').execute()
        
        task['comments'] = comments.data or []
        
        # Get history
        history = db.table('task_history').select(
            '*, user:users(id, username, display_name)'
        ).eq('task_id', task_id).order('created_at', desc=True).limit(20).execute()
        
        task['history'] = history.data or []
        
        return success({'task': task})
        
    except Exception as e:
        logger.error(f"Get task error: {e}")
        return error("Failed to get task", 500)


@task_bp.route('/<task_id>', methods=['PATCH'])
@require_auth
def update_task(task_id):
    """Update task"""
    db = get_db()
    
    try:
        task_result = db.table('tasks').select('*').eq('id', task_id).single().execute()
        if not task_result.data:
            return error("Task not found", 404)
        
        task = task_result.data
        membership = get_membership(g.user['id'], task['team_id'])
        if not membership:
            return error("Access denied", 403)
        
        data = request.get_json()
        allowed = ['title', 'description', 'status', 'priority', 'type', 'assignee_id',
                   'labels', 'story_points', 'due_date', 'position', 'sprint_id', 'metadata']
        update_data = {k: v for k, v in data.items() if k in allowed}
        
        if not update_data:
            return error("No valid fields to update", 400)
        
        # Handle status change - update search index
        if 'status' in update_data and update_data['status'] != task['status']:
            db.table('activities').insert({
                'team_id': task['team_id'],
                'project_id': task['project_id'],
                'user_id': g.user['id'],
                'type': 'task_status_changed',
                'entity_type': 'task',
                'entity_id': task_id,
                'description': f"Moved task '{task['title']}' from {task['status']} to {update_data['status']}"
            }).execute()
        
        # Handle new assignee notification
        if 'assignee_id' in update_data and update_data['assignee_id'] != task.get('assignee_id'):
            if update_data['assignee_id']:
                db.table('notifications').insert({
                    'user_id': update_data['assignee_id'],
                    'team_id': task['team_id'],
                    'type': 'task_assigned',
                    'title': 'Task Assigned',
                    'body': f"You've been assigned: {task['title']}",
                    'link': f"/task/{task_id}",
                    'metadata': {'task_id': task_id}
                }).execute()
        
        result = db.table('tasks').update(update_data).eq('id', task_id).execute()
        
        return success({'task': result.data[0] if result.data else {}}, "Task updated")
        
    except Exception as e:
        logger.error(f"Update task error: {e}")
        return error("Failed to update task", 500)


@task_bp.route('/<task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    """Delete task"""
    db = get_db()
    
    try:
        task_result = db.table('tasks').select('*').eq('id', task_id).single().execute()
        if not task_result.data:
            return error("Task not found", 404)
        
        task = task_result.data
        membership = get_membership(g.user['id'], task['team_id'])
        if not membership or not has_permission(membership['role'], 'delete'):
            return error("Permission denied", 403)
        
        db.table('tasks').delete().eq('id', task_id).execute()
        db.table('search_index').delete().eq('entity_id', task_id).execute()
        
        return success(None, "Task deleted")
        
    except Exception as e:
        logger.error(f"Delete task error: {e}")
        return error("Failed to delete task", 500)


@task_bp.route('/bulk-update', methods=['POST'])
@require_auth
def bulk_update_tasks():
    """Bulk update task positions (for drag-drop reordering)"""
    data = request.get_json()
    updates = data.get('updates', [])
    
    if not updates:
        return error("No updates provided", 400)
    
    db = get_db()
    
    try:
        for update in updates:
            task_id = update.get('id')
            if not task_id:
                continue
            
            fields = {}
            if 'status' in update:
                fields['status'] = update['status']
            if 'position' in update:
                fields['position'] = update['position']
            if 'sprint_id' in update:
                fields['sprint_id'] = update['sprint_id']
            
            if fields:
                db.table('tasks').update(fields).eq('id', task_id).execute()
        
        return success(None, "Tasks updated")
        
    except Exception as e:
        logger.error(f"Bulk update error: {e}")
        return error("Failed to update tasks", 500)


# ── Task Comments ────────────────────────────────────────────

@task_bp.route('/<task_id>/comments', methods=['GET'])
@require_auth
def get_comments(task_id):
    """Get task comments"""
    db = get_db()
    
    try:
        task_result = db.table('tasks').select('team_id').eq('id', task_id).single().execute()
        if not task_result.data:
            return error("Task not found", 404)
        
        membership = get_membership(g.user['id'], task_result.data['team_id'])
        if not membership:
            return error("Access denied", 403)
        
        result = db.table('task_comments').select(
            '*, user:users(id, username, display_name, avatar_url)'
        ).eq('task_id', task_id).order('created_at').execute()
        
        return success({'comments': result.data or []})
        
    except Exception as e:
        logger.error(f"Get comments error: {e}")
        return error("Failed to get comments", 500)


@task_bp.route('/<task_id>/comments', methods=['POST'])
@require_auth
def add_comment(task_id):
    """Add task comment"""
    data = request.get_json()
    
    if not data.get('content', '').strip():
        return error("Comment content required", 400)
    
    db = get_db()
    
    try:
        task_result = db.table('tasks').select('*').eq('id', task_id).single().execute()
        if not task_result.data:
            return error("Task not found", 404)
        
        task = task_result.data
        membership = get_membership(g.user['id'], task['team_id'])
        if not membership:
            return error("Access denied", 403)
        
        comment_result = db.table('task_comments').insert({
            'task_id': task_id,
            'user_id': g.user['id'],
            'content': data['content'].strip(),
            'parent_id': data.get('parent_id'),
            'attachments': data.get('attachments', [])
        }).execute()
        
        comment = comment_result.data[0] if comment_result.data else {}
        
        # Notify task reporter/assignee
        notify_users = set()
        if task.get('reporter_id') and task['reporter_id'] != g.user['id']:
            notify_users.add(task['reporter_id'])
        if task.get('assignee_id') and task['assignee_id'] != g.user['id']:
            notify_users.add(task['assignee_id'])
        
        for uid in notify_users:
            db.table('notifications').insert({
                'user_id': uid,
                'team_id': task['team_id'],
                'type': 'task_comment',
                'title': 'New Comment',
                'body': f"{g.user.get('display_name', g.user['username'])} commented on: {task['title']}",
                'link': f"/task/{task_id}",
                'metadata': {'task_id': task_id, 'comment_id': comment.get('id')}
            }).execute()
        
        return success({'comment': comment}, "Comment added", 201)
        
    except Exception as e:
        logger.error(f"Add comment error: {e}")
        return error("Failed to add comment", 500)


@task_bp.route('/comments/<comment_id>', methods=['PATCH'])
@require_auth
def update_comment(comment_id):
    """Update comment"""
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return error("Content required", 400)
    
    db = get_db()
    
    try:
        result = db.table('task_comments').select('*').eq('id', comment_id).single().execute()
        if not result.data:
            return error("Comment not found", 404)
        
        comment = result.data
        if comment['user_id'] != g.user['id']:
            return error("Can only edit your own comments", 403)
        
        updated = db.table('task_comments').update({
            'content': content,
            'is_edited': True
        }).eq('id', comment_id).execute()
        
        return success({'comment': updated.data[0] if updated.data else {}})
        
    except Exception as e:
        return error("Failed to update comment", 500)


@task_bp.route('/comments/<comment_id>', methods=['DELETE'])
@require_auth
def delete_comment(comment_id):
    """Delete comment"""
    db = get_db()
    
    try:
        result = db.table('task_comments').select('*').eq('id', comment_id).single().execute()
        if not result.data:
            return error("Comment not found", 404)
        
        comment = result.data
        if comment['user_id'] != g.user['id']:
            # Allow admins/owners to delete
            task_result = db.table('tasks').select('team_id').eq('id', comment['task_id']).single().execute()
            if task_result.data:
                membership = get_membership(g.user['id'], task_result.data['team_id'])
                if not membership or not has_permission(membership['role'], 'delete'):
                    return error("Permission denied", 403)
        
        db.table('task_comments').delete().eq('id', comment_id).execute()
        return success(None, "Comment deleted")
        
    except Exception as e:
        return error("Failed to delete comment", 500)


# ── Sprints ──────────────────────────────────────────────────

@task_bp.route('/sprints', methods=['GET'])
@require_auth
def get_sprints():
    """Get sprints for a project"""
    project_id = request.args.get('project_id')
    if not project_id:
        return error("project_id required", 400)
    
    team_id, membership = verify_project_access(project_id, g.user['id'])
    if not membership:
        return error("Access denied", 403)
    
    db = get_db()
    
    try:
        result = db.table('sprints').select('*').eq('project_id', project_id).order('created_at', desc=True).execute()
        
        sprints = []
        for sprint in (result.data or []):
            # Get task count
            tasks = db.table('tasks').select('id, status').eq('sprint_id', sprint['id']).execute()
            sprint['task_count'] = len(tasks.data) if tasks.data else 0
            sprint['completed_count'] = sum(1 for t in (tasks.data or []) if t['status'] == 'done')
            sprints.append(sprint)
        
        return success({'sprints': sprints})
        
    except Exception as e:
        logger.error(f"Get sprints error: {e}")
        return error("Failed to get sprints", 500)


@task_bp.route('/sprints', methods=['POST'])
@require_auth
def create_sprint():
    """Create a sprint"""
    data = request.get_json()
    
    valid, msg = validate_required(data, ['name', 'project_id'])
    if not valid:
        return error(msg, 400)
    
    project_id = data['project_id']
    team_id, membership = verify_project_access(project_id, g.user['id'])
    if not membership or not has_permission(membership['role'], 'manage_tasks'):
        return error("Permission denied", 403)
    
    db = get_db()
    
    try:
        result = db.table('sprints').insert({
            'project_id': project_id,
            'team_id': team_id,
            'name': data['name'],
            'goal': data.get('goal', ''),
            'status': 'planned',
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'created_by': g.user['id']
        }).execute()
        
        return success({'sprint': result.data[0] if result.data else {}}, "Sprint created", 201)
        
    except Exception as e:
        logger.error(f"Create sprint error: {e}")
        return error("Failed to create sprint", 500)


@task_bp.route('/sprints/<sprint_id>', methods=['PATCH'])
@require_auth
def update_sprint(sprint_id):
    """Update sprint"""
    db = get_db()
    
    try:
        sprint_result = db.table('sprints').select('*').eq('id', sprint_id).single().execute()
        if not sprint_result.data:
            return error("Sprint not found", 404)
        
        sprint = sprint_result.data
        membership = get_membership(g.user['id'], sprint['team_id'])
        if not membership or not has_permission(membership['role'], 'manage_tasks'):
            return error("Permission denied", 403)
        
        data = request.get_json()
        allowed = ['name', 'goal', 'status', 'start_date', 'end_date', 'velocity']
        update_data = {k: v for k, v in data.items() if k in allowed}
        
        result = db.table('sprints').update(update_data).eq('id', sprint_id).execute()
        return success({'sprint': result.data[0] if result.data else {}})
        
    except Exception as e:
        return error("Failed to update sprint", 500)