"""
HackForge - AUTH ROUTES (Production - Schema Safe)
"""

import logging
import json
from flask import Blueprint, request, make_response
from datetime import datetime, timezone, timedelta

from backend.utils.db import get_db, safe_insert
from backend.services.supabase_service import filter_fields
from backend.services.email_service import EmailService
from backend.utils.security import (
    hash_password, verify_password, hash_otp, verify_otp,
    generate_otp, generate_token, create_jwt, set_auth_cookie
)
from backend.utils.error_handlers import success, error, validate_required
from backend.utils.redis_client import get_redis

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

email_service = EmailService()


def cache_set_json(redis, key, value, ttl):
    """Set JSON value in Redis."""
    redis.setex(key, ttl, json.dumps(value))


def cache_get_json(redis, key):
    """Get JSON value from Redis."""
    data = redis.get(key)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def cache_delete_key(redis, key):
    """Delete key from Redis."""
    redis.delete(key)


def send_otp_email(email: str, otp: str):
    """Send OTP via email."""
    try:
        email_service.send_otp(email, "HackForge Workspace", otp)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


@auth_bp.route("/signup/initiate", methods=["POST"])
def signup_initiate():
    """Initiate signup with email OTP."""
    data = request.get_json()

    valid, msg = validate_required(data, ["email", "username", "password"])
    if not valid:
        return error(msg, 400)

    email = data["email"].lower().strip()
    username = data["username"].lower().strip()
    password = data["password"]

    db = get_db()
    redis = get_redis()

    try:
        existing = db.table("users").select("id").eq("email", email).execute().data
        if existing:
            return error("Email already registered", 409)

        if redis.get(f"cooldown:{email}"):
            return error("Please wait before requesting another OTP", 429)

        otp = generate_otp()
        otp_hash = hash_otp(otp)

        cache_set_json(redis, f"pending:{email}", {
            "email": email,
            "username": username,
            "password_hash": hash_password(password)
        }, ttl=3600)

        cache_set_json(redis, f"otp:{email}", {
            "otp_hash": otp_hash,
            "expires": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        }, ttl=300)

        if not send_otp_email(email, otp):
            return error("Failed to send OTP email", 500)

        redis.setex(f"cooldown:{email}", 60, "1")

        return success({"email": email}, "OTP sent successfully")

    except Exception as e:
        logger.error(f"Signup initiate error: {e}")
        return error("Signup failed", 500)


@auth_bp.route("/signup/verify", methods=["POST"])
def signup_verify():
    """Verify OTP and create user account."""
    data = request.get_json()

    valid, msg = validate_required(data, ["email", "otp"])
    if not valid:
        return error(msg, 400)

    email = data["email"].lower().strip()
    otp = data["otp"].strip()

    db = get_db()
    redis = get_redis()

    try:
        otp_data = cache_get_json(redis, f"otp:{email}")
        if not otp_data:
            return error("OTP expired or not found", 400)

        if not verify_otp(otp, otp_data["otp_hash"]):
            return error("Invalid OTP", 400)

        cache_delete_key(redis, f"otp:{email}")

        pending = cache_get_json(redis, f"pending:{email}")
        if not pending:
            return error("Signup session expired", 400)

        cache_delete_key(redis, f"pending:{email}")

        user_data = {
            "email": email,
            "username": pending["username"],
            "password_hash": pending["password_hash"],
            "is_verified": True,
            "is_active": True
        }

        filtered = filter_fields("users", user_data)
        result = db.table("users").insert(filtered).execute()

        if not result.data:
            return error("User creation failed", 500)

        user = result.data[0]
        token = create_jwt(user["id"], generate_token(16))
        response = make_response(success({"user": user}, "Account created"))

        return set_auth_cookie(response, token)

    except Exception as e:
        logger.error(f"Signup verify error: {e}")
        return error("Verification failed", 500)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """Resend OTP to email."""
    data = request.get_json()
    email = (data.get("email") or "").lower().strip()

    if not email:
        return error("Email required", 400)

    redis = get_redis()

    try:
        if redis.get(f"cooldown:{email}"):
            return error("Please wait before retrying", 429)

        otp = generate_otp()
        otp_hash = hash_otp(otp)

        cache_set_json(redis, f"otp:{email}", {
            "otp_hash": otp_hash,
            "expires": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        }, ttl=300)

        send_otp_email(email, otp)
        redis.setex(f"cooldown:{email}", 60, "1")

        return success({"email": email}, "OTP resent")

    except Exception as e:
        logger.error(f"Resend OTP error: {e}")
        return error("Resend failed", 500)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login with email/username and password."""
    try:
        data = request.get_json()

        if not data:
            return error("No JSON data", 400)

        identifier = (data.get("identifier") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not identifier or not password:
            return error("Missing credentials", 400)

        db = get_db()

        query = db.table("users").select("*")

        if "@" in identifier:
            result = query.eq("email", identifier).execute()
        else:
            result = query.eq("username", identifier).execute()

        if not result.data:
            return error("Invalid credentials", 401)

        user = result.data[0]

        if not verify_password(password, user["password_hash"]):
            return error("Invalid credentials", 401)

        token = create_jwt(user["id"], generate_token(16))

        response = make_response(success({
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"]
            }
        }, "Login successful"))

        return set_auth_cookie(response, token)

    except Exception as e:
        logger.error(f"Login error: {e}")
        return error("Login failed", 500)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout user by clearing auth cookie."""
    try:
        response = make_response(success(message="Logout successful"))
        response.delete_cookie("hackforge_token", path="/")
        return response
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return error("Logout failed", 500)


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """Get current authenticated user info."""
    try:
        from flask import g
        if not hasattr(g, 'user') or not g.user:
            return error("Not authenticated", 401)

        return success({"user": g.user})
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        return error("Failed to get user", 500)