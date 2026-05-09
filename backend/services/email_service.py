"""HackForge — Email Service (EmailJS + SMTP fallback FIXED & STABLE)"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# =========================
# CONFIG
# =========================

EMAILJS_URL = "https://api.emailjs.com/api/v1.0/email/send"

SERVICE_ID = os.getenv("EMAILJS_SERVICE_ID", "")
TEMPLATE_OTP_ID = os.getenv("EMAILJS_TEMPLATE_ID", "")
TEMPLATE_RESET_ID = os.getenv("EMAILJS_RESET_TEMPLATE_ID", "")
TEMPLATE_INVITE_ID = os.getenv("EMAILJS_INVITE_TEMPLATE_ID", "")

PUBLIC_KEY = os.getenv("EMAILJS_PUBLIC_KEY", "")
PRIVATE_KEY = os.getenv("EMAILJS_PRIVATE_KEY", "")

APP_NAME = os.getenv("APP_NAME", "HackForge Workspace")
APP_URL = os.getenv("APP_URL", "http://localhost:5000")

# SMTP fallback
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

EMAIL_FROM = os.getenv("EMAIL_FROM_EMAIL", SMTP_USERNAME)
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", APP_NAME)


# =========================
# CLASS
# =========================

class EmailService:

    # -------------------------
    # SMTP CHECK
    # -------------------------
    def _smtp_ready(self) -> bool:
        return all([SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD])

    # -------------------------
    # SMTP FALLBACK
    # -------------------------
    def _send_smtp(self, to_email: str, subject: str, text: str, html: str) -> bool:
        if not self._smtp_ready():
            logger.error("SMTP not configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
            msg["To"] = to_email

            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))

            context = ssl.create_default_context()

            if SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context)
            else:
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
                if SMTP_USE_TLS:
                    server.starttls(context=context)

            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
            server.quit()

            logger.info(f"SMTP email sent -> {to_email}")
            return True

        except Exception as e:
            logger.error(f"SMTP failed: {e}")
            return False

    # -------------------------
    # EMAILJS SEND (FIXED)
    # -------------------------
    def _send_emailjs(self, template_id: str, params: dict) -> bool:

        # strict validation
        missing = []
        if not SERVICE_ID:
            missing.append("EMAILJS_SERVICE_ID")
        if not template_id:
            missing.append("EMAILJS_TEMPLATE_ID")
        if not PUBLIC_KEY:
            missing.append("EMAILJS_PUBLIC_KEY")

        if missing:
            logger.error(f"EmailJS misconfigured: {missing}")
            return False

        payload = {
            "service_id": SERVICE_ID,
            "template_id": template_id,
            "user_id": PUBLIC_KEY,
            "template_params": params
        }

        if PRIVATE_KEY:
            payload["accessToken"] = PRIVATE_KEY

        try:
            logger.info("Sending EmailJS request...")

            resp = requests.post(
                EMAILJS_URL,
                json=payload,
                timeout=10
            )

            # FIXED: no Unicode arrow
            logger.info(f"EmailJS response -> {resp.status_code} | {resp.text}")

            if resp.status_code not in (200, 201, 204):
                logger.error("EmailJS failed response")
                return False

            return True

        except Exception as e:
            logger.error(f"EmailJS request exception: {e}")
            return False

    # -------------------------
    # OTP EMAIL
    # -------------------------
    def send_otp(self, to_email: str, to_name: str, otp: str, purpose: str = "signup") -> bool:

        params = {
            "to_email": to_email,
            "to_name": to_name,
            "otp": otp,
            "app_name": APP_NAME,
            "expiry_minutes": "5",
            "app_url": APP_URL,
            "purpose": purpose
        }

        # try EmailJS first
        if self._send_emailjs(TEMPLATE_OTP_ID, params):
            return True

        logger.error("EmailJS failed -> trying SMTP fallback")

        subject = f"{APP_NAME} Verification Code"

        text = f"""
Hello {to_name},

Your OTP is: {otp}

This code expires in 5 minutes.
"""

        html = f"""
        <div style="font-family:Arial">
            <h2>{APP_NAME}</h2>
            <p>Hello {to_name},</p>
            <h1>{otp}</h1>
            <p>Expires in 5 minutes</p>
        </div>
        """

        smtp_result = self._send_smtp(to_email, subject, text, html)

        if not smtp_result:
            logger.error("Both EmailJS and SMTP failed")
            return False

        return True

    # -------------------------
    # PASSWORD RESET
    # -------------------------
    def send_password_reset_otp(self, to_email: str, to_name: str, otp: str) -> bool:

        params = {
            "to_email": to_email,
            "to_name": to_name,
            "otp": otp,
            "app_name": APP_NAME
        }

        if self._send_emailjs(TEMPLATE_RESET_ID or TEMPLATE_OTP_ID, params):
            return True

        return self._send_smtp(
            to_email,
            f"{APP_NAME} Password Reset Code",
            f"OTP: {otp}",
            f"<h1>{otp}</h1>"
        )

    # -------------------------
    # TEAM INVITE
    # -------------------------
    def send_team_invite(self, to_email: str, inviter_name: str, team_name: str, invite_code: str) -> bool:

        params = {
            "to_email": to_email,
            "inviter_name": inviter_name,
            "team_name": team_name,
            "invite_code": invite_code,
            "join_url": f"{APP_URL}/join/{invite_code}",
            "app_name": APP_NAME
        }

        return self._send_emailjs(TEMPLATE_INVITE_ID or TEMPLATE_OTP_ID, params)

    # -------------------------
    # NOTIFICATIONS
    # -------------------------
    def send_notification(self, to_email: str, to_name: str, subject: str, message: str) -> bool:

        params = {
            "to_email": to_email,
            "to_name": to_name,
            "subject": subject,
            "message": message,
            "app_name": APP_NAME
        }

        return self._send_emailjs(TEMPLATE_OTP_ID, params)