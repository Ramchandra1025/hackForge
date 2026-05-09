"""HackForge — OTP Service"""

import secrets
import bcrypt
from datetime import datetime, timedelta


class OTPService:

    OTP_EXPIRY_MINUTES = 5
    MAX_ATTEMPTS = 5

    def generate_otp(self) -> tuple[str, str, datetime]:
        """
        Generate secure 6-digit OTP,
        hashed version,
        and expiry timestamp.
        """

        otp = str(secrets.randbelow(900000) + 100000)

        otp_hash = bcrypt.hashpw(
            otp.encode(),
            bcrypt.gensalt()
        ).decode()

        expires_at = datetime.utcnow() + timedelta(
            minutes=self.OTP_EXPIRY_MINUTES
        )

        return otp, otp_hash, expires_at

    def verify_otp(
        self,
        otp_code: str,
        otp_hash: str,
        expires_at: datetime,
        attempt_count: int = 0
    ) -> tuple[bool, str]:

        # Expiry check
        if datetime.utcnow() > expires_at:
            return False, "OTP expired"

        # Attempt limit
        if attempt_count >= self.MAX_ATTEMPTS:
            return False, "Too many attempts"

        try:
            valid = bcrypt.checkpw(
                str(otp_code).strip().encode(),
                otp_hash.encode()
            )

            if not valid:
                return False, "Invalid OTP"

            return True, "OTP verified"

        except Exception:
            return False, "OTP verification failed"