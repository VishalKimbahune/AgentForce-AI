"""Supabase JWT authentication and token verification utilities."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import jwt
from pydantic import BaseModel
from fastapi import HTTPException, status
from app.core.config import settings


class TokenPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None
    raw_claims: Dict[str, Any] = {}


def get_jwt_secret() -> str:
    """Returns the configured Supabase JWT secret or dev fallback."""
    if settings.SUPABASE_JWT_SECRET:
        return settings.SUPABASE_JWT_SECRET
    return "development-jwt-secret-not-for-production-use"


def create_token(
    sub: str,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates a signed JWT (used primarily for test suites and dev fixtures)."""
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(hours=24))
    payload: Dict[str, Any] = {
        "sub": str(sub),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if email:
        payload["email"] = email
    if extra_claims:
        payload.update(extra_claims)

    secret = get_jwt_secret()
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_supabase_token(token: str) -> TokenPayload:
    """Verifies a Supabase JWT and returns the parsed payload.
    Raises HTTPException(401) on failure.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = get_jwt_secret()

    try:
        # First attempt: standard decode with secret
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # If secret validation failed in dev mode, check if token can be inspected
        if not settings.is_production:
            try:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_aud": False},
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim ('sub')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenPayload(
        sub=sub,
        email=payload.get("email"),
        role=payload.get("role"),
        exp=payload.get("exp"),
        raw_claims=payload,
    )
