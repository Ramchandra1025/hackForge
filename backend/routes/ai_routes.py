"""HackForge - AI Routes"""
import logging
from flask import Blueprint, request, g, Response, stream_with_context
from backend.utils.db import get_db
from backend.utils.security import require_auth
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.helpers import generate_id, now_iso
from backend.utils.redis_client import cache_get, cache_set

ai_bp = Blueprint('ai', __name__)
logger = logging.getLogger(__name__)

def get_gemini():
    """Get configured Gemini model."""
    import google.generativeai as genai
    import os
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')


def get_ai_memory(user_id: str, team_id: str = None, limit: int = 20) -> list:
    db = get_db()
    query = db.table('ai_memory').select('role,content').eq('user_id', user_id)
    if team_id:
        query = query.eq('team_id', team_id)
    result = query.order('created_at', desc=True).limit(limit).execute()
    return list(reversed(result.data or []))


def save_ai_memory(user_id: str, role: str, content: str, team_id: str = None, context_type: str = 'chat'):
    db = get_db()
    try:
        db.table('ai_memory').insert({
            'id': generate_id(),
            'user_id': user_id,
            'team_id': team_id,
            'role': role,
            'content': content[:8000],
            'context_type': context_type
        }).execute()
    except Exception as e:
        logger.error(f"AI memory save error: {e}")


@ai_bp.route('/chat', methods=['POST'])
@require_auth
def ai_chat():
    data = request.get_json(silent=True) or {}
    if not data.get('message'):
        return error('message required')

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    team_id = data.get('team_id')
    context_type = data.get('context_type', 'chat')
    
    # Build conversation history
    memory = get_ai_memory(g.user['id'], team_id)
    system_prompt = (
        "You are HackForge AI, an intelligent assistant for a collaborative developer workspace. "
        "Help with coding, project planning, code review, debugging, documentation, and team collaboration. "
        "Be concise, technical, and practical. Format code with markdown code blocks."
    )

    history = []
    for mem in memory:
        history.append({'role': mem['role'], 'parts': [mem['content']]})
    
    history.append({'role': 'user', 'parts': [data['message']]})

    try:
        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(data['message'])
        reply = response.text

        # Save to memory
        save_ai_memory(g.user['id'], 'user', data['message'], team_id, context_type)
        save_ai_memory(g.user['id'], 'model', reply, team_id, context_type)

        # Log API usage
        db = get_db()
        try:
            db.table('api_usage').insert({
                'id': generate_id(),
                'user_id': g.user['id'],
                'team_id': team_id,
                'service': 'gemini',
                'endpoint': 'chat',
                'tokens_in': len(data['message'].split()),
                'tokens_out': len(reply.split())
            }).execute()
        except Exception:
            pass

        return success(data={'reply': reply, 'context_type': context_type})
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return error('AI request failed', 500)


@ai_bp.route('/review', methods=['POST'])
@require_auth
def review_code():
    data = request.get_json(silent=True) or {}
    if not data.get('code'):
        return error('code required')

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    language = data.get('language', 'unknown')
    prompt = f"""You are an expert code reviewer. Review the following {language} code and provide:

1. **Summary**: Brief overview of what the code does
2. **Issues**: List any bugs, security vulnerabilities, or performance problems
3. **Improvements**: Suggest specific improvements with examples
4. **Quality Score**: Rate the code quality 1-10

Code to review:
```{language}
{data['code'][:6000]}
```

Be specific, actionable, and constructive."""

    try:
        response = model.generate_content(prompt)
        return success(data={'review': response.text, 'language': language})
    except Exception as e:
        logger.error(f"Code review error: {e}")
        return error('Code review failed', 500)


@ai_bp.route('/explain', methods=['POST'])
@require_auth
def explain_code():
    data = request.get_json(silent=True) or {}
    if not data.get('code'):
        return error('code required')

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    language = data.get('language', 'code')
    prompt = f"""Explain this {language} code clearly and concisely. 
Cover what it does, how it works, and any important patterns or techniques used.

```{language}
{data['code'][:4000]}
```"""

    try:
        response = model.generate_content(prompt)
        return success(data={'explanation': response.text})
    except Exception as e:
        return error('Explain failed', 500)


@ai_bp.route('/generate-readme', methods=['POST'])
@require_auth
def generate_readme():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['project_name'])
    if not ok:
        return error(msg)

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    prompt = f"""Generate a professional, comprehensive README.md for a project called "{data['project_name']}".

Description: {data.get('description', 'No description provided')}
Tech Stack: {', '.join(data.get('tech_stack', []))}
Features: {', '.join(data.get('features', []))}

Include: badges, overview, features, installation, usage, API docs (if applicable), contributing, license.
Use proper markdown formatting."""

    try:
        response = model.generate_content(prompt)
        return success(data={'readme': response.text})
    except Exception as e:
        return error('README generation failed', 500)


@ai_bp.route('/plan-sprint', methods=['POST'])
@require_auth
def plan_sprint():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_required(data, ['project_id'])
    if not ok:
        return error(msg)

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    db = get_db()
    # Get backlog tasks
    tasks = db.table('tasks').select('title,description,priority,story_points').eq('project_id', data['project_id']).eq('status', 'backlog').limit(30).execute()

    task_list = '\n'.join([f"- {t['title']} (Priority: {t.get('priority','medium')}, Points: {t.get('story_points','?')})" for t in (tasks.data or [])])
    
    prompt = f"""You are a sprint planning AI. Based on these backlog tasks, create an optimal 2-week sprint plan.

Backlog items:
{task_list or 'No tasks available'}

Team size: {data.get('team_size', 3)}
Velocity: {data.get('velocity', 20)} story points per sprint
Sprint goal: {data.get('goal', 'Not specified')}

Provide:
1. Recommended sprint tasks (with reasoning)
2. Sprint goal statement
3. Risk assessment
4. Team capacity breakdown
Output as structured JSON."""

    try:
        response = model.generate_content(prompt)
        return success(data={'plan': response.text})
    except Exception as e:
        return error('Sprint planning failed', 500)


@ai_bp.route('/find-bugs', methods=['POST'])
@require_auth
def find_bugs():
    data = request.get_json(silent=True) or {}
    if not data.get('code'):
        return error('code required')

    model = get_gemini()
    if not model:
        return error('AI service not configured', 503)

    language = data.get('language', 'code')
    prompt = f"""Analyze this {language} code for bugs and issues. For each issue found, provide:
- Line number (if identifiable)
- Severity (critical/high/medium/low)
- Description of the bug
- Suggested fix

```{language}
{data['code'][:5000]}
```

Format as JSON array: [{{"line": N, "severity": "...", "issue": "...", "fix": "..."}}]"""

    try:
        response = model.generate_content(prompt)
        return success(data={'bugs': response.text, 'language': language})
    except Exception as e:
        return error('Bug finder failed', 500)


@ai_bp.route('/memory', methods=['GET'])
@require_auth
def get_memory():
    team_id = request.args.get('team_id')
    memory = get_ai_memory(g.user['id'], team_id, limit=50)
    return success(data=memory)


@ai_bp.route('/memory', methods=['DELETE'])
@require_auth
def clear_memory():
    db = get_db()
    team_id = request.args.get('team_id')
    query = db.table('ai_memory').delete().eq('user_id', g.user['id'])
    if team_id:
        query = query.eq('team_id', team_id)
    query.execute()
    return success(message='Memory cleared')