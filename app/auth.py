import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import User

COOKIE_NAME = "session"
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="leftovereat-session")
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def make_session_token(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def read_session_token(token: str) -> int | None:
    try:
        data = _serializer.loads(token, max_age=config.SESSION_MAX_AGE)
        return int(data["uid"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    uid = read_session_token(token)
    return db.get(User, uid) if uid else None


def _redirect(url: str) -> HTTPException:
    return HTTPException(status_code=303, headers={"Location": url})


def require_role(*roles: str):
    def dep(user: User | None = Depends(get_current_user)) -> User:
        if user is None:
            raise _redirect("/login")
        if user.role not in roles:
            raise _redirect("/?msg=That+page+is+for+a+different+account+type")
        return user

    return dep
