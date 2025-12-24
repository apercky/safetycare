"""SafetyCare data models."""

from safetycare.models.auth import (
    InitialPasswordResponse,
    LoginRequest,
    LoginResponse,
    SetupStatusResponse,
    TokenVerifyResponse,
)
from safetycare.models.camera import (
    Camera,
    CameraActionResponse,
    CameraBase,
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraStatus,
    CameraStream,
    CameraUpdate,
)
from safetycare.models.detection import (
    AlertPayload,
    BoundingBox,
    DetectionPayload,
    DetectionResult,
    FramePayload,
    PersonDetection,
    PersonState,
    PoseLandmark,
    StatusPayload,
    StreamMessage,
)
from safetycare.models.health import (
    HealthResponse,
    ReadinessResponse,
)
from safetycare.models.telegram import (
    TelegramConfigRequest,
    TelegramConfigResponse,
    TelegramInstructionsResponse,
    TelegramTestResponse,
)

__all__ = [
    "AlertPayload",
    "BoundingBox",
    "Camera",
    "CameraActionResponse",
    "CameraBase",
    "CameraCreate",
    "CameraListResponse",
    "CameraResponse",
    "CameraStatus",
    "CameraStream",
    "CameraUpdate",
    "DetectionPayload",
    "DetectionResult",
    "FramePayload",
    "HealthResponse",
    "InitialPasswordResponse",
    "LoginRequest",
    "LoginResponse",
    "PersonDetection",
    "PersonState",
    "PoseLandmark",
    "ReadinessResponse",
    "SetupStatusResponse",
    "StatusPayload",
    "StreamMessage",
    "TelegramConfigRequest",
    "TelegramConfigResponse",
    "TelegramInstructionsResponse",
    "TelegramTestResponse",
    "TokenVerifyResponse",
]
