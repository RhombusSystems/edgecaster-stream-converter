"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from backend.app.auth import create_session_token, hash_password, verify_password
from backend.app.config import save_config
from backend.app.dependencies import get_config, get_state_store, require_auth
from backend.app.models.settings import SetupState

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class SetPasswordRequest(BaseModel):
    password: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    setup_state: SetupState


@router.get("/status")
async def auth_status() -> AuthStatusResponse:
    """Check authentication state and setup progress."""
    config = get_config()

    if not config.admin_password_hash:
        return AuthStatusResponse(authenticated=False, setup_state=SetupState.NEEDS_PASSWORD)
    if not config.api_key:
        return AuthStatusResponse(authenticated=False, setup_state=SetupState.NEEDS_API_KEY)
    return AuthStatusResponse(authenticated=False, setup_state=SetupState.READY)


@router.post("/setup-password")
async def setup_password(req: SetPasswordRequest, response: Response) -> dict:
    """Set the admin password during first-run setup."""
    config = get_config()

    if config.admin_password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin password already configured. Use settings to change it.",
        )

    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )

    config.admin_password_hash = hash_password(req.password)
    save_config(config)

    # Auto-login after password creation
    token = create_session_token(config.session_secret)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return {"ok": True}


@router.post("/login")
async def login(req: LoginRequest, response: Response) -> dict:
    """Authenticate with the admin password."""
    config = get_config()

    if not config.admin_password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No admin password set. Complete first-run setup.",
        )

    if not verify_password(req.password, config.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )

    token = create_session_token(config.session_secret)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return {"ok": True}


@router.post("/logout", dependencies=[Depends(require_auth)])
async def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie("session")
    return {"ok": True}
