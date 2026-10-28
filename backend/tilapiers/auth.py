"""Password hashing and signed session cookies (paper Security module)."""

import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

ITERATIONS = 200_000
COOKIE = "tl_session"
MAX_AGE_S = 12 * 3600
ROLES = ("caretaker", "technician", "admin")


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, stored):
    try:
        _, iters, salt, digest = stored.split("$")
    except (AttributeError, ValueError):
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
    return hmac.compare_digest(test, digest)


class Sessions:
    def __init__(self, secret_key):
        self._s = URLSafeTimedSerializer(secret_key, salt="tilapiers-session")

    def issue(self, user_id):
        return self._s.dumps({"uid": user_id})

    def read(self, token):
        if not token:
            return None
        try:
            return self._s.loads(token, max_age=MAX_AGE_S).get("uid")
        except (BadSignature, SignatureExpired):
            return None
