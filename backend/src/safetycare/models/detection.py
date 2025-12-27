"""Pydantic models for detection results and streaming data."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PersonState(str, Enum):
    """Detected person posture state."""

    STANDING = "standing"
    SITTING = "sitting"
    LYING = "lying"
    FALLING = "falling"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    """Bounding box coordinates (normalized 0-1)."""

    x: Annotated[float, Field(ge=0, le=1, description="Left edge")]
    y: Annotated[float, Field(ge=0, le=1, description="Top edge")]
    width: Annotated[float, Field(ge=0, le=1, description="Box width")]
    height: Annotated[float, Field(ge=0, le=1, description="Box height")]

    def to_pixels(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        """Convert to pixel coordinates.

        Returns:
            Tuple of (x1, y1, x2, y2) in pixels
        """
        x1 = int(self.x * frame_width)
        y1 = int(self.y * frame_height)
        x2 = int((self.x + self.width) * frame_width)
        y2 = int((self.y + self.height) * frame_height)
        return x1, y1, x2, y2


class PoseLandmark(BaseModel):
    """Single pose landmark from MediaPipe."""

    id: int = Field(description="Landmark index (0-32)")
    name: str = Field(description="Landmark name")
    x: float = Field(description="X coordinate (normalized)")
    y: float = Field(description="Y coordinate (normalized)")
    z: float = Field(description="Z coordinate (depth)")
    visibility: float = Field(ge=0, le=1, description="Landmark visibility confidence")


class PersonDetection(BaseModel):
    """Detection result for a single person."""

    id: str = Field(description="Tracking ID (format: camera_id_person_N)")
    bbox: BoundingBox
    pose_landmarks: list[PoseLandmark] = Field(default_factory=list)
    state: PersonState = PersonState.UNKNOWN
    confidence: Annotated[float, Field(ge=0, le=1)] = 0.0
    body_angle: float | None = Field(default=None, description="Torso angle from vertical")
    fall_risk_score: float | None = Field(default=None, ge=0, le=1)


class DetectionResult(BaseModel):
    """Complete detection result for a frame."""

    timestamp: datetime = Field(default_factory=datetime.now)
    frame_number: int = 0
    persons: list[PersonDetection] = Field(default_factory=list)
    fall_detected: bool = False
    fall_person_ids: list[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


class FramePayload(BaseModel):
    """Payload for streaming frame data."""

    frame: str = Field(description="Base64 encoded JPEG")
    width: int
    height: int
    fps: float


class DetectionPayload(BaseModel):
    """Payload for detection results."""

    persons: list[PersonDetection]
    fall_detected: bool
    processing_time_ms: float


class AlertPayload(BaseModel):
    """Payload for fall alert."""

    type: Literal["fall_detected"] = "fall_detected"
    person_id: str
    confidence: float
    frame_snapshot: str = Field(description="Base64 encoded JPEG snapshot")


class StatusPayload(BaseModel):
    """Payload for stream status updates."""

    connected: bool
    streaming: bool
    error: str | None = None
    fps: float | None = None
    frame_count: int = 0


class StreamMessage(BaseModel):
    """WebSocket message wrapper."""

    type: Literal["frame", "detection", "alert", "status"]
    timestamp: datetime = Field(default_factory=datetime.now)
    camera_id: str
    payload: FramePayload | DetectionPayload | AlertPayload | StatusPayload


class FallEvent(BaseModel):
    """Recorded fall event."""

    id: str
    camera_id: str
    timestamp: datetime
    person_detection: PersonDetection
    confidence: float
    snapshot_path: str | None = None
    notified: bool = False
    acknowledged: bool = False
