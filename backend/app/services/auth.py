import base64
import hashlib
import hmac
import os
import re
import hashlib
import time
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import settings
from app.database import transactional_db

PASSWORD_ITERATIONS = 310_000
SESSION_TTL_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "$".join(
        (
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        iterations, salt_text, digest_text = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _session_secret() -> bytes:
    secret = settings.APP_SECRET_KEY
    if not secret:
        if settings.APP_ENV.lower() == "production":
            raise RuntimeError("APP_SECRET_KEY is required in production.")
        secret = "local-development-session-key-change-before-deployment"
    return secret.encode("utf-8")


def create_session_token(user_id: int, now: int | None = None) -> str:
    expires_at = (now or int(time.time())) + SESSION_TTL_SECONDS
    payload = f"{user_id}.{expires_at}"
    signature = hmac.new(_session_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def read_session_user_id(token: str, now: int | None = None) -> int | None:
    try:
        user_id_text, expires_text, supplied_signature = token.split(".", 2)
        payload = f"{user_id_text}.{expires_text}"
        expected_signature = hmac.new(
            _session_secret(), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        if int(expires_text) < (now or int(time.time())):
            return None
        return int(user_id_text)
    except (ValueError, TypeError):
        return None


def bootstrap_owner() -> None:
    email = settings.BOOTSTRAP_ADMIN_EMAIL
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not email and not password:
        if settings.APP_ENV.lower() == "production":
            with transactional_db() as conn:
                owner_count = conn.execute(
                    "SELECT COUNT(*) AS count FROM users WHERE role = 'owner' AND status = 'ACTIVE'"
                ).fetchone()["count"]
            if owner_count == 0:
                raise RuntimeError(
                    "Configure bootstrap owner credentials before starting a production database without an owner."
                )
        return
    if not email or len(password) < 12:
        raise RuntimeError("Set both bootstrap owner email and a password of at least 12 characters.")

    with transactional_db() as conn:
        existing = conn.execute("SELECT id, role FROM users WHERE email = ?", (email,)).fetchone()
        owner_exists = conn.execute(
            "SELECT 1 FROM users WHERE role = 'owner' AND status = 'ACTIVE' LIMIT 1"
        ).fetchone()
        if existing:
            if existing["role"] != "owner":
                raise RuntimeError("Bootstrap email is already assigned to a client account.")
            # Never rotate an existing credential from an environment variable on every restart.
        elif owner_exists:
            raise RuntimeError("An active owner already exists; remove bootstrap credentials after initial setup.")
        else:
            conn.execute(
                """INSERT INTO users
                (full_name, email, password_hash, role, status, business_name, vertical)
                VALUES ('Agency Owner', ?, ?, 'owner', 'ACTIVE', 'Agency', 'agency')""",
                (email, password_hash),
            )
        conn.commit()


def get_current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get("ar_session", "")
    user_id = read_session_user_id(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    with transactional_db() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, role, status, business_name, vertical, tenant_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row or row["status"] != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")
    return dict(row)


def require_owner(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if user["role"] != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required.")
    return user


def require_client(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if user["role"] != "client" or not user["tenant_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client workspace required.")
    return user


def normalize_signup_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return normalized


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 900) -> None:
    """Persistent per-key throttle shared by app workers using the same SQLite file."""
    key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    now = int(time.time())
    with transactional_db() as conn:
        row = conn.execute(
            "SELECT failures, window_started_at, blocked_until FROM auth_rate_limits WHERE rate_key = ?",
            (key,),
        ).fetchone()
        if row and row["blocked_until"] > now:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.", headers={"Retry-After": str(row["blocked_until"] - now)})
        if not row or now - row["window_started_at"] >= window_seconds:
            conn.execute(
                "INSERT INTO auth_rate_limits(rate_key, failures, window_started_at, blocked_until) VALUES (?, 0, ?, 0) "
                "ON CONFLICT(rate_key) DO UPDATE SET failures=0, window_started_at=excluded.window_started_at, blocked_until=0",
                (key, now),
            )
            conn.commit()


def record_auth_failure(key: str, limit: int = 10, window_seconds: int = 900) -> None:
    key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    now = int(time.time())
    with transactional_db() as conn:
        row = conn.execute(
            "SELECT failures, window_started_at FROM auth_rate_limits WHERE rate_key = ?", (key,)
        ).fetchone()
        failures = 1 if not row or now - row["window_started_at"] >= window_seconds else row["failures"] + 1
        started = now if not row or now - row["window_started_at"] >= window_seconds else row["window_started_at"]
        blocked = now + window_seconds if failures >= limit else 0
        conn.execute(
            "INSERT INTO auth_rate_limits(rate_key, failures, window_started_at, blocked_until) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(rate_key) DO UPDATE SET failures=excluded.failures, window_started_at=excluded.window_started_at, blocked_until=excluded.blocked_until",
            (key, failures, started, blocked),
        )
        conn.execute("DELETE FROM auth_rate_limits WHERE window_started_at < ?", (now - 86400,))
        conn.commit()


def clear_auth_failures(key: str) -> None:
    key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    with transactional_db() as conn:
        conn.execute("DELETE FROM auth_rate_limits WHERE rate_key = ?", (key,))
        conn.commit()
