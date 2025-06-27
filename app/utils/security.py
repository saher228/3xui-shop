import hashlib
import hmac
import base64
from typing import Optional

class SecurityHelper:
    @staticmethod
    def generate_hmac(key: str, message: str) -> str:
        """Generate HMAC-SHA256 signature for the message using the key."""
        hmac_obj = hmac.new(
            key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(hmac_obj.digest()).decode('utf-8')

    @staticmethod
    def verify_hmac(key: str, message: str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature for the message."""
        expected_signature = SecurityHelper.generate_hmac(key, message)
        return hmac.compare_digest(expected_signature, signature)

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash password with salt using SHA-256."""
        if salt is None:
            salt = base64.b64encode(hashlib.sha256(password.encode()).digest()).decode('utf-8')
        
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt

    @staticmethod
    def verify_password(password: str, hashed_password: str, salt: str) -> bool:
        """Verify password against hashed password and salt."""
        new_hash, _ = SecurityHelper.hash_password(password, salt)
        return hmac.compare_digest(new_hash, hashed_password) 