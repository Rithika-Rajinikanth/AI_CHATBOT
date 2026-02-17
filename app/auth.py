"""
app/auth.py
JWT Authentication — single secret, role embedded in payload.

Fix applied: replaced HTTPBearer() with OAuth2PasswordBearer so that
Swagger UI shows the 🔒 Authorize button and persists the token across
all requests in the /docs page.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.config import settings

# ── Security scheme ────────────────────────────────────────────────────────────
# OAuth2PasswordBearer registers a named "bearerAuth" scheme in the OpenAPI spec.
# This is what makes the 🔒 Authorize button appear in Swagger UI.
# tokenUrl points to our login endpoint so Swagger knows where to get tokens.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/swagger", auto_error=False)


# ── Pydantic models ────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    """Decoded access-token payload — used as FastAPI dependency result."""
    sub:  str             # Firebase UID
    role: str             # "farmer" | "dealer" | "user"
    exp:  Optional[int] = None


class TokenPair(BaseModel):
    """Returned by /auth/login and /auth/refresh."""
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    role:          str
    user_id:       str


# ── Token creation ─────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    """Short-lived access token — signed with JWT_SECRET."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": user_id, "role": role, "type": "access", "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str, role: str) -> str:
    """Long-lived refresh token — signed with JWT_REFRESH_SECRET."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": user_id, "role": role, "type": "refresh", "exp": expire},
        settings.JWT_REFRESH_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_token_pair(user_id: str, role: str) -> TokenPair:
    """Create both tokens at once (called after successful login)."""
    return TokenPair(
        access_token=create_access_token(user_id, role),
        refresh_token=create_refresh_token(user_id, role),
        role=role,
        user_id=user_id,
    )


# ── Token decoding ─────────────────────────────────────────────────────────────

def _decode(token: str, secret: str, expected_type: str) -> dict:
    """Decode and validate a JWT. Raises clean HTTP errors on failure."""
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Call POST /auth/refresh to renew.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Wrong token type. Expected '{expected_type}'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── FastAPI dependency ─────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    """
    Decodes the Bearer access token → returns TokenPayload(sub, role).

    auto_error=False means: if no token is provided, token=None here.
    We then raise a clean 401 ourselves (not a 403 "Forbidden").

    Usage in routes:
        @app.post("/chat")
        def chat(body: ChatRequest, user: TokenPayload = Depends(get_current_user)):
            role    = user.role    # "farmer" | "dealer" | "user"
            user_id = user.sub     # Firebase UID
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Click 🔒 Authorize in Swagger and paste your access_token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode(token, settings.JWT_SECRET, "access")

    role = payload.get("role", "")
    if role not in settings.VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role '{role}' in token. Must be: {sorted(settings.VALID_ROLES)}",
        )

    return TokenPayload(sub=payload["sub"], role=role, exp=payload.get("exp"))


# ── Refresh helper ─────────────────────────────────────────────────────────────

def refresh_access_token(refresh_token: str) -> TokenPair:
    """Validate a refresh token and issue a new token pair."""
    payload = _decode(refresh_token, settings.JWT_REFRESH_SECRET, "refresh")
    return create_token_pair(user_id=payload["sub"], role=payload["role"])
