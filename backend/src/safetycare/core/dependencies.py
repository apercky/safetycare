"""
SafetyCare FastAPI Dependencies

Provides dependency injection functions for FastAPI routes.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status

from safetycare.config import Settings, get_settings
from safetycare.core.exceptions import (
    CameraNotFoundError,
    CameraNotStreamingError,
    TokenExpiredError,
    TokenInvalidError,
)
from safetycare.core.security import PasswordManager, verify_access_token
from safetycare.services.rtsp_client import RTSPClientManager
from safetycare.services.telegram_notifier import TelegramNotifier


# =============================================================================
# Settings Dependency
# =============================================================================


def get_app_settings() -> Settings:
    """Get application settings singleton."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# =============================================================================
# Authentication Dependencies
# =============================================================================


def get_password_manager(request: Request) -> PasswordManager:
    """Get password manager from app state."""
    return request.app.state.password_manager


PasswordManagerDep = Annotated[PasswordManager, Depends(get_password_manager)]


async def get_current_user(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    """
    Validate JWT token from cookie and return user info.
    
    Raises:
        HTTPException: If token is missing, invalid, or expired.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = verify_access_token(access_token)
        return {"authenticated": True, "exp": payload.get("exp")}
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


def require_auth(current_user: CurrentUserDep) -> dict:
    """
    Dependency that requires valid authentication.
    
    Use this as a dependency to protect routes:
    
        @router.get("/protected")
        async def protected_route(user: RequireAuthDep):
            return {"message": "You are authenticated"}
    """
    return current_user


RequireAuthDep = Annotated[dict, Depends(require_auth)]


# =============================================================================
# RTSP Client Dependencies
# =============================================================================


def get_rtsp_manager(request: Request) -> RTSPClientManager:
    """Get RTSP client manager from app state."""
    return request.app.state.rtsp_manager


RTSPManagerDep = Annotated[RTSPClientManager, Depends(get_rtsp_manager)]


def get_rtsp_client(
    camera_id: str,
    rtsp_manager: RTSPManagerDep,
):
    """
    Get RTSP client for a specific camera.
    
    Raises:
        HTTPException: If camera is not streaming.
    """
    client = rtsp_manager.get_client(camera_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} is not streaming",
        )
    return client


# =============================================================================
# Telegram Dependencies
# =============================================================================


def get_telegram_notifier(request: Request) -> TelegramNotifier:
    """Get Telegram notifier from app state."""
    return request.app.state.telegram_notifier


TelegramNotifierDep = Annotated[TelegramNotifier, Depends(get_telegram_notifier)]


# =============================================================================
# Camera Storage Dependencies
# =============================================================================


def get_camera_storage(request: Request):
    """Get camera storage from app state."""
    return request.app.state.camera_storage


CameraStorageDep = Annotated[object, Depends(get_camera_storage)]


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_camera_exists(camera_id: str, camera_storage: CameraStorageDep) -> str:
    """
    Validate that a camera exists.
    
    Returns:
        The camera_id if valid.
        
    Raises:
        HTTPException: If camera not found.
    """
    camera = camera_storage.get(camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera not found: {camera_id}",
        )
    return camera_id


def validate_camera_streaming(
    camera_id: str,
    rtsp_manager: RTSPManagerDep,
) -> str:
    """
    Validate that a camera is currently streaming.
    
    Returns:
        The camera_id if streaming.
        
    Raises:
        HTTPException: If camera is not streaming.
    """
    if not rtsp_manager.has_client(camera_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera {camera_id} is not streaming",
        )
    return camera_id
