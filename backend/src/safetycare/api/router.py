"""Main API router aggregating all endpoints."""

from fastapi import APIRouter

from safetycare.api.auth import router as auth_router
from safetycare.api.cameras import router as cameras_router
from safetycare.api.health import router as health_router
from safetycare.api.stream import router as stream_router
from safetycare.api.telegram import router as telegram_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(cameras_router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(stream_router, prefix="/stream", tags=["Streaming"])
api_router.include_router(telegram_router, prefix="/telegram", tags=["Telegram"])
