"""HackForge — Auth Middleware"""
from functools import wraps
from flask import request, jsonify, g
from backend.services.jwt_service import JWTService
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)
jwt_svc = JWTService()


def get_token_from_request() -> str | None:
    """Extract JWT from cookie or Authorization header."""
    # HttpOnly cookie first
    token = request.cookies.get("access_token")
    if token:
        return token

    # Bearer header fallback
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "Authentication required"}), 401

        payload = jwt_svc.verify_access_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Attach user context
        g.user_id = payload["sub"]
        g.user_email = payload.get("email")
        g.user_role = payload.get("role", "user")
        g.user_username = payload.get("username")

        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Auth is optional — sets g.user_id if token exists."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if token:
            payload = jwt_svc.verify_access_token(token)
            if payload:
                g.user_id = payload["sub"]
                g.user_email = payload.get("email")
                g.user_role = payload.get("role", "user")
            else:
                g.user_id = None
        else:
            g.user_id = None
        return f(*args, **kwargs)
    return decorated


def require_verified(f):
    """Require auth + verified account."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "Authentication required"}), 401

        payload = jwt_svc.verify_access_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Check DB for verification status
        supabase = get_supabase()
        user = supabase.table("users").select("id,is_verified,is_active").eq(
            "id", payload["sub"]
        ).execute()

        if not user.data:
            return jsonify({"error": "User not found"}), 401

        u = user.data[0]
        if not u.get("is_active"):
            return jsonify({"error": "Account disabled"}), 403
        if not u.get("is_verified"):
            return jsonify({"error": "Email not verified"}), 403

        g.user_id = payload["sub"]
        g.user_email = payload.get("email")
        g.user_role = payload.get("role", "user")

        return f(*args, **kwargs)
    return decorated