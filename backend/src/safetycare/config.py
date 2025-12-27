"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="SAFETYCARE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    env: Literal["development", "production", "testing"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_dir: Path = Path("/data")
    host: str = "0.0.0.0"
    port: int = 8000

    # Security
    jwt_secret: str = Field(default="", description="JWT secret key (auto-generated if empty)")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    password_min_length: int = 18

    # Detection Pipeline
    detection_confidence: float = Field(
        default=0.7, ge=0.1, le=1.0, description="Minimum confidence for fall detection"
    )
    fall_alert_cooldown: int = Field(
        default=30, ge=5, le=300, description="Seconds between alerts for same camera"
    )
    frame_skip: int = Field(
        default=2, ge=0, le=10, description="Process every Nth frame (0 = no skip)"
    )
    max_persons_per_frame: int = Field(default=5, ge=1, le=20)

    # MediaPipe
    mediapipe_model_complexity: Literal[0, 1, 2] = Field(
        default=1,
        description="0=Lite, 1=Full, 2=Heavy. Higher = more accurate but slower"
    )
    mediapipe_min_detection_confidence: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Minimum detection confidence"
    )
    mediapipe_min_tracking_confidence: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Minimum tracking confidence"
    )

    # Streaming
    stream_quality: int = Field(default=80, ge=10, le=100, description="JPEG quality")
    stream_max_fps: int = Field(default=15, ge=1, le=30)
    websocket_heartbeat_interval: int = 30

    # RTSP
    rtsp_timeout: int = Field(default=10, ge=5, le=60)
    rtsp_reconnect_delay: int = Field(default=5, ge=1, le=30)
    rtsp_max_reconnect_attempts: int = Field(default=5, ge=1, le=20)

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    @field_validator("data_dir")
    @classmethod
    def ensure_data_dir_exists(cls, v: Path) -> Path:
        """Ensure data directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def auth_dir(self) -> Path:
        """Directory for authentication data."""
        path = self.data_dir / "auth"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cameras_dir(self) -> Path:
        """Directory for camera configurations."""
        path = self.data_dir / "cameras"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Directory for log files."""
        path = self.data_dir / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def models_dir(self) -> Path:
        """Directory for ML models."""
        path = self.data_dir / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
