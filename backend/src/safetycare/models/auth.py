"""Authentication models for SafetyCare API."""

from typing import Annotated

from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    """Response for setup status check."""

    is_initialized: bool
    has_initial_password: bool
    requires_setup: bool


class InitialPasswordResponse(BaseModel):
    """Response containing initial password for first-run setup."""

    password: str
    message: str


class LoginRequest(BaseModel):
    """Login request payload."""

    password: Annotated[str, Field(min_length=1)]


class LoginResponse(BaseModel):
    """Login response."""

    success: bool
    message: str


class TokenVerifyResponse(BaseModel):
    """Token verification response."""

    valid: bool
    expires_in_hours: float | None = None
