"""
SafetyCare Custom Exceptions

Defines application-specific exceptions for consistent error handling.
"""

from typing import Any


class SafetyCareError(Exception):
    """Base exception for all SafetyCare errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# =============================================================================
# Authentication Errors
# =============================================================================


class AuthenticationError(SafetyCareError):
    """Raised when authentication fails."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials are invalid."""

    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


class TokenInvalidError(AuthenticationError):
    """Raised when JWT token is malformed or invalid."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message)


class SetupNotCompleteError(AuthenticationError):
    """Raised when initial setup has not been completed."""

    def __init__(self, message: str = "Initial setup not complete") -> None:
        super().__init__(message)


# =============================================================================
# Camera Errors
# =============================================================================


class CameraError(SafetyCareError):
    """Base exception for camera-related errors."""

    pass


class CameraNotFoundError(CameraError):
    """Raised when a camera cannot be found by ID."""

    def __init__(self, camera_id: str) -> None:
        super().__init__(
            f"Camera not found: {camera_id}",
            details={"camera_id": camera_id},
        )
        self.camera_id = camera_id


class CameraAlreadyExistsError(CameraError):
    """Raised when attempting to create a camera that already exists."""

    def __init__(self, ip_address: str) -> None:
        super().__init__(
            f"Camera with IP address already exists: {ip_address}",
            details={"ip_address": ip_address},
        )
        self.ip_address = ip_address


class CameraConnectionError(CameraError):
    """Raised when camera connection fails."""

    def __init__(self, camera_id: str, reason: str) -> None:
        super().__init__(
            f"Failed to connect to camera {camera_id}: {reason}",
            details={"camera_id": camera_id, "reason": reason},
        )
        self.camera_id = camera_id
        self.reason = reason


class CameraStreamError(CameraError):
    """Raised when streaming from camera fails."""

    def __init__(self, camera_id: str, reason: str) -> None:
        super().__init__(
            f"Camera stream error for {camera_id}: {reason}",
            details={"camera_id": camera_id, "reason": reason},
        )
        self.camera_id = camera_id
        self.reason = reason


class CameraNotStreamingError(CameraError):
    """Raised when attempting to access a camera that is not streaming."""

    def __init__(self, camera_id: str) -> None:
        super().__init__(
            f"Camera is not streaming: {camera_id}",
            details={"camera_id": camera_id},
        )
        self.camera_id = camera_id


# =============================================================================
# Detection Errors
# =============================================================================


class DetectionError(SafetyCareError):
    """Base exception for detection-related errors."""

    pass


class ModelLoadError(DetectionError):
    """Raised when a ML model fails to load."""

    def __init__(self, model_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to load model {model_name}: {reason}",
            details={"model_name": model_name, "reason": reason},
        )
        self.model_name = model_name
        self.reason = reason


class FrameProcessingError(DetectionError):
    """Raised when frame processing fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Frame processing failed: {reason}",
            details={"reason": reason},
        )
        self.reason = reason


# =============================================================================
# Telegram Errors
# =============================================================================


class TelegramError(SafetyCareError):
    """Base exception for Telegram-related errors."""

    pass


class TelegramNotConfiguredError(TelegramError):
    """Raised when Telegram is not configured."""

    def __init__(self, message: str = "Telegram is not configured") -> None:
        super().__init__(message)


class TelegramConnectionError(TelegramError):
    """Raised when Telegram API connection fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Telegram connection failed: {reason}",
            details={"reason": reason},
        )
        self.reason = reason


class TelegramSendError(TelegramError):
    """Raised when sending a Telegram message fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Failed to send Telegram message: {reason}",
            details={"reason": reason},
        )
        self.reason = reason


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(SafetyCareError):
    """Raised when there's a configuration problem."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            f"Invalid configuration for {field}: {reason}",
            details={"field": field, "reason": reason},
        )
        self.field = field
        self.reason = reason
