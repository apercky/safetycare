"""SafetyCare - Fall Detection System Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from safetycare import __version__
from safetycare.api.router import api_router
from safetycare.config import get_settings
from safetycare.core.security import PasswordManager, get_or_create_jwt_secret
from safetycare.services.rtsp_client import RTSPClientManager
from safetycare.services.telegram_notifier import TelegramConfigManager, TelegramNotifier
from safetycare.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Global service instances
rtsp_manager: RTSPClientManager | None = None
telegram_notifier: TelegramNotifier | None = None


def get_rtsp_manager() -> RTSPClientManager:
    """Get RTSP client manager instance."""
    global rtsp_manager
    if rtsp_manager is None:
        rtsp_manager = RTSPClientManager()
    return rtsp_manager


def get_telegram_notifier() -> TelegramNotifier:
    """Get Telegram notifier instance."""
    global telegram_notifier
    if telegram_notifier is None:
        telegram_notifier = TelegramNotifier()
    return telegram_notifier


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Setup logging
    setup_logging(settings.log_level)
    logger.info(f"Starting SafetyCare in {settings.env} mode")

    # Initialize JWT secret
    jwt_secret = get_or_create_jwt_secret()
    # Update settings with generated secret if needed
    if not settings.jwt_secret:
        object.__setattr__(settings, "jwt_secret", jwt_secret)

    # Initialize password manager
    password_manager = PasswordManager(settings.auth_dir)
    if not password_manager.is_initialized():
        password = password_manager.initialize()
        logger.info("Initial password generated - check setup page")

    # Initialize RTSP manager
    global rtsp_manager
    rtsp_manager = RTSPClientManager(settings)

    # Initialize Telegram notifier
    global telegram_notifier
    telegram_config_manager = TelegramConfigManager(settings=settings)
    telegram_config = telegram_config_manager.load()
    telegram_notifier = TelegramNotifier(config=telegram_config, settings=settings)

    if telegram_notifier.is_configured():
        logger.info("Telegram notifier configured")
    else:
        logger.info("Telegram notifier not configured")

    # Store managers in app state for dependency injection
    app.state.rtsp_manager = rtsp_manager
    app.state.telegram_notifier = telegram_notifier
    app.state.password_manager = password_manager
    app.state.settings = settings

    logger.info("SafetyCare started successfully")

    yield

    # Cleanup
    logger.info("Shutting down SafetyCare...")

    if rtsp_manager:
        rtsp_manager.stop_all()

    if telegram_notifier:
        await telegram_notifier.close()

    logger.info("SafetyCare shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="SafetyCare API",
        description="Fall Detection System via IP Cam using MediaPipe and YOLOv8",
        version=__version__,
        docs_url="/api/docs" if settings.env != "production" else None,
        redoc_url="/api/redoc" if settings.env != "production" else None,
        openapi_url="/api/openapi.json" if settings.env != "production" else None,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://safetycare.local",
            "https://localhost:3000",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Basic health check endpoint."""
        return {"status": "healthy"}

    return app


# Create app instance
app = create_app()


def main() -> None:
    """Main entry point for running the application."""
    settings = get_settings()

    uvicorn.run(
        "safetycare.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
        log_level=settings.log_level.lower(),
        ssl_keyfile="/certs/server.key" if settings.env == "production" else None,
        ssl_certfile="/certs/server.crt" if settings.env == "production" else None,
    )


if __name__ == "__main__":
    main()
