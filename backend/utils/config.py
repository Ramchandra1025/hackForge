"""HackForge application configuration helpers."""

import os


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_app_config(app):
    """Populate Flask config with safe defaults from environment."""
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "hackforge-dev-secret-change-in-production"))
    app.config.setdefault("JWT_SECRET", os.getenv("JWT_SECRET", "hackforge-jwt-secret-change-in-production"))
    app.config.setdefault("MAX_UPLOAD_SIZE_MB", int(os.getenv("MAX_UPLOAD_SIZE_MB", 100)))
    app.config.setdefault("REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    app.config.setdefault("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
    app.config.setdefault("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SERVICE_KEY", ""))
    app.config.setdefault("DEBUG", _as_bool(os.getenv("FLASK_DEBUG", "false")))
    return app
