"""Health check models for SafetyCare API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    checks: dict[str, bool]
