"""Telegram configuration models."""

from typing import Annotated

from pydantic import BaseModel, Field


class TelegramConfigRequest(BaseModel):
    """Request to configure Telegram bot."""

    bot_token: Annotated[str, Field(min_length=10, description="Telegram Bot Token")]
    chat_id: Annotated[str, Field(min_length=1, description="Telegram Chat ID")]
    enabled: bool = True
    alert_cooldown_seconds: int = Field(default=30, ge=5, le=300)


class TelegramConfigResponse(BaseModel):
    """Response with current Telegram configuration."""

    configured: bool
    enabled: bool
    chat_id_masked: str | None = None
    alert_cooldown_seconds: int = 30


class TelegramTestResponse(BaseModel):
    """Response from Telegram test."""

    success: bool
    message: str


class TelegramInstructionsResponse(BaseModel):
    """Response with setup instructions."""

    instructions: str
