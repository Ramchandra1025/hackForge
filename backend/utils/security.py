"""
HackForge - SECURITY MODULE (CLEAN + FIXED + STABLE)
"""

import os
import jwt
import bcrypt
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g, current_app

from backend.utils.db import get_db
from backend.utils.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

# -------------------------
# ROLE PERMISSIONS
# -------------------------
ROLE_PERMISSIONS = {
    "owner": ["*"],
    "admin": ["read", "write", "delete", "invite", "manage_tasks", "deploy", "manage_chat"],
    "developer": ["read", "write", "manage_tasks", "deploy", "manage_chat"],
    "designer": ["read", "write", "manage_tasks", "manage_chat"],
    "viewer": ["read"],
    "judge": ["read", "judge_score"],
}

# -------------------------
# SECURITY HEADERS
# -------------------------
def configure_security(app):
    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if not app.config.get("DEBUG"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# -------------------------
# PASSWORD SECURITY (FIXED)
# -------------------------
def hash_password(password: str) -> str:
    """Proper bcrypt hashing (ONLY ONE VERSION)"""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Proper bcrypt verification"""
    try:
        if not hashed:
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"bcrypt error: {e}")
        return False


# -------------------------
# OTP SYSTEM
# -------------------------
def generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp(otp: str, hashed: str) -> bool:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest() == hashed


# -------------------------
# TOKENS
# -------------------------
def generate_token(length=32):
    return secrets.token_urlsafe(length)


def create_jwt(user_id: str, session_id: str = None) -> str:
    payload = {
        "sub": user_id,
        "sid": session_id or generate_token(16),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
    }

    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm="HS256"
    )


def decode_jwt(token: str):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=["HS256"]
    )


# -------------------------
# COOKIE HANDLING
# -------------------------
def set_auth_cookie(response, token: str):
    response.set_cookie(
        "hackforge_token",
        token,
        httponly=True,
        secure=False,  # localhost fix
        samesite="Lax",
        max_age=86400,
    )
    return response


def clear_auth_cookie(response):
    response.set_cookie("hackforge_token", "", max_age=0)
    return response


# -------------------------
# TOKEN EXTRACTION
# -------------------------
def get_token():
    token = request.cookies.get("hackforge_token")

    if token:
        return token

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    return None


# -------------------------
# CURRENT USER
# -------------------------
def get_current_user():
    token = get_token()
    if not token:
        return None

    try:
        payload = decode_jwt(token)
        user_id = payload.get("sub")

        if not user_id:
            return None

        cache_key = f"user:{user_id}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        db = get_db()
        result = db.table("users").select("*").eq("id", user_id).single().execute()

        if not result.data:
            return None

        cache_set(cache_key, result.data, 300)
        return result.data

    except Exception as e:
        logger.debug(f"Auth error: {e}")
        return None


# -------------------------
# AUTH DECORATOR
# -------------------------
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        g.user = user
        return f(*args, **kwargs)

    return wrapper


# -------------------------
# TEAM MEMBERSHIP (FIXED)
# -------------------------
def get_membership(user_id: str, team_id: str):
    try:
        db = get_db()

        result = db.table("memberships") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("team_id", team_id) \
            .eq("is_active", True) \
            .single() \
            .execute()

        return result.data

    except Exception as e:
        logger.debug(f"membership error: {e}")
        return None


def require_team_member(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401

            team_id = kwargs.get("team_id") or (request.json or {}).get("team_id")
            if not team_id:
                return jsonify({"error": "Team ID required"}), 400

            membership = get_membership(user["id"], team_id)
            if not membership:
                return jsonify({"error": "Not a team member"}), 403

            g.user = user
            g.membership = membership

            return f(*args, **kwargs)

        return wrapper
    return decorator


# -------------------------
# PERMISSIONS
# -------------------------
def has_permission(role, permission):
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not hasattr(g, "membership"):
                return jsonify({"error": "No membership"}), 403

            if not has_permission(g.membership["role"], permission):
                return jsonify({"error": "Permission denied"}), 403

            return f(*args, **kwargs)

        return wrapper
    return decorator


# -------------------------
# AUDIT LOG
# -------------------------
def audit_log(user_id, action, resource_type=None, resource_id=None, team_id=None):
    try:
        db = get_db()

        db.table("audit_logs").insert({
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "team_id": team_id,
            "ip_address": request.remote_addr if request else None,
            "user_agent": request.headers.get("User-Agent") if request else None,
        }).execute()

    except Exception as e:
        logger.error(f"audit log error: {e}")