"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from safetycare import __version__
from safetycare.models.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


# Store startup time
_startup_time: datetime | None = None


def set_startup_time() -> None:
    """Set the application startup time."""
    global _startup_time
    _startup_time = datetime.now(timezone.utc)


def get_uptime() -> float:
    """Get uptime in seconds."""
    if _startup_time is None:
        return 0.0
    return (datetime.now(timezone.utc) - _startup_time).total_seconds()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns the service status, current timestamp, version, and uptime.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=__version__,
        uptime_seconds=get_uptime(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(request: Request) -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Verifies that all required services are available and the application
    is ready to handle requests.
    """
    checks: dict[str, bool] = {}
    
    # Check if RTSP manager is available
    rtsp_manager = getattr(request.app.state, "rtsp_manager", None)
    checks["rtsp_manager"] = rtsp_manager is not None
    
    # Check if password manager is initialized
    password_manager = getattr(request.app.state, "password_manager", None)
    checks["password_manager"] = password_manager is not None
    
    # Check if detection pipeline can be created (models available)
    try:
        from safetycare.services.detection_pipeline import DetectionPipeline
        checks["detection_models"] = True
    except Exception:
        checks["detection_models"] = False
    
    # Overall readiness
    ready = all(checks.values())
    
    return ReadinessResponse(ready=ready, checks=checks)


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.
    
    Simple endpoint that returns OK if the service is running.
    Used by container orchestrators to determine if the container should be restarted.
    """
    return {"status": "alive"}
