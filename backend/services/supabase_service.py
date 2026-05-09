"""
HackForge — Supabase Service with Schema Safety
Production-grade Supabase client with schema validation
"""
import os
from supabase import create_client, Client
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_service_client: Client = None
_anon_client: Client = None

# ────────────────────────────────────────────────────────────
# SCHEMA DEFINITIONS (prevents invalid field errors)
# ────────────────────────────────────────────────────────────

SCHEMA_FIELDS = {
    "users": {
        "id", "email", "username", "password_hash", "avatar_url", 
        "bio", "github_url", "portfolio_url", "reputation_score",
        "is_verified", "is_active", "created_at", "updated_at"
    },
    "teams": {
        "id", "name", "slug", "description", "owner_id", "created_by",
        "join_code", "max_members", "is_active", "avatar_url", "settings",
        "created_at", "updated_at"
    },
    "memberships": {
        "id", "team_id", "user_id", "role", "is_active",
        "joined_at", "created_at"
    },
    "projects": {
        "id", "team_id", "name", "description", "visibility",
        "created_by", "is_active", "created_at", "updated_at"
    },
    "tasks": {
        "id", "project_id", "title", "description", "status",
        "assignee_id", "created_by", "priority", "due_date",
        "is_active", "created_at", "updated_at"
    },
    "files": {
        "id", "team_id", "project_id", "folder_id", "name",
        "storage_path", "mime_type", "size_bytes", "created_by",
        "is_deleted", "created_at", "updated_at"
    },
    "chat_rooms": {
        "id", "team_id", "name", "description", "type", "is_private",
        "created_by", "is_active", "created_at", "updated_at"
    },
    "messages": {
        "id", "room_id", "user_id", "content", "is_edited",
        "created_at", "updated_at"
    },
    "notifications": {
        "id", "user_id", "type", "title", "message", "data",
        "is_read", "created_at"
    },
    "team_invites": {
        "id", "team_id", "email", "role", "token", "invited_by",
        "is_used", "expires_at", "created_at"
    },
    "presence": {
        "id", "user_id", "status", "last_seen", "updated_at"
    }
}


def filter_fields(table: str, data: dict) -> dict:
    """
    Remove invalid fields before insert/update.
    Prevents PGRST204 schema cache errors.
    """
    if table not in SCHEMA_FIELDS:
        return data
    
    allowed = SCHEMA_FIELDS[table]
    return {k: v for k, v in data.items() if k in allowed}


def get_supabase_service() -> Client:
    """
    Admin client with service role key (bypasses RLS).
    Use only for privileged operations.
    """
    global _service_client
    if _service_client is None:
        url = os.getenv("SUPABASE_URL")
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
        )
        if not url or not key:
            logger.warning("Supabase service client not configured")
            return None
        _service_client = create_client(url, key)
        logger.info("Supabase service client initialized")
    return _service_client


def get_supabase_anon() -> Client:
    """
    Public client with anon key (RLS enforced).
    Use for all user-facing operations.
    """
    global _anon_client
    if _anon_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            logger.warning("Supabase anon client not configured")
            return None
        _anon_client = create_client(url, key)
        logger.info("Supabase anon client initialized")
    return _anon_client


def get_supabase() -> Client:
    """Get service client (admin)."""
    return get_supabase_service()