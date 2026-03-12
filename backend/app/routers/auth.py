"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.dependencies import get_config
from backend.app.models.settings import SetupState

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    setup_state: SetupState


@router.get("/status")
async def auth_status() -> AuthStatusResponse:
    """Check setup progress."""
    config = get_config()

    if not config.api_key:
        return AuthStatusResponse(setup_state=SetupState.NEEDS_API_KEY)
    return AuthStatusResponse(setup_state=SetupState.READY)
