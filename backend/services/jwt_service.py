"""HackForge — JWT Service"""
import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from backend.utils.logger import get_logger

logger = get_logger(__name__)

SECRET = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", SECRET + "-refresh")
ACCESS_EXP = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))
REFRESH_EXP = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 2592000))


class JWTService:

    def create_access_token(self, user: Dict[str, Any]) -> str:
        payload = {
            "sub": str(user["id"]),
            "email": user["email"],
            "username": user.get("username"),
            "role": user.get("role", "user"),
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=ACCESS_EXP)
        }
        return jwt.encode(payload, SECRET, algorithm="HS256")

    def create_refresh_token(self, user_id: str) -> str:
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=REFRESH_EXP)
        }
        return jwt.encode(payload, REFRESH_SECRET, algorithm="HS256")

    def verify_access_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Access token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid access token: {e}")
            return None

    def verify_refresh_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, REFRESH_SECRET, algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return None
            return payload["sub"]
        except jwt.InvalidTokenError:
            return None

    def decode_token_unsafe(self, token: str) -> Optional[Dict]:
        """Decode without verifying expiry — for migration/audit purposes only."""
        try:
            return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_exp": False})
        except Exception:
            return None