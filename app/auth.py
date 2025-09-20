import base64
import hashlib
import hmac
import json
from typing import Optional

from .config import SECRET_KEY


class PasswordHasher:
    iterations = 200_000

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, cls.iterations
        )
        return base64.b64encode(hash_bytes).decode("ascii")

    @classmethod
    def verify_password(cls, password: str, stored: str) -> bool:
        expected = cls.hash_password(password)
        return hmac.compare_digest(expected, stored)


class SessionManager:
    cookie_name = "dndtable_session"

    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8")

    def _sign(self, data: bytes) -> str:
        signature = hmac.new(self.secret, data, hashlib.sha256).hexdigest()
        return signature

    def serialize(self, payload: dict) -> str:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        token = base64.urlsafe_b64encode(data).decode("ascii")
        signature = self._sign(token.encode("ascii"))
        return f"{token}.{signature}"

    def deserialize(self, token: str) -> Optional[dict]:
        if not token or "." not in token:
            return None
        data_part, signature = token.split(".", 1)
        expected_signature = self._sign(data_part.encode("ascii"))
        if not hmac.compare_digest(signature, expected_signature):
            return None
        try:
            data_bytes = base64.urlsafe_b64decode(data_part.encode("ascii"))
            return json.loads(data_bytes.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None

    def load_from_headers(self, headers: dict) -> Optional[dict]:
        cookie = headers.get("HTTP_COOKIE", "")
        for part in cookie.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == self.cookie_name:
                return self.deserialize(value)
        return None


session_manager = SessionManager(SECRET_KEY)
