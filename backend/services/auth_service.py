"""
HackForge — Authentication Service
Full auth lifecycle: signup, OTP, login, session, password reset
"""

import bcrypt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from backend.services.supabase_service import get_supabase
from backend.services.jwt_service import JWTService
from backend.services.otp_service import OTPService
from backend.services.email_service import EmailService
from backend.utils.logger import get_logger
from backend.utils.helpers import generate_username_from_email, generate_avatar_url
from backend.utils.constants import (
    MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES,
    SESSION_EXPIRY_DAYS, PASSWORD_MIN, PASSWORD_MAX
)

logger = get_logger(__name__)


class AuthService:

    def __init__(self):
        self.supabase = get_supabase()
        self.jwt = JWTService()
        self.otp = OTPService()
        self.email = EmailService()

    # ──────────────────────────────────────────
    # SIGNUP
    # ──────────────────────────────────────────

    def initiate_signup(self, email: str, username: str, password: str,
                        full_name: str, ip_address: str) -> Dict[str, Any]:
        """Step 1: Validate, store pending user, send OTP."""
        email = email.lower().strip()
        username = username.lower().strip()

        # Check existing
        existing = self.supabase.table("users").select("id").eq("email", email).execute()
        if existing.data:
            raise ValueError("Email already registered")

        existing_u = self.supabase.table("users").select("id").eq("username", username).execute()
        if existing_u.data:
            raise ValueError("Username already taken")

        # Hash password
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        # Generate OTP
        otp_code, otp_hash = self.otp.generate_otp()

        # Store pending user
        pending = {
            "email": email,
            "username": username,
            "full_name": full_name,
            "password_hash": pw_hash,
            "otp_hash": otp_hash,
            "otp_expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "attempt_count": 0,
            "ip_address": ip_address,
            "created_at": datetime.utcnow().isoformat()
        }

        # Upsert pending (replace if same email)
        self.supabase.table("pending_users").upsert(pending, on_conflict="email").execute()

        # Send OTP email
        self.email.send_otp(email, full_name, otp_code)

        logger.info(f"Signup initiated for {email}")
        return {"message": "OTP sent to email", "email": email}

    def verify_signup_otp(self, email: str, otp_code: str, ip_address: str,
                          user_agent: str) -> Dict[str, Any]:
        """Step 2: Verify OTP and create user account."""
        email = email.lower().strip()

        pending = self.supabase.table("pending_users").select("*").eq("email", email).execute()
        if not pending.data:
            raise ValueError("No pending signup found for this email")

        p = pending.data[0]

        # Check expiry
        expires = datetime.fromisoformat(p["otp_expires_at"].replace("Z", "+00:00").replace("+00:00", ""))
        if datetime.utcnow() > expires:
            raise ValueError("OTP has expired. Please request a new one")

        # Check attempt count
        if p["attempt_count"] >= 5:
            raise ValueError("Too many failed attempts. Please restart signup")

        # Verify OTP
        if not self.otp.verify_otp(otp_code, p["otp_hash"]):
            # Increment attempts
            self.supabase.table("pending_users").update(
                {"attempt_count": p["attempt_count"] + 1}
            ).eq("email", email).execute()
            raise ValueError("Invalid OTP code")

        # Create user
        avatar_url = generate_avatar_url(p["email"])
        user_data = {
            "email": p["email"],
            "username": p["username"],
            "full_name": p["full_name"],
            "password_hash": p["password_hash"],
            "avatar_url": avatar_url,
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "reputation_score": 0,
            "created_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }

        result = self.supabase.table("users").insert(user_data).execute()
        if not result.data:
            raise RuntimeError("Failed to create user account")

        user = result.data[0]

        # Delete pending
        self.supabase.table("pending_users").delete().eq("email", email).execute()

        # Create session
        tokens = self._create_session(user, ip_address, user_agent)

        logger.info(f"User created: {email} (id={user['id']})")
        return {
            "user": self._sanitize_user(user),
            "tokens": tokens
        }

    def resend_signup_otp(self, email: str) -> Dict[str, Any]:
        """Resend OTP with cooldown check."""
        email = email.lower().strip()

        pending = self.supabase.table("pending_users").select("*").eq("email", email).execute()
        if not pending.data:
            raise ValueError("No pending signup for this email")

        p = pending.data[0]

        # Cooldown check: 60 seconds
        updated_at = p.get("otp_resent_at") or p.get("created_at")
        if updated_at:
            last = datetime.fromisoformat(str(updated_at).replace("Z", ""))
            if (datetime.utcnow() - last).total_seconds() < 60:
                raise ValueError("Please wait 60 seconds before resending OTP")

        otp_code, otp_hash = self.otp.generate_otp()

        self.supabase.table("pending_users").update({
            "otp_hash": otp_hash,
            "otp_expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "attempt_count": 0,
            "otp_resent_at": datetime.utcnow().isoformat()
        }).eq("email", email).execute()

        self.email.send_otp(email, p["full_name"], otp_code)
        return {"message": "OTP resent"}

    # ──────────────────────────────────────────
    # LOGIN
    # ──────────────────────────────────────────

    def login(self, identifier: str, password: str,
              ip_address: str, user_agent: str) -> Dict[str, Any]:
        """Login with email or username."""
        identifier = identifier.lower().strip()

        # Find user by email or username
        result = self.supabase.table("users").select("*").or_(
            f"email.eq.{identifier},username.eq.{identifier}"
        ).execute()

        if not result.data:
            raise ValueError("Invalid credentials")

        user = result.data[0]

        if not user.get("is_active"):
            raise ValueError("Account is disabled. Contact support")

        if not user.get("is_verified"):
            raise ValueError("Email not verified")

        # Check lockout
        if user.get("locked_until"):
            locked = datetime.fromisoformat(str(user["locked_until"]).replace("Z", ""))
            if datetime.utcnow() < locked:
                remaining = int((locked - datetime.utcnow()).total_seconds() / 60)
                raise ValueError(f"Account locked. Try again in {remaining} minutes")

        # Verify password
        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            # Track failed attempts
            attempts = (user.get("failed_login_attempts") or 0) + 1
            update_data = {"failed_login_attempts": attempts}

            if attempts >= MAX_LOGIN_ATTEMPTS:
                update_data["locked_until"] = (
                    datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                ).isoformat()
                update_data["failed_login_attempts"] = 0

            self.supabase.table("users").update(update_data).eq("id", user["id"]).execute()
            raise ValueError("Invalid credentials")

        # Reset failed attempts
        self.supabase.table("users").update({
            "failed_login_attempts": 0,
            "locked_until": None,
            "last_seen": datetime.utcnow().isoformat()
        }).eq("id", user["id"]).execute()

        # Create session
        tokens = self._create_session(user, ip_address, user_agent)

        # Audit log
        self._log_login(user["id"], ip_address, user_agent, "login_success")

        logger.info(f"Login success: {identifier}")
        return {
            "user": self._sanitize_user(user),
            "tokens": tokens
        }

    # ──────────────────────────────────────────
    # PASSWORD RESET
    # ──────────────────────────────────────────

    def initiate_password_reset(self, email: str) -> Dict[str, Any]:
        """Send OTP for password reset."""
        email = email.lower().strip()

        result = self.supabase.table("users").select("id,full_name,email").eq("email", email).execute()
        if not result.data:
            # Don't leak whether email exists
            return {"message": "If that email exists, a reset OTP has been sent"}

        user = result.data[0]
        otp_code, otp_hash = self.otp.generate_otp()

        self.supabase.table("password_resets").upsert({
            "user_id": user["id"],
            "email": email,
            "otp_hash": otp_hash,
            "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "used": False,
            "created_at": datetime.utcnow().isoformat()
        }, on_conflict="email").execute()

        self.email.send_password_reset_otp(email, user["full_name"], otp_code)
        return {"message": "If that email exists, a reset OTP has been sent"}

    def verify_reset_otp(self, email: str, otp_code: str) -> str:
        """Verify reset OTP, return reset token."""
        email = email.lower().strip()

        result = self.supabase.table("password_resets").select("*").eq("email", email).eq("used", False).execute()
        if not result.data:
            raise ValueError("Invalid or expired reset request")

        r = result.data[0]
        expires = datetime.fromisoformat(str(r["expires_at"]).replace("Z", ""))
        if datetime.utcnow() > expires:
            raise ValueError("OTP has expired")

        if not self.otp.verify_otp(otp_code, r["otp_hash"]):
            raise ValueError("Invalid OTP")

        # Generate short-lived reset token
        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

        self.supabase.table("password_resets").update({
            "reset_token_hash": reset_token_hash,
            "token_expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }).eq("email", email).execute()

        return reset_token

    def complete_password_reset(self, email: str, reset_token: str, new_password: str) -> Dict[str, Any]:
        """Set new password using reset token."""
        email = email.lower().strip()
        reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

        result = self.supabase.table("password_resets").select("*").eq("email", email).eq("used", False).execute()
        if not result.data:
            raise ValueError("Invalid reset request")

        r = result.data[0]
        if r.get("reset_token_hash") != reset_token_hash:
            raise ValueError("Invalid reset token")

        token_exp = datetime.fromisoformat(str(r["token_expires_at"]).replace("Z", ""))
        if datetime.utcnow() > token_exp:
            raise ValueError("Reset token expired")

        pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()

        self.supabase.table("users").update({
            "password_hash": pw_hash,
            "failed_login_attempts": 0,
            "locked_until": None
        }).eq("id", r["user_id"]).execute()

        self.supabase.table("password_resets").update({"used": True}).eq("email", email).execute()

        # Invalidate all sessions
        self.supabase.table("login_sessions").update({"is_active": False}).eq("user_id", r["user_id"]).execute()

        return {"message": "Password reset successful"}

    # ──────────────────────────────────────────
    # SESSION
    # ──────────────────────────────────────────

    def _create_session(self, user: Dict, ip_address: str, user_agent: str) -> Dict[str, str]:
        access_token = self.jwt.create_access_token(user)
        refresh_token = self.jwt.create_refresh_token(user["id"])

        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        self.supabase.table("login_sessions").insert({
            "user_id": user["id"],
            "refresh_token_hash": refresh_hash,
            "ip_address": ip_address,
            "user_agent": user_agent[:500],
            "is_active": True,
            "expires_at": (datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat()
        }).execute()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    def refresh_tokens(self, refresh_token: str, ip_address: str, user_agent: str) -> Dict[str, str]:
        """Rotate refresh token."""
        user_id = self.jwt.verify_refresh_token(refresh_token)
        if not user_id:
            raise ValueError("Invalid refresh token")

        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        session = self.supabase.table("login_sessions").select("*").eq(
            "refresh_token_hash", refresh_hash
        ).eq("is_active", True).execute()

        if not session.data:
            raise ValueError("Session not found or expired")

        # Invalidate old session
        self.supabase.table("login_sessions").update({"is_active": False}).eq(
            "refresh_token_hash", refresh_hash
        ).execute()

        user_result = self.supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_result.data:
            raise ValueError("User not found")

        tokens = self._create_session(user_result.data[0], ip_address, user_agent)
        return tokens

    def logout(self, user_id: str, refresh_token: Optional[str] = None) -> None:
        """Logout single session or all sessions."""
        if refresh_token:
            refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            self.supabase.table("login_sessions").update({"is_active": False}).eq(
                "refresh_token_hash", refresh_hash
            ).execute()
        else:
            # Logout all
            self.supabase.table("login_sessions").update({"is_active": False}).eq(
                "user_id", user_id
            ).execute()

    def logout_all_devices(self, user_id: str) -> Dict[str, Any]:
        self.supabase.table("login_sessions").update({"is_active": False}).eq(
            "user_id", user_id
        ).execute()
        return {"message": "Logged out from all devices"}

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _sanitize_user(self, user: Dict) -> Dict:
        return {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "role": user.get("role", "user"),
            "is_verified": user.get("is_verified"),
            "reputation_score": user.get("reputation_score", 0),
            "created_at": str(user.get("created_at")),
            "last_seen": str(user.get("last_seen"))
        }

    def _log_login(self, user_id: str, ip: str, ua: str, event: str):
        try:
            self.supabase.table("audit_logs").insert({
                "user_id": user_id,
                "action": event,
                "resource_type": "auth",
                "metadata": {"ip": ip, "user_agent": ua[:200]},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Audit log failed: {e}")

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        result = self.supabase.table("users").select("*").eq("id", user_id).execute()
        if result.data:
            return self._sanitize_user(result.data[0])
        return None

    def get_active_sessions(self, user_id: str) -> list:
        result = self.supabase.table("login_sessions").select(
            "id,ip_address,user_agent,created_at,last_used"
        ).eq("user_id", user_id).eq("is_active", True).order("last_used", desc=True).execute()
        return result.data or []