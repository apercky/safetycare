"""Pydantic models for camera configuration and status."""

from datetime import datetime
from enum import Enum
from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CameraStatus(str, Enum):
    """Camera connection status."""

    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ERROR = "error"
    DISABLED = "disabled"


class CameraStream(str, Enum):
    """RTSP stream quality selection."""

    STREAM1 = "stream1"  # 1080p
    STREAM2 = "stream2"  # 720p


class CameraBase(BaseModel):
    """Base camera configuration."""

    name: Annotated[str, Field(min_length=1, max_length=100, description="Display name")]
    ip_address: Annotated[
        str,
        Field(
            pattern=r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
            description="Camera IP address",
        ),
    ]
    username: Annotated[str, Field(min_length=1, max_length=50, description="RTSP username")]
    password: Annotated[str, Field(min_length=1, max_length=100, description="RTSP password")]
    stream: CameraStream = Field(default=CameraStream.STREAM2, description="Stream quality")
    port: int = Field(default=554, ge=1, le=65535, description="RTSP port")
    enabled: bool = Field(default=True, description="Whether camera is enabled")

    @property
    def rtsp_url(self) -> str:
        """Generate RTSP URL for this camera with URL-encoded credentials."""
        # URL encode username and password to handle special characters like @, :, /, etc.
        encoded_user = quote(self.username, safe="")
        encoded_pass = quote(self.password, safe="")
        return f"rtsp://{encoded_user}:{encoded_pass}@{self.ip_address}:{self.port}/{self.stream.value}"


class CameraCreate(CameraBase):
    """Model for creating a new camera."""

    pass


class CameraUpdate(BaseModel):
    """Model for updating camera configuration."""

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    ip_address: Annotated[
        str | None,
        Field(
            pattern=r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        ),
    ] = None
    username: Annotated[str | None, Field(min_length=1, max_length=50)] = None
    password: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    stream: CameraStream | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    enabled: bool | None = None


class Camera(CameraBase):
    """Full camera model with ID and status."""

    id: UUID = Field(default_factory=uuid4)
    status: CameraStatus = CameraStatus.IDLE
    last_seen: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class CameraResponse(BaseModel):
    """Camera response model (excludes password)."""

    id: UUID
    name: str
    ip_address: str
    username: str
    stream: CameraStream
    port: int
    enabled: bool
    status: CameraStatus
    last_seen: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_camera(cls, camera: Camera) -> "CameraResponse":
        """Create response from full camera model."""
        return cls(
            id=camera.id,
            name=camera.name,
            ip_address=camera.ip_address,
            username=camera.username,
            stream=camera.stream,
            port=camera.port,
            enabled=camera.enabled,
            status=camera.status,
            last_seen=camera.last_seen,
            error_message=camera.error_message,
            created_at=camera.created_at,
            updated_at=camera.updated_at,
        )


class CameraListResponse(BaseModel):
    """Response for camera list."""

    cameras: list[CameraResponse]
    total: int


class CameraActionResponse(BaseModel):
    """Response for camera actions."""

    success: bool
    message: str
    camera_id: str
