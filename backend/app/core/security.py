"""JWT token creation / validation and password hashing."""

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash password using bcrypt (with fallback to PBKDF2)."""
    try:
        import bcrypt
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
    except (ImportError, AttributeError):
        # Fallback: PBKDF2-SHA256
        import os
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return f"pbkdf2$sha256${salt.hex()}${key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash."""
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ImportError, AttributeError, ValueError):
        # Fallback: PBKDF2
        if not hashed.startswith("pbkdf2$"):
            return False
        try:
            _, algo, salt_hex, key_hex = hashed.split("$")
            salt = bytes.fromhex(salt_hex)
            key = hashlib.pbkdf2_hmac(algo, plain.encode("utf-8"), salt, 100000)
            return key.hex() == key_hex
        except Exception:
            return False


def create_access_token(sub: str, username: str) -> str:
    """Create a JWT with user id as subject."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency — validates JWT and returns user_id."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌"
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌已过期或无效"
        )
