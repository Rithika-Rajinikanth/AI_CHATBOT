"""
app/auth_routes.py
Auth endpoints — registered in main.py under /auth prefix.

POST /auth/login          → JSON body  { user_id, role } → token pair
POST /auth/login/swagger  → form body  (username=user_id, password=role)
                            This is the tokenUrl that Swagger's Authorize
                            dialog posts to — it maps username→user_id,
                            password→role so the 🔒 button works.
POST /auth/refresh        → { refresh_token } → new token pair
GET  /auth/me             → current user info from token
"""
from fastapi import APIRouter, HTTPException, status, Depends, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth   import (
    TokenPayload, TokenPair,
    create_token_pair, refresh_access_token, get_current_user,
)
from app.config import settings

auth_router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    user_id: str
    role:    str

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "DIAckepAiQcR592cPUztHlMXQCD2",
                "role":    "farmer",
            }
        }


class RefreshRequest(BaseModel):
    refresh_token: str

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


# ── Helper: verify + issue tokens ─────────────────────────────────────────────

def _issue_tokens(user_id: str, role: str) -> TokenPair:
    """Validate role, optionally verify against Firestore, then issue tokens."""
    if role not in settings.VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {sorted(settings.VALID_ROLES)}",
        )

    # Try Firestore role verification (gracefully skipped if Firebase is down)
    verified_role = role
    try:
        from app.queries import get_user
        user_doc = get_user(user_id)
        if user_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found in Firestore.",
            )
        fs_role = user_doc.get("role", "")
        if fs_role in settings.VALID_ROLES:
            verified_role = fs_role   # Firestore role takes priority
    except HTTPException:
        raise
    except Exception:
        pass   # Firebase unavailable → use app-sent role (dev/test mode)

    return create_token_pair(user_id=user_id, role=verified_role)


# ── Routes ─────────────────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=TokenPair, tags=["Auth"])
def login(body: LoginRequest):
    """
    **JSON login** — used by your mobile app and curl.

    Send `user_id` (Firebase UID) and `role`.
    Returns `access_token` (30 min) + `refresh_token` (7 days).
    """
    return _issue_tokens(body.user_id, body.role)


@auth_router.post(
    "/login/swagger",
    response_model=TokenPair,
    include_in_schema=False,   # hidden from docs — only used by Swagger Authorize
)
def login_swagger(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 form-body login — used ONLY by the Swagger UI 🔒 Authorize button.

    Swagger sends:  username = Firebase UID
                    password = role  (farmer | dealer | user)

    This maps them to our actual fields and issues the token pair.
    The access_token is then automatically sent as Bearer on every
    Swagger request — no manual copy-paste needed.
    """
    user_id = form_data.username   # Swagger "username" field → Firebase UID
    role    = form_data.password   # Swagger "password" field → role

    return _issue_tokens(user_id, role)


@auth_router.post("/refresh", response_model=TokenPair, tags=["Auth"])
def refresh(body: RefreshRequest):
    """
    Exchange a valid refresh token for a fresh access + refresh token pair.
    Call this when you receive `401 Token has expired`.
    """
    return refresh_access_token(body.refresh_token)


@auth_router.get("/me", tags=["Auth"])
def me(user: TokenPayload = Depends(get_current_user)):
    """Returns current user's decoded token info. Requires Bearer token."""
    return {"user_id": user.sub, "role": user.role}
