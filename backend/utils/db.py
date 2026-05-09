"""
Database utilities with schema safety
"""
from backend.services.supabase_service import (
    get_supabase_service, get_supabase_anon, filter_fields
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def init_db(app):
    """Initialize database connection and verify schema"""
    try:
        db = get_supabase_service()
        if not db:
            logger.warning("Supabase client not available during init; skipping verification")
            app.supabase = None
            return False

        db.table('users').select('id').limit(1).execute()
        logger.info("Database connection verified. Users table accessible.")

        app.supabase = db
        return True
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
        logger.info("Database will be initialized on first use")
        return False


def get_db():
    """Get service client (admin access)."""
    from flask import current_app
    if hasattr(current_app, 'supabase') and current_app.supabase:
        return current_app.supabase
    return get_supabase_service()


def get_db_anon():
    """Get anon client (RLS enforced)."""
    from flask import current_app
    return get_supabase_anon()


def safe_insert(db, table: str, data: dict):
    """Insert with schema validation."""
    filtered = filter_fields(table, data)
    return db.table(table).insert(filtered).execute()


def safe_update(db, table: str, data: dict):
    """Update with schema validation."""
    filtered = filter_fields(table, data)
    return db.table(table).update(filtered)


def safe_upsert(db, table: str, data: dict):
    """Upsert with schema validation."""
    filtered = filter_fields(table, data)
    return db.table(table).upsert(filtered).execute()

