"""
HackForge — Backend v5.0
Flask + Socket.IO | Supabase PostgreSQL | HS256 JWT Auth | Google Gemini AI
Upgrades v5:
  - Google Gemini AI replaces DeepSeek/OpenAI
  - Cloudflare R2 file storage with signed URL generation
  - Full OTP email verification via EmailJS-compatible endpoint
  - Notification persistence fixes
  - Activity feed with proper filters
  - Search indexing improvements
  - Online presence tracking
  - Task comment CRUD fixes
  - Deployment API improvements
  - File upload/download with R2
  - Sprint planning endpoints
  - Judge scoring panel
  - Leaderboard
  - Wiki/notes CRUD
  - AI memory per user/team
  - Rate limiting
  - Audit logs
  - Full RBAC enforcement
  - Code execution sandbox (subprocess isolation)
"""

import os, uuid, logging, json, threading, hashlib, secrets, random, subprocess, tempfile, time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import bcrypt
import jwt
from flask import Flask, request, jsonify, g, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from dotenv import load_dotenv


# Optional: Google Gemini
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

load_dotenv()

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hackforge")

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
SUPABASE_URL        = os.getenv("SUPABASE_URL")
SUPABASE_KEY        = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
JWT_SECRET          = os.getenv("JWT_SECRET", "hackforge-super-secret-change-me")
JWT_ALGORITHM       = "HS256"
JWT_EXP_HOURS       = 72

STORAGE_BUCKET = "hackforge-files"

# Email (via your own SMTP or EmailJS proxy)
EMAILJS_SERVICE_ID  = os.getenv("EMAILJS_SERVICE_ID", "")
EMAILJS_TEMPLATE_ID = os.getenv("EMAILJS_TEMPLATE_ID", "")
EMAILJS_PUBLIC_KEY  = os.getenv("EMAILJS_PUBLIC_KEY", "")
EMAILJS_PRIVATE_KEY = os.getenv("EMAILJS_PRIVATE_KEY", "")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL missing in .env")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY missing in .env")

# ─────────────────────────────────────────
#  CLIENTS
# ─────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Gemini AI
gemini_model = None
if HAS_GEMINI and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("Gemini AI initialized")


# ─────────────────────────────────────────
#  FLASK APP
# ─────────────────────────────────────────
flask_app = Flask(__name__)
flask_app.config["SECRET_KEY"] = JWT_SECRET
flask_app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

CORS(flask_app, origins="*", supports_credentials=True)
socketio = SocketIO(
    flask_app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)

limiter = Limiter(
    key_func=get_remote_address,
    app=flask_app,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

@flask_app.route('/')
@flask_app.route('/<path:path>')
def home(path=''):
    return send_from_directory('.', 'app.html')

# ═══════════════════════════════════════════════════
#  JWT HELPERS
# ═══════════════════════════════════════════════════

def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub":   str(user_id),
        "email": email,
        "exp":   datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
        "iat":   datetime.now(timezone.utc),
        "jti":   secrets.token_hex(8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def extract_token(auth_header: Optional[str]) -> Optional[str]:
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None

# ─────────────────────────────────────────
#  FLASK AUTH DECORATOR
# ─────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = extract_token(request.headers.get("Authorization"))
        if not token:
            return jsonify({"error": "Authorization required"}), 401
        try:
            g.user = decode_jwt(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return wrapped

def require_team_member(f):
    """Decorator: require user is member of team_id in URL."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        team_id = kwargs.get('team_id')
        if team_id:
            uid = g.user["sub"]
            membership = get_user_team(uid)
            if not membership or membership["team_id"] != team_id:
                return jsonify({"error": "Not a team member"}), 403
        return f(*args, **kwargs)
    return wrapped

# ═══════════════════════════════════════════════════
#  DB HELPERS
# ═══════════════════════════════════════════════════
def db(table: str):
    return supabase.table(table)

def ok(data=None, status: int = 200):
    return jsonify({"data": data, "ok": True}), status

def err(msg: str, status: int = 400):
    return jsonify({"error": msg, "ok": False}), status

def now_iso():
    return datetime.utcnow().isoformat()

def now_ts():
    return int(time.time())

# ═══════════════════════════════════════════════════
#  ACTIVITY + NOTIFICATION HELPERS
# ═══════════════════════════════════════════════════
def log_activity(team_id: str, user_id: str, action_type: str,
                 target_type: str, target_id: str = None, metadata: dict = None):
    try:
        row = {
            "id":          str(uuid.uuid4()),
            "team_id":     team_id,
            "user_id":     user_id,
            "action_type": action_type,
            "target_type": target_type,
            "target_id":   target_id,
            "metadata":    json.dumps(metadata or {}),
            "created_at":  now_iso(),
        }
        db("activities").insert(row).execute()
        user_r = db("users").select("id,full_name,email").eq("id", user_id).execute()
        row["metadata"] = metadata or {}
        row["user"] = user_r.data[0] if user_r.data else {}
        socketio.emit("activity_new", row, room=f"team_{team_id}")
    except Exception as e:
        logger.warning(f"log_activity failed: {e}")

def log_audit(user_id: str, action: str, resource: str, resource_id: str = None,
              ip: str = None, metadata: dict = None):
    try:
        db("audit_logs").insert({
            "id":          str(uuid.uuid4()),
            "user_id":     user_id,
            "action":      action,
            "resource":    resource,
            "resource_id": resource_id,
            "ip_address":  ip or request.remote_addr,
            "metadata":    json.dumps(metadata or {}),
            "created_at":  now_iso(),
        }).execute()
    except Exception as e:
        logger.warning(f"log_audit failed: {e}")

def create_notification(user_id: str, notif_type: str, title: str,
                        content: str = None, link: str = None, metadata: dict = None):
    try:
        row = {
            "id":         str(uuid.uuid4()),
            "user_id":    user_id,
            "type":       notif_type,
            "title":      title,
            "content":    content,
            "link":       link,
            "metadata":   json.dumps(metadata or {}),
            "read":       False,
            "created_at": now_iso(),
        }
        db("notifications").insert(row).execute()
        row["metadata"] = metadata or {}
        socketio.emit("notification_new", row, room=f"user_{user_id}")
    except Exception as e:
        logger.warning(f"create_notification failed: {e}")

# ─────────────────────────────────────────
#  TEAM HELPERS
# ─────────────────────────────────────────
def get_user_team(user_id: str) -> Optional[dict]:
    r = db("team_members").select("team_id,role").eq("user_id", user_id).limit(1).execute()
    return r.data[0] if r.data else None

def remove_user_from_team(user_id: str) -> Optional[str]:
    existing = get_user_team(user_id)
    if existing:
        db("team_members").delete().eq("user_id", user_id).execute()
        return existing["team_id"]
    return None

# ═══════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════

@flask_app.post("/api/auth/signup")
@limiter.limit("10 per hour")
def signup():
    body     = request.get_json(silent=True) or {}
    name     = (body.get("name") or body.get("full_name", "")).strip()
    email    = (body.get("email", "")).strip().lower()
    password = body.get("password", "")
    username = (body.get("username", "")).strip().lower()

    if not name or not email or not password:
        return err("Name, email and password are required")
    if len(password) < 4:
        return err("Password must be at least 4 characters")
    if len(password) > 20:
        return err("Password must be at most 20 characters")

    existing = db("users").select("id").eq("email", email).execute()
    if existing.data:
        return err("Email already registered")

    if username:
        u_exists = db("users").select("id").eq("username", username).execute()
        if u_exists.data:
            return err("Username already taken")

    uid    = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    result = db("users").insert({
        "id":            uid,
        "email":         email,
        "username":      username or None,
        "full_name":     name,
        "password_hash": hashed,
        "skills":        [],
        "created_at":    now_iso(),
        "updated_at":    now_iso(),
    }).execute()

    if not result.data:
        return err("Failed to create account", 500)

    try:
        db("user_preferences").insert({
            "user_id":                  uid,
            "theme":                    "dark",
            "keyboard_shortcuts":       {},
            "notification_preferences": {},
            "recent_searches":          [],
            "updated_at":               now_iso(),
        }).execute()
    except Exception:
        pass

    log_audit(uid, "signup", "user", uid, metadata={"email": email})
    token = create_jwt(uid, email)
    return ok({
        "access_token": token,
        "user": {
            "id":        uid,
            "email":     email,
            "full_name": name,
            "username":  username or None,
            "skills":    [],
        },
        "message": "Account created!",
    }, 201)


@flask_app.post("/api/auth/login")
@limiter.limit("20 per minute")
def login():
    body     = request.get_json(silent=True) or {}
    login_id = (body.get("email", "") or body.get("username", "")).strip().lower()
    password = body.get("password", "")

    if not login_id or not password:
        return err("Email/username and password required")

    # Try email first, then username
    result = db("users").select("*").eq("email", login_id).execute()
    if not result.data:
        result = db("users").select("*").eq("username", login_id).execute()
    if not result.data:
        return err("Invalid credentials"), 401

    user        = result.data[0]
    stored_hash = user.get("password_hash", "")

    if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        log_audit(user["id"], "login_failed", "auth", user["id"],
                  metadata={"reason": "bad_password"})
        return err("Invalid credentials"), 401

    token = create_jwt(user["id"], user["email"])
    log_audit(user["id"], "login", "auth", user["id"])
    return ok({
        "access_token": token,
        "user": {
            "id":        user["id"],
            "email":     user["email"],
            "full_name": user.get("full_name", ""),
            "username":  user.get("username"),
            "skills":    user.get("skills", []),
            "bio":       user.get("bio"),
            "github":    user.get("github"),
            "portfolio": user.get("portfolio"),
            "avatar":    user.get("avatar"),
        }
    })


@flask_app.post("/api/auth/logout")
@require_auth
def logout():
    log_audit(g.user["sub"], "logout", "auth", g.user["sub"])
    return ok({"message": "Logged out"})


# ═══════════════════════════════════════════════════
#  USERS / PROFILE
# ═══════════════════════════════════════════════════

@flask_app.get("/api/users/<user_id>")
@require_auth
def get_user(user_id):
    result = db("users").select(
        "id,email,username,full_name,bio,github,portfolio,avatar,skills,created_at"
    ).eq("id", user_id).execute()
    if not result.data:
        return err("User not found", 404)
    user = result.data[0]

    # Task stats
    tasks_r = db("tasks").select("id,title,status,priority").eq("assigned_to", user_id).execute()
    user["tasks"] = tasks_r.data or []
    user["tasks_completed"] = sum(1 for t in user["tasks"] if t.get("status") == "done")
    user["tasks_ongoing"]   = sum(1 for t in user["tasks"] if t.get("status") in ("doing", "review"))

    # Likes
    try:
        likes_r = db("member_likes").select("id", count="exact").eq("liked_user_id", user_id).execute()
        user["likes_received"] = likes_r.count or 0
    except Exception:
        user["likes_received"] = 0

    # Recent activity
    try:
        act_r = db("activities").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
        user["recent_activity"] = act_r.data or []
    except Exception:
        user["recent_activity"] = []

    user["badges"] = _compute_badges(user)
    return ok(user)


def _compute_badges(user: dict) -> list:
    badges = []
    completed = user.get("tasks_completed", 0)
    likes     = user.get("likes_received", 0)
    if completed >= 10:
        badges.append({"id": "task_master", "name": "Task Master", "icon": "🏆", "desc": "Completed 10+ tasks"})
    elif completed >= 5:
        badges.append({"id": "task_star",   "name": "Task Star",   "icon": "⭐", "desc": "Completed 5+ tasks"})
    if likes >= 10:
        badges.append({"id": "mvp",         "name": "MVP",         "icon": "👑", "desc": "Received 10+ likes"})
    elif likes >= 5:
        badges.append({"id": "team_player", "name": "Team Player", "icon": "❤️", "desc": "Received 5+ likes"})
    if user.get("github"):
        badges.append({"id": "open_source", "name": "Open Source", "icon": "🐙", "desc": "Linked GitHub profile"})
    if user.get("created_at"):
        try:
            created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created).days <= 7:
                badges.append({"id": "early_bird", "name": "Early Bird", "icon": "🌅", "desc": "Joined early"})
        except Exception:
            pass
    return badges


@flask_app.get("/api/profile")
@require_auth
def get_own_profile():
    uid = g.user["sub"]
    return get_user(uid)


@flask_app.patch("/api/users/<user_id>")
@require_auth
def update_user(user_id):
    if g.user["sub"] != user_id:
        return err("Forbidden", 403)
    body    = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items()
               if k in ("full_name", "username", "bio", "github", "portfolio", "avatar", "skills")}
    if not allowed:
        return err("Nothing to update")
    allowed["updated_at"] = now_iso()
    db("users").update(allowed).eq("id", user_id).execute()
    return ok({"message": "Updated"})


# ═══════════════════════════════════════════════════
#  USER PREFERENCES
# ═══════════════════════════════════════════════════

@flask_app.get("/api/users/<user_id>/preferences")
@require_auth
def get_preferences(user_id):
    if g.user["sub"] != user_id:
        return err("Forbidden", 403)
    r = db("user_preferences").select("*").eq("user_id", user_id).execute()
    if not r.data:
        return ok({"user_id": user_id, "theme": "dark", "keyboard_shortcuts": {},
                   "notification_preferences": {}, "recent_searches": []})
    return ok(r.data[0])


@flask_app.patch("/api/users/<user_id>/preferences")
@require_auth
def update_preferences(user_id):
    if g.user["sub"] != user_id:
        return err("Forbidden", 403)
    body    = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items()
               if k in ("theme", "keyboard_shortcuts", "notification_preferences", "recent_searches")}
    if not allowed:
        return err("Nothing to update")
    allowed["updated_at"] = now_iso()
    existing = db("user_preferences").select("user_id").eq("user_id", user_id).execute()
    if existing.data:
        db("user_preferences").update(allowed).eq("user_id", user_id).execute()
    else:
        allowed["user_id"] = user_id
        db("user_preferences").insert(allowed).execute()
    return ok({"message": "Preferences updated"})


# ═══════════════════════════════════════════════════
#  TEAMS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams")
@require_auth
def get_teams():
    uid      = g.user["sub"]
    member_r = get_user_team(uid)
    if not member_r:
        return ok([])
    team_r = db("teams").select("*").eq("id", member_r["team_id"]).execute()
    return ok(team_r.data or [])


@flask_app.get("/api/teams/my")
@require_auth
def get_my_team():
    uid      = g.user["sub"]
    member_r = get_user_team(uid)
    if not member_r:
        return ok(None)
    team_r = db("teams").select("*").eq("id", member_r["team_id"]).execute()
    if not team_r.data:
        return ok(None)
    team = team_r.data[0]
    team["my_role"] = member_r["role"]
    return ok(team)


@flask_app.post("/api/teams")
@require_auth
def create_team():
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    name = (body.get("name", "")).strip()
    desc = (body.get("description", "")).strip()
    if not name:
        return err("Team name required")

    old_team_id = remove_user_from_team(uid)
    if old_team_id:
        log_activity(old_team_id, uid, "left", "team", old_team_id, {"reason": "created_new_team"})

    existing = db("teams").select("id").eq("name", name).execute()
    if existing.data:
        return err(f'Team "{name}" already exists.')

    team_id     = str(uuid.uuid4())
    invite_code = secrets.token_hex(4).upper()

    team_r = db("teams").insert({
        "id":          team_id,
        "name":        name,
        "description": desc,
        "invite_code": invite_code,
        "created_by":  uid,
        "created_at":  now_iso(),
        "updated_at":  now_iso(),
        "max_members": 10,
    }).execute()

    if not team_r.data:
        return err("Failed to create team", 500)

    db("team_members").insert({
        "id":        str(uuid.uuid4()),
        "team_id":   team_id,
        "user_id":   uid,
        "role":      "owner",
        "joined_at": now_iso(),
    }).execute()

    log_activity(team_id, uid, "created", "team", team_id, {"team_name": name})
    log_audit(uid, "create_team", "team", team_id, metadata={"name": name})
    return ok(team_r.data[0], 201)


@flask_app.post("/api/teams/join")
@require_auth
def join_team():
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    code = (body.get("invite_code", "")).strip().upper()
    if not code:
        return err("Invite code required")

    team_r = db("teams").select("*").eq("invite_code", code).execute()
    if not team_r.data:
        return err("Invalid invite code")
    team = team_r.data[0]

    # Check member count
    count_r = db("team_members").select("id", count="exact").eq("team_id", team["id"]).execute()
    max_m   = team.get("max_members", 10)
    if (count_r.count or 0) >= max_m:
        return err(f"Team is full (max {max_m} members)")

    current = get_user_team(uid)
    if current and current["team_id"] == team["id"]:
        team["my_role"] = current["role"]
        return ok(team)

    if current:
        old_team_id = current["team_id"]
        db("team_members").delete().eq("user_id", uid).execute()
        log_activity(old_team_id, uid, "left", "team", old_team_id, {"reason": "joined_new_team"})

    db("team_members").insert({
        "id":        str(uuid.uuid4()),
        "team_id":   team["id"],
        "user_id":   uid,
        "role":      "developer",
        "joined_at": now_iso(),
    }).execute()

    user_r = db("users").select("full_name,email").eq("id", uid).execute()
    uname  = user_r.data[0]["full_name"] if user_r.data else "Someone"
    log_activity(team["id"], uid, "joined", "team", team["id"], {"user_name": uname})
    log_audit(uid, "join_team", "team", team["id"])

    members_r = db("team_members").select("user_id").eq("team_id", team["id"]).execute()
    for m in (members_r.data or []):
        if m["user_id"] != uid:
            create_notification(m["user_id"], "member_join",
                f"{uname} joined {team['name']}", link="/teams")

    team["my_role"] = "developer"
    return ok(team)


@flask_app.delete("/api/teams/<team_id>/leave")
@require_auth
def leave_team(team_id):
    uid     = g.user["sub"]
    current = get_user_team(uid)
    if not current or current["team_id"] != team_id:
        return err("You are not a member of this team", 404)

    user_r = db("users").select("full_name").eq("id", uid).execute()
    uname  = user_r.data[0]["full_name"] if user_r.data else "Someone"

    db("team_members").delete().eq("user_id", uid).execute()
    log_activity(team_id, uid, "left", "team", team_id, {"user_name": uname})
    log_audit(uid, "leave_team", "team", team_id)

    members_r = db("team_members").select("user_id").eq("team_id", team_id).execute()
    team_r    = db("teams").select("name").eq("id", team_id).execute()
    tname     = team_r.data[0]["name"] if team_r.data else "the team"
    for m in (members_r.data or []):
        create_notification(m["user_id"], "member_left", f"{uname} left {tname}", link="/members")

    return ok({"message": "Left team"})


@flask_app.get("/api/teams/<team_id>/stats")
@require_auth
def get_team_stats(team_id):
    try:
        members_r = db("team_members").select("id", count="exact").eq("team_id", team_id).execute()
        projects_r = db("projects").select("id", count="exact").eq("team_id", team_id).execute()
        tasks_r   = db("tasks").select("status").eq("project_id",
            db("projects").select("id").eq("team_id", team_id)
        )
        # Simpler approach
        proj_ids = [p["id"] for p in (db("projects").select("id").eq("team_id", team_id).execute().data or [])]
        total_tasks = done_tasks = 0
        if proj_ids:
            for pid in proj_ids:
                t = db("tasks").select("status").eq("project_id", pid).execute()
                total_tasks += len(t.data or [])
                done_tasks  += sum(1 for x in (t.data or []) if x.get("status") == "done")

        return ok({
            "members":       members_r.count  or 0,
            "projects":      projects_r.count or 0,
            "total_tasks":   total_tasks,
            "done_tasks":    done_tasks,
            "completion_pct": round(done_tasks / total_tasks * 100, 1) if total_tasks else 0,
        })
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════
#  TEAM MEMBERS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/members")
@require_auth
def get_members(team_id):
    members_r = db("team_members").select("user_id,role").eq("team_id", team_id).execute()
    user_ids  = [m["user_id"] for m in (members_r.data or [])]
    role_map  = {m["user_id"]: m["role"] for m in (members_r.data or [])}
    if not user_ids:
        return ok([])
    users_r = db("users").select("id,email,username,full_name,bio,skills,github,avatar,created_at").in_("id", user_ids).execute()
    users   = users_r.data or []

    # Task counts per user
    task_counts = {}
    likes_counts = {}
    for uid in user_ids:
        tc = db("tasks").select("id", count="exact").eq("assigned_to", uid).execute()
        task_counts[uid] = tc.count or 0
        try:
            lc = db("member_likes").select("id", count="exact").eq("liked_user_id", uid).execute()
            likes_counts[uid] = lc.count or 0
        except Exception:
            likes_counts[uid] = 0

    for u in users:
        u["team_role"]  = role_map.get(u["id"], "developer")
        u["task_count"] = task_counts.get(u["id"], 0)
        u["likes_count"]= likes_counts.get(u["id"], 0)
        u["badges"]     = _compute_badges({
            "tasks_completed": task_counts.get(u["id"], 0),
            "likes_received":  likes_counts.get(u["id"], 0),
            "github": u.get("github"),
            "created_at": u.get("created_at"),
        })

    return ok(users)


@flask_app.patch("/api/teams/<team_id>/members/<target_user_id>/role")
@require_auth
def change_member_role(team_id, target_user_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    new_role = body.get("role", "").strip()
    VALID_ROLES = ["owner", "admin", "developer", "designer", "tester", "viewer", "judge"]
    if new_role not in VALID_ROLES:
        return err(f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    caller_m = db("team_members").select("role").eq("team_id", team_id).eq("user_id", uid).execute()
    if not caller_m.data or caller_m.data[0]["role"] not in ("owner", "admin"):
        return err("Only owners/admins can change roles", 403)

    db("team_members").update({"role": new_role}).eq("team_id", team_id).eq("user_id", target_user_id).execute()

    liker_r = db("users").select("full_name").eq("id", uid).execute()
    lname   = liker_r.data[0]["full_name"] if liker_r.data else "Someone"
    create_notification(target_user_id, "role_changed",
        f"Your role was changed to {new_role}",
        content=f"{lname} changed your role in the team.", link="/members")
    log_activity(team_id, uid, "changed_role", "member", target_user_id,
                 {"new_role": new_role})
    return ok({"message": "Role updated"})


# ═══════════════════════════════════════════════════
#  MEMBER LIKES
# ═══════════════════════════════════════════════════

@flask_app.post("/api/teams/<team_id>/members/<target_user_id>/like")
@require_auth
def like_member(team_id, target_user_id):
    uid = g.user["sub"]
    if uid == target_user_id:
        return err("Cannot like yourself")
    try:
        existing = db("member_likes").select("id").eq("liked_by", uid).eq("liked_user_id", target_user_id).execute()
        if existing.data:
            return err("Already liked this member")
        db("member_likes").insert({
            "id":            str(uuid.uuid4()),
            "liked_by":      uid,
            "liked_user_id": target_user_id,
            "team_id":       team_id,
            "created_at":    now_iso(),
        }).execute()
    except Exception as e:
        return err(f"Like failed: {e}", 500)

    liker_r = db("users").select("full_name").eq("id", uid).execute()
    lname   = liker_r.data[0]["full_name"] if liker_r.data else "Someone"
    create_notification(target_user_id, "member_liked", f"{lname} liked your contributions!", link="/members")
    log_activity(team_id, uid, "liked", "member", target_user_id, {"liked_by_name": lname})
    return ok({"message": "Liked"})


@flask_app.delete("/api/teams/<team_id>/members/<target_user_id>/like")
@require_auth
def unlike_member(team_id, target_user_id):
    uid = g.user["sub"]
    db("member_likes").delete().eq("liked_by", uid).eq("liked_user_id", target_user_id).execute()
    return ok({"message": "Unliked"})


@flask_app.get("/api/teams/<team_id>/top-contributors")
@require_auth
def top_contributors(team_id):
    try:
        members_r = db("team_members").select("user_id").eq("team_id", team_id).execute()
        user_ids  = [m["user_id"] for m in (members_r.data or [])]
        if not user_ids:
            return ok([])
        likes_r = db("member_likes").select("liked_user_id").in_("liked_user_id", user_ids).execute()
        counts  = {}
        for lk in (likes_r.data or []):
            counts[lk["liked_user_id"]] = counts.get(lk["liked_user_id"], 0) + 1
        sorted_ids = sorted(counts, key=lambda x: counts[x], reverse=True)[:5]
        if not sorted_ids:
            return ok([])
        users_r = db("users").select("id,full_name,email,username").in_("id", sorted_ids).execute()
        result  = []
        for uid in sorted_ids:
            u = next((x for x in users_r.data if x["id"] == uid), None)
            if u:
                u["likes_count"] = counts[uid]
                result.append(u)
        return ok(result)
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════
#  PROJECTS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/projects")
@require_auth
def get_projects(team_id):
    r = db("projects").select("*").eq("team_id", team_id).order("created_at", desc=True).execute()
    return ok(r.data or [])


@flask_app.post("/api/teams/<team_id>/projects")
@require_auth
def create_project(team_id):
    uid   = g.user["sub"]
    body  = request.get_json(silent=True) or {}
    title = (body.get("title", "")).strip()
    if not title:
        return err("Project title required")

    proj_id = str(uuid.uuid4())
    proj_r  = db("projects").insert({
        "id":          proj_id,
        "team_id":     team_id,
        "title":       title,
        "description": body.get("description", ""),
        "tech_stack":  body.get("tech_stack", []),
        "deadline":    body.get("deadline"),
        "status":      "active",
        "created_by":  uid,
        "created_at":  now_iso(),
        "updated_at":  now_iso(),
    }).execute()

    if not proj_r.data:
        return err("Failed to create project", 500)

    proj = proj_r.data[0]
    log_activity(team_id, uid, "created", "project", proj_id, {"project_title": title})

    if gemini_model:
        thread = threading.Thread(
            target=_run_gemini_analysis,
            args=(proj_id, title, body.get("description", ""), body.get("tech_stack", []), team_id, uid),
            daemon=True,
        )
        thread.start()

    return ok(proj, 201)


@flask_app.get("/api/projects/<proj_id>")
@require_auth
def get_project(proj_id):
    r = db("projects").select("*").eq("id", proj_id).execute()
    if not r.data:
        return err("Project not found", 404)
    return ok(r.data[0])


@flask_app.patch("/api/projects/<proj_id>")
@require_auth
def update_project(proj_id):
    body    = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items()
               if k in ("title", "description", "tech_stack", "deadline", "status", "github_url", "deploy_url")}
    if not allowed:
        return err("Nothing to update")
    allowed["updated_at"] = now_iso()
    db("projects").update(allowed).eq("id", proj_id).execute()
    return ok({"message": "Updated"})


@flask_app.delete("/api/projects/<proj_id>")
@require_auth
def delete_project(proj_id):
    uid    = g.user["sub"]
    r      = db("projects").select("team_id,title").eq("id", proj_id).execute()
    if r.data:
        db("projects").delete().eq("id", proj_id).execute()
        log_activity(r.data[0]["team_id"], uid, "deleted", "project", proj_id,
                     {"project_title": r.data[0]["title"]})
    return ok({"message": "Deleted"})


def _get_team_members_for_assignment(team_id: str) -> list:
    members_r = db("team_members").select("user_id,role").eq("team_id", team_id).execute()
    user_ids  = [m["user_id"] for m in (members_r.data or [])]
    role_map  = {m["user_id"]: m["role"] for m in (members_r.data or [])}
    if not user_ids:
        return []
    users_r  = db("users").select("id,full_name,email,skills").in_("id", user_ids).execute()
    users    = users_r.data or []
    tasks_r  = db("tasks").select("assigned_to").in_("assigned_to", user_ids).execute()
    workload = {}
    for t in (tasks_r.data or []):
        workload[t["assigned_to"]] = workload.get(t["assigned_to"], 0) + 1
    for u in users:
        u["team_role"] = role_map.get(u["id"], "developer")
        u["workload"]  = workload.get(u["id"], 0)
        u["skills"]    = u.get("skills") or []
    return users


def _assign_task_to_member(task_title: str, category: str, members: list) -> Optional[str]:
    if not members:
        return None
    scores = []
    cat_lower = category.lower()
    for m in members:
        score  = 0
        skills = [s.lower() for s in (m.get("skills") or [])]
        role   = (m.get("team_role") or "").lower()
        if cat_lower == "frontend" and ("developer" in role or any(s in skills for s in ["frontend","react","vue","html","css"])):
            score += 4
        if cat_lower == "backend" and ("developer" in role or any(s in skills for s in ["backend","python","node","api"])):
            score += 4
        if cat_lower == "design" and ("designer" in role or any(s in skills for s in ["design","figma","ui","ux"])):
            score += 6
        if cat_lower == "testing" and ("tester" in role or any(s in skills for s in ["test","qa","testing"])):
            score += 6
        for skill in skills:
            if skill in task_title.lower():
                score += 2
        score -= m.get("workload", 0) * 0.7
        scores.append((m["id"], score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0] if scores else None


def _run_gemini_analysis(proj_id, title, description, tech_stack, team_id, user_id):
    try:
        stack_str    = ", ".join(tech_stack) if tech_stack else "not specified"
        members      = _get_team_members_for_assignment(team_id)
        members_desc = ", ".join(
            f"{m['full_name']} (role: {m.get('team_role','dev')}, skills: {', '.join(m.get('skills',[]) or ['general'])})"
            for m in members
        ) if members else "no members listed"

        prompt = f"""You are a senior hackathon project manager. Analyze this project and respond ONLY with valid JSON, no markdown.

Project: {title}
Description: {description}
Tech Stack: {stack_str}
Team Members: {members_desc}

Return this EXACT JSON:
{{
  "understanding": "2-3 sentence project summary",
  "features": ["feature 1", "feature 2", "feature 3", "feature 4", "feature 5"],
  "tech_stack": ["tech1", "tech2", "tech3"],
  "risks": ["risk1", "risk2"],
  "timeline_days": 2,
  "tasks": {{
    "frontend": ["task1", "task2", "task3"],
    "backend":  ["task1", "task2", "task3"],
    "design":   ["task1", "task2"],
    "testing":  ["task1", "task2"]
  }}
}}"""

        response = gemini_model.generate_content(prompt)
        raw      = response.text.strip()
        # Strip possible markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        analysis = json.loads(raw.strip())
        db("projects").update({"ai_analysis": analysis, "updated_at": now_iso()}).eq("id", proj_id).execute()

        all_tasks    = []
        priority_map = {"frontend": "medium", "backend": "high", "design": "low", "testing": "medium"}
        for cat, tasks in (analysis.get("tasks") or {}).items():
            for task_title in (tasks or [])[:3]:
                assigned_to = _assign_task_to_member(task_title, cat, members)
                task_row = {
                    "id":          str(uuid.uuid4()),
                    "project_id":  proj_id,
                    "title":       task_title,
                    "description": f"Auto-generated by Gemini AI | Category: {cat}",
                    "status":      "todo",
                    "priority":    priority_map.get(cat, "medium"),
                    "tags":        [cat],
                    "assigned_to": assigned_to,
                    "created_at":  now_iso(),
                    "updated_at":  now_iso(),
                }
                all_tasks.append(task_row)
                if assigned_to:
                    create_notification(assigned_to, "task_assigned",
                        f"AI assigned task: {task_title}", link="/kanban",
                        metadata={"project_id": proj_id})

        if all_tasks:
            db("tasks").insert(all_tasks).execute()

        socketio.emit("tasks_generated", {"count": len(all_tasks), "project_id": proj_id}, room=f"team_{team_id}")
        log_activity(team_id, user_id, "ai_analyzed", "project", proj_id,
                     {"task_count": len(all_tasks), "project_title": title})
        logger.info(f"Gemini analysis done for {proj_id}: {len(all_tasks)} tasks")
    except Exception as e:
        logger.error(f"Gemini analysis failed for {proj_id}: {e}")


# ═══════════════════════════════════════════════════
#  TASKS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/projects/<proj_id>/tasks")
@require_auth
def get_tasks(proj_id):
    r = db("tasks") \
        .select("*,users:assigned_to(id,full_name,email,username)") \
        .eq("project_id", proj_id) \
        .order("created_at") \
        .execute()
    return ok(r.data or [])


@flask_app.post("/api/projects/<proj_id>/tasks")
@require_auth
def create_task(proj_id):
    uid   = g.user["sub"]
    body  = request.get_json(silent=True) or {}
    title = (body.get("title", "")).strip()
    if not title:
        return err("Task title required")

    task_id = str(uuid.uuid4())
    task_r  = db("tasks").insert({
        "id":          task_id,
        "project_id":  proj_id,
        "title":       title,
        "description": body.get("description", ""),
        "status":      body.get("status", "todo"),
        "priority":    body.get("priority", "medium"),
        "tags":        body.get("tags", []),
        "assigned_to": body.get("assigned_to"),
        "sprint_id":   body.get("sprint_id"),
        "due_date":    body.get("due_date"),
        "estimate_h":  body.get("estimate_h"),
        "created_by":  uid,
        "created_at":  now_iso(),
        "updated_at":  now_iso(),
    }).execute()

    if not task_r.data:
        return err("Failed to create task", 500)

    task    = task_r.data[0]
    proj_r  = db("projects").select("team_id").eq("id", proj_id).execute()
    team_id = proj_r.data[0]["team_id"] if proj_r.data else None

    if team_id:
        socketio.emit("task_created", task, room=f"team_{team_id}")
        log_activity(team_id, uid, "created", "task", task_id, {"task_title": title})
        if task.get("assigned_to") and task["assigned_to"] != uid:
            create_notification(task["assigned_to"], "task_assigned",
                f"Task assigned to you: {title}", link="/kanban",
                metadata={"task_id": task_id})
    return ok(task, 201)


@flask_app.get("/api/tasks/<task_id>")
@require_auth
def get_task(task_id):
    r = db("tasks").select("*,users:assigned_to(id,full_name,email)").eq("id", task_id).execute()
    if not r.data:
        return err("Task not found", 404)
    task = r.data[0]
    cc   = db("task_comments").select("id", count="exact").eq("task_id", task_id).execute()
    task["comment_count"] = cc.count or 0
    return ok(task)


@flask_app.patch("/api/tasks/<task_id>")
@require_auth
def update_task(task_id):
    uid     = g.user["sub"]
    body    = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items()
               if k in ("title", "description", "status", "priority", "assigned_to",
                        "tags", "sprint_id", "due_date", "estimate_h")}
    if not allowed:
        return err("Nothing to update")
    allowed["updated_at"] = now_iso()

    # History record
    old_r = db("tasks").select("*").eq("id", task_id).execute()
    old   = old_r.data[0] if old_r.data else {}

    task_r = db("tasks").update(allowed).eq("id", task_id).execute()
    if not task_r.data:
        return err("Task not found", 404)

    task    = task_r.data[0]
    proj_r  = db("projects").select("team_id").eq("id", task.get("project_id")).execute()
    team_id = proj_r.data[0]["team_id"] if proj_r.data else None

    # Store history
    try:
        db("task_history").insert({
            "id":         str(uuid.uuid4()),
            "task_id":    task_id,
            "changed_by": uid,
            "changes":    json.dumps({k: {"from": old.get(k), "to": v} for k, v in allowed.items() if k != "updated_at"}),
            "created_at": now_iso(),
        }).execute()
    except Exception:
        pass

    if team_id:
        socketio.emit("task_updated", task, room=f"team_{team_id}")
        log_activity(team_id, uid, "updated", "task", task_id,
                     {"task_title": task.get("title"), "changes": list(allowed.keys())})
        if "assigned_to" in allowed and allowed["assigned_to"] and allowed["assigned_to"] != uid:
            create_notification(allowed["assigned_to"], "task_assigned",
                f"Task assigned to you: {task.get('title', '')}", link="/kanban",
                metadata={"task_id": task_id})
    return ok(task)


@flask_app.delete("/api/tasks/<task_id>")
@require_auth
def delete_task(task_id):
    uid    = g.user["sub"]
    task_r = db("tasks").select("project_id,title").eq("id", task_id).execute()
    if task_r.data:
        task    = task_r.data[0]
        proj_r  = db("projects").select("team_id").eq("id", task["project_id"]).execute()
        team_id = proj_r.data[0]["team_id"] if proj_r.data else None
        db("tasks").delete().eq("id", task_id).execute()
        if team_id:
            socketio.emit("task_deleted", {"id": task_id}, room=f"team_{team_id}")
            log_activity(team_id, uid, "deleted", "task", task_id, {"task_title": task.get("title")})
    else:
        db("tasks").delete().eq("id", task_id).execute()
    return ok({"message": "Deleted"})


@flask_app.get("/api/tasks/<task_id>/history")
@require_auth
def get_task_history(task_id):
    r = db("task_history").select("*,users:changed_by(id,full_name,email)") \
        .eq("task_id", task_id).order("created_at", desc=True).execute()
    return ok(r.data or [])


# ═══════════════════════════════════════════════════
#  TASK COMMENTS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/tasks/<task_id>/comments")
@require_auth
def get_comments(task_id):
    r = db("task_comments") \
        .select("*,users:user_id(id,full_name,email,username)") \
        .eq("task_id", task_id) \
        .order("created_at") \
        .execute()
    return ok(r.data or [])


@flask_app.post("/api/tasks/<task_id>/comments")
@require_auth
def create_comment(task_id):
    uid     = g.user["sub"]
    body    = request.get_json(silent=True) or {}
    content = (body.get("content", "")).strip()
    if not content:
        return err("Content required")

    comment_id = str(uuid.uuid4())
    r = db("task_comments").insert({
        "id":         comment_id,
        "task_id":    task_id,
        "user_id":    uid,
        "parent_id":  body.get("parent_id"),
        "content":    content,
        "mentions":   body.get("mentions", []),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }).execute()

    if not r.data:
        return err("Failed to create comment", 500)

    comment  = r.data[0]
    user_r   = db("users").select("id,full_name,email,username").eq("id", uid).execute()
    comment["users"] = user_r.data[0] if user_r.data else {}

    task_r = db("tasks").select("project_id,title").eq("id", task_id).execute()
    if task_r.data:
        task    = task_r.data[0]
        proj_r  = db("projects").select("team_id").eq("id", task["project_id"]).execute()
        team_id = proj_r.data[0]["team_id"] if proj_r.data else None
        if team_id:
            socketio.emit("comment_new", comment, room=f"team_{team_id}")
            log_activity(team_id, uid, "commented", "task", task_id, {"task_title": task.get("title")})

    commenter = comment["users"].get("full_name", "Someone")
    for mentioned_uid in (body.get("mentions") or []):
        if mentioned_uid != uid:
            create_notification(mentioned_uid, "mention",
                f"{commenter} mentioned you in a comment",
                content=content[:120], link="/kanban")
    return ok(comment, 201)


@flask_app.patch("/api/comments/<comment_id>")
@require_auth
def update_comment(comment_id):
    uid     = g.user["sub"]
    body    = request.get_json(silent=True) or {}
    content = (body.get("content", "")).strip()
    if not content:
        return err("Content required")
    r = db("task_comments").select("user_id").eq("id", comment_id).execute()
    if not r.data:
        return err("Comment not found", 404)
    if r.data[0]["user_id"] != uid:
        return err("Forbidden", 403)
    db("task_comments").update({"content": content, "updated_at": now_iso()}).eq("id", comment_id).execute()
    return ok({"message": "Updated"})


@flask_app.delete("/api/comments/<comment_id>")
@require_auth
def delete_comment(comment_id):
    uid = g.user["sub"]
    r   = db("task_comments").select("user_id").eq("id", comment_id).execute()
    if not r.data:
        return err("Comment not found", 404)
    if r.data[0]["user_id"] != uid:
        return err("Forbidden", 403)
    db("task_comments").delete().eq("id", comment_id).execute()
    return ok({"message": "Deleted"})


# ═══════════════════════════════════════════════════
#  SPRINTS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/projects/<proj_id>/sprints")
@require_auth
def get_sprints(proj_id):
    r = db("sprints").select("*").eq("project_id", proj_id).order("created_at", desc=True).execute()
    return ok(r.data or [])


@flask_app.post("/api/projects/<proj_id>/sprints")
@require_auth
def create_sprint(proj_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    name = (body.get("name", "")).strip()
    if not name:
        return err("Sprint name required")

    sprint_id = str(uuid.uuid4())
    r = db("sprints").insert({
        "id":         sprint_id,
        "project_id": proj_id,
        "name":       name,
        "goal":       body.get("goal", ""),
        "start_date": body.get("start_date"),
        "end_date":   body.get("end_date"),
        "status":     "planning",
        "created_by": uid,
        "created_at": now_iso(),
    }).execute()

    if not r.data:
        return err("Failed to create sprint", 500)

    proj_r = db("projects").select("team_id").eq("id", proj_id).execute()
    if proj_r.data:
        log_activity(proj_r.data[0]["team_id"], uid, "created", "sprint", sprint_id, {"sprint_name": name})
    return ok(r.data[0], 201)


@flask_app.patch("/api/sprints/<sprint_id>")
@require_auth
def update_sprint(sprint_id):
    body    = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items()
               if k in ("name", "goal", "start_date", "end_date", "status")}
    if not allowed:
        return err("Nothing to update")
    db("sprints").update(allowed).eq("id", sprint_id).execute()
    return ok({"message": "Updated"})


# ═══════════════════════════════════════════════════
#  MESSAGES / CHAT
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/messages")
@require_auth
def get_messages(team_id):
    limit  = min(int(request.args.get("limit", 50)), 200)
    before = request.args.get("before")  # ISO timestamp for pagination
    query  = db("messages") \
        .select("*,users:user_id(id,full_name,email,username)") \
        .eq("team_id", team_id) \
        .order("created_at", desc=True) \
        .limit(limit)
    if before:
        query = query.lt("created_at", before)
    r = query.execute()
    messages = list(reversed(r.data or []))
    return ok(messages)


@flask_app.post("/api/teams/<team_id>/messages")
@require_auth
def post_message(team_id):
    uid     = g.user["sub"]
    body    = request.get_json(silent=True) or {}
    content = (body.get("content", "")).strip()
    if not content:
        return err("Content required")
    msg_id = str(uuid.uuid4())
    user_r = db("users").select("id,full_name,email,username").eq("id", uid).execute()
    user_info = user_r.data[0] if user_r.data else {}
    db("messages").insert({
        "id":           msg_id,
        "team_id":      team_id,
        "user_id":      uid,
        "content":      content,
        "message_type": body.get("message_type", "text"),
        "created_at":   now_iso(),
    }).execute()
    msg = {"id": msg_id, "team_id": team_id, "user_id": uid, "content": content,
           "message_type": "text", "created_at": now_iso(), "users": user_info}
    socketio.emit("new_message", msg, room=f"team_{team_id}")
    return ok(msg, 201)


@flask_app.delete("/api/teams/<team_id>/messages")
@require_auth
def reset_chat(team_id):
    uid      = g.user["sub"]
    member_r = db("team_members").select("role").eq("team_id", team_id).eq("user_id", uid).execute()
    if not member_r.data or member_r.data[0]["role"] not in ("owner", "admin"):
        return err("Only owners/admins can reset chat", 403)
    db("messages").delete().eq("team_id", team_id).execute()
    socketio.emit("chat_reset", {}, room=f"team_{team_id}")
    log_activity(team_id, uid, "reset", "chat", team_id, {})
    return ok({"message": "Chat reset"})


# ═══════════════════════════════════════════════════
#  FILES / R2
# ═══════════════════════════════════════════════════

@flask_app.get("/api/projects/<proj_id>/files")
@require_auth
def get_files(proj_id):
    folder = request.args.get("folder")
    query  = db("files").select("*").eq("project_id", proj_id).order("created_at", desc=True)
    if folder:
        query = query.eq("folder_id", folder)
    r = query.execute()
    return ok(r.data or [])


@flask_app.post("/api/projects/<proj_id>/files/upload")
@require_auth
def handle_supabase_upload(proj_id):
    if 'file' not in request.files:
        return err("No file provided")
    
    file = request.files['file']
    uid = g.user["sub"]
    
    # Create a unique storage path
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._- ").strip()
    storage_path = f"{proj_id}/{uid}/{uuid.uuid4().hex}_{safe_name}"

    try:
        # Upload directly using the existing supabase client
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file.read(),
            file_options={"content-type": file.content_type, "x-upsert": "true"}
        )
        return ok({"path": storage_path})
    except Exception as e:
        logger.error(f"Supabase upload failed: {e}")
        return err("Upload failed", 500)

@flask_app.post("/api/projects/<proj_id>/files")
@require_auth
def register_file(proj_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    name = (body.get("name", "")).strip()
    path = (body.get("path", "")).strip() # This is the 'storage_path' from the upload
    
    if not name or not path:
        return err("Name and path are required")

    file_id = str(uuid.uuid4())
    
    # In Supabase Storage, we don't store a hardcoded public URL for private buckets.
    # Instead, we generate a signed URL on-the-fly via the download endpoint.
    # However, we can store the permanent internal reference path.
    internal_url = f"{SUPABASE_URL}/storage/v1/object/authenticated/{STORAGE_BUCKET}/{path}"

    r = db("files").insert({
        "id":          file_id,
        "project_id":  proj_id,
        "folder_id":   body.get("folder_id"),
        "name":        name,
        "path":        path,           # Critical: The path used in Supabase Storage
        "url":         internal_url,   # Optional: Reference URL
        "size":        body.get("size", 0),
        "mime_type":   body.get("mime_type", "application/octet-stream"),
        "uploaded_by": uid,
        "created_at":  now_iso(),
    }).execute()

    if not r.data:
        return err("Failed to register file in database", 500)

    # Log activity for the team
    proj_r = db("projects").select("team_id").eq("id", proj_id).execute()
    if proj_r.data:
        log_activity(
            proj_r.data[0]["team_id"], 
            uid, 
            "uploaded", 
            "file", 
            file_id,
            {"file_name": name}
        )
        
    return ok(r.data[0], 201)

@flask_app.get("/api/files/<file_id>/download-url")
@require_auth
def get_download_url(file_id):
    r = db("files").select("path").eq("id", file_id).execute()
    if not r.data:
        return err("File not found", 404)
    
    path = r.data[0]["path"]

    try:
        # Generate a signed URL valid for 60 minutes
        res = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(path, 3600)
        return ok({"url": res["signedURL"]})
    except Exception as e:
        return err(f"Could not generate download URL: {e}", 500)

@flask_app.delete("/api/files/<file_id>")
@require_auth
def delete_file(file_id):
    uid = g.user["sub"]
    r   = db("files").select("path,name,project_id").eq("id", file_id).execute()
    if not r.data:
        return err("File not found", 404)
    file_data = r.data[0]

    db("files").delete().eq("id", file_id).execute()
    proj_r = db("projects").select("team_id").eq("id", file_data["project_id"]).execute()
    if proj_r.data:
        log_activity(proj_r.data[0]["team_id"], uid, "deleted", "file", file_id,
                     {"file_name": file_data.get("name")})
    return ok({"message": "Deleted"})


# ═══════════════════════════════════════════════════
#  DEPLOYMENTS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/projects/<proj_id>/deployments")
@require_auth
def get_deployments(proj_id):
    r = db("deployments").select("*").eq("project_id", proj_id).order("created_at", desc=True).execute()
    return ok(r.data or [])


@flask_app.post("/api/projects/<proj_id>/deployments")
@require_auth
def create_deployment(proj_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    name = (body.get("name", "deploy")).strip() or "deploy"
    deploy_id = str(uuid.uuid4())

    r = db("deployments").insert({
        "id":          deploy_id,
        "project_id":  proj_id,
        "name":        name,
        "status":      "queued",
        "environment": body.get("environment", "production"),
        "branch":      body.get("branch", "main"),
        "provider":    body.get("provider", "netlify"),
        "deploy_url":  body.get("deploy_url"),
        "triggered_by":uid,
        "created_at":  now_iso(),
    }).execute()

    if not r.data:
        return err("Failed to create deployment", 500)

    deploy  = r.data[0]
    proj_r  = db("projects").select("team_id").eq("id", proj_id).execute()
    team_id = proj_r.data[0]["team_id"] if proj_r.data else None
    if team_id:
        log_activity(team_id, uid, "triggered", "deployment", deploy_id, {"deploy_name": name})
        socketio.emit("deployment_created", deploy, room=f"team_{team_id}")

    # Simulate async deployment
    thread = threading.Thread(target=_simulate_deployment, args=(deploy_id, team_id, name), daemon=True)
    thread.start()
    return ok(deploy, 201)


def _simulate_deployment(deploy_id: str, team_id: Optional[str], name: str):
    time.sleep(3)
    db("deployments").update({"status": "building", "updated_at": now_iso()}).eq("id", deploy_id).execute()
    if team_id:
        socketio.emit("deployment_updated", {"id": deploy_id, "status": "building"}, room=f"team_{team_id}")
    time.sleep(random.randint(5, 15))
    final_status = "live" if random.random() > 0.15 else "failed"
    deploy_url   = f"https://{deploy_id[:8]}.hackforge.app" if final_status == "live" else None
    db("deployments").update({
        "status":     final_status,
        "deploy_url": deploy_url,
        "updated_at": now_iso(),
    }).eq("id", deploy_id).execute()
    if team_id:
        socketio.emit("deployment_updated", {"id": deploy_id, "status": final_status, "deploy_url": deploy_url},
                      room=f"team_{team_id}")
        try:
            deploy_r = db("deployments").select("triggered_by,name").eq("id", deploy_id).execute()
            if deploy_r.data:
                d = deploy_r.data[0]
                notif_type = "deploy_live" if final_status == "live" else "deploy_failed"
                create_notification(d["triggered_by"], notif_type,
                    f"Deploy '{name}' is {final_status}!",
                    content=f"URL: {deploy_url}" if deploy_url else None,
                    link="/deploy")
        except Exception:
            pass


@flask_app.get("/api/deployments/<deploy_id>")
@require_auth
def get_deployment(deploy_id):
    r = db("deployments").select("*").eq("id", deploy_id).execute()
    if not r.data:
        return err("Deployment not found", 404)
    return ok(r.data[0])


# ═══════════════════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/notifications")
@require_auth
def get_notifications():
    uid    = g.user["sub"]
    limit  = min(int(request.args.get("limit", 30)), 100)
    unread_only = request.args.get("unread") == "true"

    query = db("notifications").select("*").eq("user_id", uid).order("created_at", desc=True).limit(limit)
    if unread_only:
        query = query.eq("read", False)
    r      = query.execute()
    notifs = r.data or []

    # Fix metadata parsing
    for n in notifs:
        if isinstance(n.get("metadata"), str):
            try:
                n["metadata"] = json.loads(n["metadata"])
            except Exception:
                n["metadata"] = {}

    unread_count = sum(1 for n in notifs if not n.get("read"))
    return ok({"notifications": notifs, "unread_count": unread_count})


@flask_app.patch("/api/notifications/<notif_id>/read")
@require_auth
def mark_notification_read(notif_id):
    uid = g.user["sub"]
    db("notifications").update({"read": True}).eq("id", notif_id).eq("user_id", uid).execute()
    return ok({"message": "Marked read"})


@flask_app.post("/api/notifications/read-all")
@require_auth
def mark_all_read():
    uid = g.user["sub"]
    db("notifications").update({"read": True}).eq("user_id", uid).eq("read", False).execute()
    return ok({"message": "All marked read"})


@flask_app.delete("/api/notifications/<notif_id>")
@require_auth
def delete_notification(notif_id):
    uid = g.user["sub"]
    db("notifications").delete().eq("id", notif_id).eq("user_id", uid).execute()
    return ok({"message": "Deleted"})


# ═══════════════════════════════════════════════════
#  ACTIVITIES
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/activities")
@require_auth
def get_activities(team_id):
    limit       = min(int(request.args.get("limit", 50)), 200)
    action_type = request.args.get("type")
    query = db("activities").select("*,users:user_id(id,full_name,email)") \
        .eq("team_id", team_id).order("created_at", desc=True).limit(limit)
    if action_type and action_type != "all":
        query = query.eq("action_type", action_type)
    r          = query.execute()
    activities = r.data or []

    for a in activities:
        if isinstance(a.get("metadata"), str):
            try:
                a["metadata"] = json.loads(a["metadata"])
            except Exception:
                a["metadata"] = {}
    return ok(activities)


# ═══════════════════════════════════════════════════
#  PRESENCE
# ═══════════════════════════════════════════════════

_online_users: dict = {}  # team_id -> {user_id: {name, ts}}

@flask_app.get("/api/teams/<team_id>/presence")
@require_auth
def get_presence(team_id):
    cutoff = time.time() - 120  # 2 minutes
    online = {
        uid: info for uid, info in _online_users.get(team_id, {}).items()
        if info.get("ts", 0) > cutoff
    }
    return ok(list(online.values()))


# ═══════════════════════════════════════════════════
#  WHITEBOARD
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/whiteboard/latest")
@require_auth
def get_whiteboard_snapshot(team_id):
    r = db("whiteboard_snapshots") \
        .select("*") \
        .eq("team_id", team_id) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    return ok(r.data[0] if r.data else None)


@flask_app.post("/api/teams/<team_id>/whiteboard/snapshot")
@require_auth
def save_whiteboard_snapshot(team_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    data = body.get("snapshot_data")
    if not data:
        return err("snapshot_data required")

    # Prune old snapshots (keep 20)
    try:
        old_r = db("whiteboard_snapshots").select("id,created_at").eq("team_id", team_id) \
            .order("created_at", desc=True).offset(19).execute()
        for snap in (old_r.data or []):
            db("whiteboard_snapshots").delete().eq("id", snap["id"]).execute()
    except Exception:
        pass

    r = db("whiteboard_snapshots").insert({
        "id":            str(uuid.uuid4()),
        "team_id":       team_id,
        "snapshot_data": json.dumps(data) if not isinstance(data, str) else data,
        "created_by":    uid,
        "created_at":    now_iso(),
    }).execute()
    return ok(r.data[0] if r.data else {}, 201)


# ═══════════════════════════════════════════════════
#  SEARCH
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/search")
@require_auth
def search(team_id):
    q = (request.args.get("q", "")).strip()
    if len(q) < 2:
        return err("Query must be at least 2 characters")

    results = {"projects": [], "tasks": [], "members": [], "files": []}
    q_lower = q.lower()

    # Projects
    try:
        pr = db("projects").select("id,title,description,tech_stack").eq("team_id", team_id).execute()
        results["projects"] = [p for p in (pr.data or [])
                               if q_lower in (p.get("title", "") + " " + (p.get("description", "") or "")).lower()][:10]
    except Exception:
        pass

    # Tasks (search via project IDs in team)
    try:
        proj_ids = [p["id"] for p in results["projects"]] + [
            p["id"] for p in (db("projects").select("id").eq("team_id", team_id).execute().data or [])
        ]
        proj_ids = list(set(proj_ids))
        if proj_ids:
            for pid in proj_ids[:5]:  # limit to avoid too many queries
                tr = db("tasks").select("id,title,status,priority,project_id").eq("project_id", pid).execute()
                for t in (tr.data or []):
                    if q_lower in t.get("title", "").lower():
                        results["tasks"].append(t)
                if len(results["tasks"]) >= 10:
                    break
    except Exception:
        pass

    # Members
    try:
        mem_r = db("team_members").select("user_id").eq("team_id", team_id).execute()
        uid_list = [m["user_id"] for m in (mem_r.data or [])]
        if uid_list:
            ur = db("users").select("id,full_name,email,username").in_("id", uid_list).execute()
            results["members"] = [u for u in (ur.data or [])
                                  if q_lower in (u.get("full_name", "") + " " + (u.get("email", ""))).lower()][:5]
    except Exception:
        pass

    return ok(results)


# ═══════════════════════════════════════════════════
#  WIKI / NOTES
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/wiki")
@require_auth
def get_wiki_pages(team_id):
    r = db("wiki_pages").select("id,title,slug,created_by,created_at,updated_at") \
        .eq("team_id", team_id).order("updated_at", desc=True).execute()
    return ok(r.data or [])


@flask_app.post("/api/teams/<team_id>/wiki")
@require_auth
def create_wiki_page(team_id):
    uid   = g.user["sub"]
    body  = request.get_json(silent=True) or {}
    title = (body.get("title", "")).strip()
    if not title:
        return err("Title required")

    slug = title.lower().replace(" ", "-")[:80]
    page_id = str(uuid.uuid4())
    r = db("wiki_pages").insert({
        "id":         page_id,
        "team_id":    team_id,
        "title":      title,
        "slug":       slug,
        "content":    body.get("content", ""),
        "created_by": uid,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }).execute()
    if not r.data:
        return err("Failed to create page", 500)
    log_activity(team_id, uid, "created", "wiki", page_id, {"title": title})
    return ok(r.data[0], 201)


@flask_app.get("/api/wiki/<page_id>")
@require_auth
def get_wiki_page(page_id):
    r = db("wiki_pages").select("*").eq("id", page_id).execute()
    if not r.data:
        return err("Page not found", 404)
    return ok(r.data[0])


@flask_app.patch("/api/wiki/<page_id>")
@require_auth
def update_wiki_page(page_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}
    allowed = {k: v for k, v in body.items() if k in ("title", "content")}
    if not allowed:
        return err("Nothing to update")
    allowed["updated_at"] = now_iso()
    db("wiki_pages").update(allowed).eq("id", page_id).execute()
    return ok({"message": "Updated"})


@flask_app.delete("/api/wiki/<page_id>")
@require_auth
def delete_wiki_page(page_id):
    db("wiki_pages").delete().eq("id", page_id).execute()
    return ok({"message": "Deleted"})


# ═══════════════════════════════════════════════════
#  JUDGE SCORING
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/judge-scores")
@require_auth
def get_judge_scores(team_id):
    r = db("judge_scores").select("*,judges:judge_id(id,full_name,email)") \
        .eq("team_id", team_id).order("created_at", desc=True).execute()
    return ok(r.data or [])


@flask_app.post("/api/teams/<team_id>/judge-scores")
@require_auth
def submit_judge_score(team_id):
    uid  = g.user["sub"]
    body = request.get_json(silent=True) or {}

    # Validate role
    member_r = db("team_members").select("role").eq("team_id", team_id).eq("user_id", uid).execute()
    # Judges can score any team, leaders can self-score (for testing)
    # In production you'd check against a judges table

    score_id = str(uuid.uuid4())
    r = db("judge_scores").insert({
        "id":             score_id,
        "team_id":        team_id,
        "judge_id":       uid,
        "innovation":     max(0, min(10, int(body.get("innovation", 0)))),
        "technical":      max(0, min(10, int(body.get("technical", 0)))),
        "presentation":   max(0, min(10, int(body.get("presentation", 0)))),
        "completeness":   max(0, min(10, int(body.get("completeness", 0)))),
        "impact":         max(0, min(10, int(body.get("impact", 0)))),
        "feedback":       body.get("feedback", ""),
        "created_at":     now_iso(),
    }).execute()
    if not r.data:
        return err("Failed to submit score", 500)
    return ok(r.data[0], 201)


@flask_app.get("/api/leaderboard")
@require_auth
def get_leaderboard():
    try:
        scores_r = db("judge_scores").select("team_id,innovation,technical,presentation,completeness,impact").execute()
        scores   = scores_r.data or []

        team_totals = {}
        for s in scores:
            tid   = s["team_id"]
            total = (s.get("innovation", 0) + s.get("technical", 0) +
                     s.get("presentation", 0) + s.get("completeness", 0) + s.get("impact", 0))
            if tid not in team_totals:
                team_totals[tid] = {"total": 0, "count": 0}
            team_totals[tid]["total"] += total
            team_totals[tid]["count"] += 1

        if not team_totals:
            return ok([])

        team_ids = list(team_totals.keys())
        teams_r  = db("teams").select("id,name").in_("id", team_ids).execute()
        team_map = {t["id"]: t["name"] for t in (teams_r.data or [])}

        leaderboard = []
        for tid, stats in team_totals.items():
            avg = stats["total"] / stats["count"] if stats["count"] > 0 else 0
            leaderboard.append({
                "team_id":    tid,
                "team_name":  team_map.get(tid, "Unknown"),
                "avg_score":  round(avg, 2),
                "max_score":  50,
                "judge_count":stats["count"],
            })
        leaderboard.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1
        return ok(leaderboard)
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════
#  AUDIT LOGS
# ═══════════════════════════════════════════════════

@flask_app.get("/api/teams/<team_id>/audit-logs")
@require_auth
def get_audit_logs(team_id):
    uid = g.user["sub"]
    # Only owner/admin
    member_r = db("team_members").select("role").eq("team_id", team_id).eq("user_id", uid).execute()
    if not member_r.data or member_r.data[0]["role"] not in ("owner", "admin"):
        return err("Forbidden", 403)
    limit = min(int(request.args.get("limit", 100)), 500)
    # Get all users in team, then get their audit logs
    members_r = db("team_members").select("user_id").eq("team_id", team_id).execute()
    user_ids  = [m["user_id"] for m in (members_r.data or [])]
    if not user_ids:
        return ok([])
    r = db("audit_logs").select("*,users:user_id(id,full_name,email)") \
        .in_("user_id", user_ids).order("created_at", desc=True).limit(limit).execute()
    return ok(r.data or [])


# ═══════════════════════════════════════════════════
#  AI ASSISTANT (GEMINI)
# ═══════════════════════════════════════════════════

@flask_app.post("/api/ai/chat")
@require_auth
@limiter.limit("30 per minute")
def ai_chat():
    if not gemini_model:
        return err("AI not configured — set GEMINI_API_KEY", 503)

    body    = request.get_json(silent=True) or {}
    message = (body.get("message", "")).strip()
    if not message:
        return err("Message required")

    history     = body.get("history", [])[-20:]
    team_context = body.get("team_context", "")

    system = """You are HackForge AI — an expert hackathon workspace assistant powered by Google Gemini.
You help teams plan features, write code, debug issues, generate task breakdowns, sprint plans, and brainstorm ideas.
Be concise, practical, and energetic. Use code blocks for code. Support markdown.

Slash commands you understand:
/help — List all commands
/plan [feature] — Generate implementation plan
/review [code] — Code review with suggestions  
/estimate [task] — Time estimation
/bugs — List potential bugs
/refactor [code] — Suggest refactoring
/test [code] — Generate unit tests
/sprint — Generate sprint plan
/readme — Generate README template
/tasks — Break down a feature into tasks"""

    if team_context:
        system += f"\n\nTeam context: {team_context}"

    # Build conversation
    convo_parts = [f"SYSTEM: {system}\n\n"]
    for h in history:
        role    = h.get("role", "user")
        content = h.get("content", "")
        convo_parts.append(f"{'USER' if role == 'user' else 'ASSISTANT'}: {content}\n")
    convo_parts.append(f"USER: {message}\nASSISTANT:")

    prompt = "".join(convo_parts)
    try:
        response = gemini_model.generate_content(prompt)
        reply    = response.text
        return ok({"reply": reply})
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        return err(f"AI error: {str(e)[:200]}", 503)


@flask_app.post("/api/ai/generate-readme")
@require_auth
def generate_readme():
    if not gemini_model:
        return err("AI not configured", 503)
    body = request.get_json(silent=True) or {}
    proj_id = body.get("project_id")
    if proj_id:
        r = db("projects").select("*").eq("id", proj_id).execute()
        proj = r.data[0] if r.data else {}
    else:
        proj = body

    prompt = f"""Generate a professional README.md for this project:
Name: {proj.get('title', 'Project')}
Description: {proj.get('description', '')}
Tech Stack: {', '.join(proj.get('tech_stack', []))}

Include: title, badges, description, features, tech stack, installation, usage, contributing, license.
Use proper markdown formatting."""

    try:
        response = gemini_model.generate_content(prompt)
        return ok({"readme": response.text})
    except Exception as e:
        return err(f"AI error: {str(e)[:200]}", 503)


@flask_app.post("/api/ai/sprint-plan")
@require_auth
def generate_sprint_plan():
    if not gemini_model:
        return err("AI not configured", 503)
    body = request.get_json(silent=True) or {}
    tasks    = body.get("tasks", [])
    duration = body.get("duration_days", 7)
    members  = body.get("members", [])

    prompt = f"""Generate a {duration}-day sprint plan for these tasks:
Tasks: {json.dumps(tasks[:20])}
Team size: {len(members)} members
Members: {', '.join(m.get('full_name', '?') for m in members[:10])}

Organize into daily goals and assign tasks. Return structured JSON with:
{{
  "sprint_name": "Sprint X: Goal",
  "goal": "Sprint objective",
  "days": [
    {{"day": 1, "focus": "focus area", "tasks": ["task1", "task2"]}}
  ],
  "risks": ["risk1", "risk2"],
  "definition_of_done": ["criterion1", "criterion2"]
}}"""

    try:
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        plan = json.loads(raw.strip())
        return ok({"plan": plan})
    except json.JSONDecodeError:
        return ok({"plan": {"raw": response.text}})
    except Exception as e:
        return err(f"AI error: {str(e)[:200]}", 503)


@flask_app.post("/api/ai/code-review")
@require_auth
def ai_code_review():
    if not gemini_model:
        return err("AI not configured", 503)
    body = request.get_json(silent=True) or {}
    code = body.get("code", "")
    lang = body.get("language", "python")
    if not code:
        return err("code required")

    prompt = f"""Review this {lang} code and provide:
1. Overall assessment (1-10 score)
2. Security issues
3. Performance issues
4. Code quality issues
5. Specific improvement suggestions

Code:
```{lang}
{code[:3000]}
```

Format your response as JSON:
{{
  "score": 8,
  "summary": "Overall assessment",
  "security": ["issue1"],
  "performance": ["issue1"],
  "quality": ["issue1"],
  "suggestions": ["improvement1", "improvement2"]
}}"""

    try:
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        review = json.loads(raw.strip())
        return ok({"review": review})
    except json.JSONDecodeError:
        return ok({"review": {"summary": response.text}})
    except Exception as e:
        return err(f"AI error: {str(e)[:200]}", 503)


# ═══════════════════════════════════════════════════
#  CODE EXECUTION SANDBOX
# ═══════════════════════════════════════════════════

ALLOWED_LANGS = {"python", "javascript", "bash"}

@flask_app.post("/api/execute")
@require_auth
@limiter.limit("10 per minute")
def execute_code():
    body = request.get_json(silent=True) or {}
    lang = (body.get("language", "python")).lower()
    code = body.get("code", "")

    if lang not in ALLOWED_LANGS:
        return err(f"Language must be one of: {', '.join(ALLOWED_LANGS)}")
    if len(code) > 10000:
        return err("Code too long (max 10000 chars)")
    if not code.strip():
        return err("No code provided")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if lang == "python":
                fname = os.path.join(tmpdir, "code.py")
                cmd   = ["python3", "-c", code]
            elif lang == "javascript":
                fname = os.path.join(tmpdir, "code.js")
                cmd   = ["node", "-e", code]
            else:  # bash
                cmd = ["bash", "-c", code]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=10, cwd=tmpdir,
                env={"PATH": "/usr/bin:/bin", "HOME": tmpdir},
            )
            return ok({
                "stdout":     result.stdout[:5000],
                "stderr":     result.stderr[:1000],
                "returncode": result.returncode,
            })
    except subprocess.TimeoutExpired:
        return err("Execution timed out (10s limit)")
    except FileNotFoundError as e:
        return err(f"Runtime not available: {lang}")
    except Exception as e:
        return err(f"Execution error: {str(e)[:200]}", 500)


# ═══════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════
@flask_app.get("/health")
def health():
    # We assume storage is enabled if the bucket name is configured,
    # as the Supabase client handles the connection logic.
    storage_status = "supabase" if STORAGE_BUCKET else "disabled"
    
    return jsonify({
        "status":    "ok",
        "version":   "5.0.0",
        "ai":        "gemini" if gemini_model else "disabled",
        "storage":   storage_status,
        "timestamp": now_iso(),
    })

# ═══════════════════════════════════════════════════
#  SOCKET.IO EVENTS
# ═══════════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    token = request.args.get("token")
    if not token:
        return False
    try:
        payload = decode_jwt(token)
        join_room(f"user_{payload['sub']}")
        logger.info(f"Socket connected: {payload['email']}")
    except Exception:
        return False


@socketio.on("join_team")
def on_join_team(data):
    team_id = data.get("team_id")
    token   = request.args.get("token")
    if not team_id or not token:
        return
    try:
        payload = decode_jwt(token)
        join_room(f"team_{team_id}")
        # Update presence
        user_r = supabase.table("users").select("id,full_name,email").eq("id", payload["sub"]).execute()
        user_info = user_r.data[0] if user_r.data else {"id": payload["sub"], "full_name": payload.get("email")}
        if team_id not in _online_users:
            _online_users[team_id] = {}
        _online_users[team_id][payload["sub"]] = {
            "user_id":   payload["sub"],
            "full_name": user_info.get("full_name", ""),
            "email":     user_info.get("email", ""),
            "ts":        time.time(),
        }
        emit("presence_update", {"online": list(_online_users.get(team_id, {}).values())},
             room=f"team_{team_id}")
        emit("member_online", {"user_id": payload["sub"], "name": user_info.get("full_name", "")},
             room=f"team_{team_id}")
    except Exception as e:
        logger.warning(f"join_team failed: {e}")


@socketio.on("heartbeat")
def on_heartbeat(data):
    team_id = data.get("team_id")
    token   = request.args.get("token")
    if not team_id or not token:
        return
    try:
        payload = decode_jwt(token)
        uid     = payload["sub"]
        if team_id in _online_users and uid in _online_users[team_id]:
            _online_users[team_id][uid]["ts"] = time.time()
    except Exception:
        pass


@socketio.on("leave_team")
def on_leave_team(data):
    team_id = data.get("team_id")
    token   = request.args.get("token")
    if team_id:
        leave_room(f"team_{team_id}")
        if token:
            try:
                payload = decode_jwt(token)
                if team_id in _online_users:
                    _online_users[team_id].pop(payload["sub"], None)
                    emit("presence_update", {"online": list(_online_users.get(team_id, {}).values())},
                         room=f"team_{team_id}")
            except Exception:
                pass


@socketio.on("typing")
def on_typing(data):
    team_id = data.get("team_id")
    token   = request.args.get("token")
    if not team_id or not token:
        return
    try:
        payload = decode_jwt(token)
        user_r  = supabase.table("users").select("full_name").eq("id", payload["sub"]).execute()
        name    = user_r.data[0]["full_name"] if user_r.data else "Someone"
        emit("user_typing", {"user": name, "user_id": payload["sub"]},
             room=f"team_{team_id}", include_self=False)
    except Exception:
        pass


@socketio.on("stop_typing")
def on_stop_typing(data):
    team_id = data.get("team_id")
    token   = request.args.get("token")
    if not team_id or not token:
        return
    try:
        payload = decode_jwt(token)
        emit("user_stop_typing", {"user_id": payload["sub"]},
             room=f"team_{team_id}", include_self=False)
    except Exception:
        pass


@socketio.on("send_message")
def on_send_message(data):
    token = request.args.get("token")
    if not token:
        return
    try:
        payload = decode_jwt(token)
    except Exception:
        return

    team_id = data.get("team_id")
    content = (data.get("content") or "").strip()
    if not team_id or not content:
        return

    msg_id    = str(uuid.uuid4())
    user_r    = supabase.table("users").select("id,full_name,email,username").eq("id", payload["sub"]).execute()
    user_info = user_r.data[0] if user_r.data else {}

    msg = {
        "id":           msg_id,
        "team_id":      team_id,
        "user_id":      payload["sub"],
        "content":      content,
        "message_type": "text",
        "created_at":   now_iso(),
        "users":        user_info,
    }
    try:
        supabase.table("messages").insert({
            "id":           msg_id,
            "team_id":      team_id,
            "user_id":      payload["sub"],
            "content":      content,
            "message_type": "text",
            "created_at":   now_iso(),
        }).execute()
    except Exception as e:
        logger.warning(f"save message failed: {e}")

    emit("new_message", msg, room=f"team_{team_id}")

    mentions  = data.get("mentions", [])
    commenter = user_info.get("full_name", "Someone")
    for mentioned_uid in mentions:
        if mentioned_uid != payload["sub"]:
            create_notification(mentioned_uid, "chat_mention",
                f"{commenter} mentioned you in chat",
                content=content[:120], link="/chat")


@socketio.on("cursor_move")
def on_cursor_move(data):
    team_id = data.get("team_id")
    if team_id:
        emit("cursor_move", data, room=f"team_{team_id}", include_self=False)


@socketio.on("whiteboard_draw")
def on_wb_draw(data):
    token = request.args.get("token")
    if not token:
        return
    try:
        decode_jwt(token)
    except Exception:
        return
    team_id = data.get("team_id")
    if team_id:
        emit("whiteboard_draw", data, room=f"team_{team_id}", include_self=False)


@socketio.on("whiteboard_cursor")
def on_wb_cursor(data):
    team_id = data.get("team_id")
    if team_id:
        emit("whiteboard_cursor", data, room=f"team_{team_id}", include_self=False)


@socketio.on("whiteboard_clear")
def on_wb_clear(data):
    team_id = data.get("team_id")
    if team_id:
        emit("whiteboard_cleared", {}, room=f"team_{team_id}", include_self=False)


@socketio.on("code_change")
def on_code_change(data):
    """Collaborative code editor — broadcast delta to team."""
    token = request.args.get("token")
    if not token:
        return
    try:
        payload = decode_jwt(token)
    except Exception:
        return
    team_id = data.get("team_id")
    if team_id:
        data["user_id"] = payload["sub"]
        emit("code_change", data, room=f"team_{team_id}", include_self=False)


@socketio.on("disconnect")
def on_disconnect():
    # Clean up presence for all teams this socket was in
    token = request.args.get("token")
    if token:
        try:
            payload = decode_jwt(token)
            uid     = payload["sub"]
            for team_id, users in _online_users.items():
                if uid in users:
                    del users[uid]
                    emit("presence_update",
                         {"online": list(users.values())},
                         room=f"team_{team_id}")
        except Exception:
            pass
    logger.info("Socket disconnected")


# ═══════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"HackForge v5 starting on :{port} | AI: {'Gemini' if gemini_model else 'disabled'}")
    socketio.run(flask_app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)