"""HackForge - Search Routes"""
import logging
from flask import Blueprint, request, g
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error

search_bp = Blueprint('search', __name__)
logger = logging.getLogger(__name__)


@search_bp.route('/', methods=['GET'])
@require_auth
def global_search():
    q = request.args.get('q', '').strip()
    team_id = request.args.get('team_id')
    scope = request.args.get('scope', 'all')  # all, tasks, files, messages, wiki

    if len(q) < 2:
        return error('Query must be at least 2 characters')

    db = get_db()
    results = {}

    # Verify team membership if team_id provided
    if team_id:
        m = db.table('memberships').select('id').eq('user_id', g.user['id']).eq('team_id', team_id).eq('is_active', True).execute()
        if not m.data:
            return error('Access denied', 403)

    try:
        if scope in ['all', 'tasks']:
            tq = db.table('tasks').select('id,title,status,priority,project_id').ilike('title', f'%{q}%').limit(10)
            if team_id:
                tq = tq.eq('team_id', team_id)
            t_res = tq.execute()
            results['tasks'] = t_res.data or []

        if scope in ['all', 'files']:
            fq = db.table('files').select('id,name,file_type,size_bytes,created_at').ilike('name', f'%{q}%').limit(10)
            if team_id:
                fq = fq.eq('team_id', team_id)
            f_res = fq.execute()
            results['files'] = f_res.data or []

        if scope in ['all', 'wiki']:
            wq = db.table('wiki_pages').select('id,title,slug,team_id').ilike('title', f'%{q}%').limit(10)
            if team_id:
                wq = wq.eq('team_id', team_id)
            w_res = wq.execute()
            results['wiki'] = w_res.data or []

        if scope in ['all', 'messages']:
            mq = db.table('chat_messages').select('id,content,room_id,created_at').ilike('content', f'%{q}%').eq('is_deleted', False).limit(10)
            m_res = mq.execute()
            results['messages'] = m_res.data or []

    except Exception as e:
        logger.error(f"Search error: {e}")
        return error('Search failed', 500)

    total = sum(len(v) for v in results.values())
    return success(data={'results': results, 'total': total, 'query': q})