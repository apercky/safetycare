"""Telegram configuration API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from safetycare.core.dependencies import require_auth
from safetycare.models.telegram import (
    TelegramConfigRequest,
    TelegramConfigResponse,
    TelegramInstructionsResponse,
    TelegramTestResponse,
)
from safetycare.services.telegram_notifier import (
    TELEGRAM_SETUP_INSTRUCTIONS,
    TelegramConfig,
    TelegramConfigManager,
)
from safetycare.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/config", response_model=TelegramConfigResponse)
async def get_telegram_config(
    _: Annotated[None, Depends(require_auth)],
) -> TelegramConfigResponse:
    """Get current Telegram configuration status.

    Returns masked configuration for security.
    """
    from safetycare.main import get_telegram_notifier

    notifier = get_telegram_notifier()
    config = notifier.config

    if config is None or not config.is_valid():
        return TelegramConfigResponse(configured=False, enabled=False)

    # Mask chat ID for security
    chat_id = config.chat_id
    if len(chat_id) > 6:
        masked = chat_id[:3] + "*" * (len(chat_id) - 6) + chat_id[-3:]
    else:
        masked = "***"

    return TelegramConfigResponse(
        configured=True,
        enabled=config.enabled,
        chat_id_masked=masked,
        alert_cooldown_seconds=config.alert_cooldown_seconds,
    )


@router.post("/configure", response_model=TelegramTestResponse)
async def configure_telegram(
    config: TelegramConfigRequest,
    _: Annotated[None, Depends(require_auth)],
) -> TelegramTestResponse:
    """Configure Telegram bot settings.

    Validates the configuration by testing the connection.
    """
    from safetycare.config import get_settings
    from safetycare.main import get_telegram_notifier

    settings = get_settings()
    notifier = get_telegram_notifier()

    # Create new config
    new_config = TelegramConfig(
        bot_token=config.bot_token,
        chat_id=config.chat_id,
        enabled=config.enabled,
        alert_cooldown_seconds=config.alert_cooldown_seconds,
    )

    # Update notifier
    notifier.config = new_config

    # Test connection
    success, message = await notifier.test_connection()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configurazione non valida: {message}",
        )

    # Save configuration
    config_manager = TelegramConfigManager(settings=settings)
    if not config_manager.save(new_config):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nel salvataggio della configurazione.",
        )

    logger.info("Telegram configuration saved")

    return TelegramTestResponse(
        success=True,
        message=f"Configurazione salvata. {message}",
    )


@router.post("/test", response_model=TelegramTestResponse)
async def test_telegram(
    _: Annotated[None, Depends(require_auth)],
) -> TelegramTestResponse:
    """Send test message to verify Telegram configuration."""
    from safetycare.main import get_telegram_notifier

    notifier = get_telegram_notifier()

    if not notifier.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram non configurato.",
        )

    success, message = await notifier.send_test_message()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message,
        )

    return TelegramTestResponse(success=True, message=message)


@router.delete("/config")
async def delete_telegram_config(
    _: Annotated[None, Depends(require_auth)],
) -> dict[str, str]:
    """Remove Telegram configuration."""
    from safetycare.config import get_settings
    from safetycare.main import get_telegram_notifier

    settings = get_settings()
    notifier = get_telegram_notifier()

    # Clear notifier config
    notifier.config = None

    # Delete config file
    config_manager = TelegramConfigManager(settings=settings)
    config_file = config_manager.config_file

    if config_file.exists():
        config_file.unlink()

    logger.info("Telegram configuration removed")

    return {"message": "Configurazione Telegram rimossa."}


@router.get("/instructions", response_model=TelegramInstructionsResponse)
async def get_setup_instructions() -> TelegramInstructionsResponse:
    """Get Telegram bot setup instructions.

    Returns detailed instructions for creating and configuring
    a Telegram bot.
    """
    return TelegramInstructionsResponse(instructions=TELEGRAM_SETUP_INSTRUCTIONS)
