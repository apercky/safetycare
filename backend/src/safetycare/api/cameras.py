"""Camera management API endpoints."""

import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from safetycare.config import Settings
from safetycare.core.dependencies import get_settings, require_auth
from safetycare.models.camera import (
    Camera,
    CameraActionResponse,
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraStatus,
    CameraUpdate,
)
from safetycare.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_cameras_file(settings: Settings) -> str:
    """Get path to cameras configuration file."""
    return str(settings.cameras_dir / "cameras.json")


def load_cameras(settings: Settings) -> dict[str, Camera]:
    """Load cameras from storage."""
    cameras_file = settings.cameras_dir / "cameras.json"

    if not cameras_file.exists():
        return {}

    try:
        data = json.loads(cameras_file.read_text())
        return {
            camera_id: Camera(**camera_data)
            for camera_id, camera_data in data.items()
        }
    except Exception as e:
        logger.error(f"Error loading cameras: {e}")
        return {}


def save_cameras(settings: Settings, cameras: dict[str, Camera]) -> None:
    """Save cameras to storage."""
    cameras_file = settings.cameras_dir / "cameras.json"

    data = {
        str(camera.id): camera.model_dump(mode="json")
        for camera in cameras.values()
    }

    cameras_file.write_text(json.dumps(data, indent=2, default=str))


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraListResponse:
    """List all configured cameras."""
    cameras = load_cameras(settings)

    return CameraListResponse(
        cameras=[CameraResponse.from_camera(c) for c in cameras.values()],
        total=len(cameras),
    )


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_data: CameraCreate,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraResponse:
    """Add a new camera."""
    cameras = load_cameras(settings)

    # Check for duplicate IP
    for existing in cameras.values():
        if existing.ip_address == camera_data.ip_address:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera con IP {camera_data.ip_address} già esistente.",
            )

    # Create new camera
    camera = Camera(
        **camera_data.model_dump(),
        status=CameraStatus.IDLE,
    )

    cameras[str(camera.id)] = camera
    save_cameras(settings, cameras)

    logger.info(f"Camera created: {camera.name} ({camera.ip_address})")

    return CameraResponse.from_camera(camera)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraResponse:
    """Get camera by ID."""
    cameras = load_cameras(settings)
    camera = cameras.get(str(camera_id))

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata.",
        )

    return CameraResponse.from_camera(camera)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: UUID,
    camera_data: CameraUpdate,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraResponse:
    """Update camera configuration."""
    cameras = load_cameras(settings)
    camera = cameras.get(str(camera_id))

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata.",
        )

    # Update fields
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    camera.updated_at = datetime.now()

    cameras[str(camera_id)] = camera
    save_cameras(settings, cameras)

    logger.info(f"Camera updated: {camera.name}")

    return CameraResponse.from_camera(camera)


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Delete a camera."""
    cameras = load_cameras(settings)

    if str(camera_id) not in cameras:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata.",
        )

    camera = cameras.pop(str(camera_id))
    save_cameras(settings, cameras)

    logger.info(f"Camera deleted: {camera.name}")

    return {"message": f"Camera '{camera.name}' eliminata."}


@router.post("/{camera_id}/start", response_model=CameraActionResponse)
async def start_camera_stream(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraActionResponse:
    """Start streaming from a camera."""
    cameras = load_cameras(settings)
    camera = cameras.get(str(camera_id))

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata.",
        )

    if not camera.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera disabilitata.",
        )

    # Import here to avoid circular imports
    from safetycare.main import get_rtsp_manager

    rtsp_manager = get_rtsp_manager()

    # Create and start client
    def on_state_change(state, error):
        # Update camera status in storage
        nonlocal cameras
        if str(camera_id) in cameras:
            cam = cameras[str(camera_id)]
            if state.value == "streaming":
                cam.status = CameraStatus.STREAMING
            elif state.value == "error":
                cam.status = CameraStatus.ERROR
                cam.error_message = error
            elif state.value == "connecting":
                cam.status = CameraStatus.CONNECTING
            cam.last_seen = datetime.now()
            save_cameras(settings, cameras)

    client = rtsp_manager.create_client(
        camera_id=str(camera_id),
        rtsp_url=camera.rtsp_url,
        on_state_change=on_state_change,
    )

    if client.start():
        camera.status = CameraStatus.CONNECTING
        camera.error_message = None  # Clear previous errors
        save_cameras(settings, cameras)

        return CameraActionResponse(
            success=True,
            message=f"Streaming avviato per {camera.name}",
            camera_id=str(camera_id),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore avvio streaming.",
        )


@router.post("/{camera_id}/stop", response_model=CameraActionResponse)
async def stop_camera_stream(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CameraActionResponse:
    """Stop streaming from a camera."""
    cameras = load_cameras(settings)
    camera = cameras.get(str(camera_id))

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata.",
        )

    from safetycare.main import get_rtsp_manager

    rtsp_manager = get_rtsp_manager()
    rtsp_manager.remove_client(str(camera_id))

    camera.status = CameraStatus.IDLE
    camera.error_message = None  # Clear errors on stop
    save_cameras(settings, cameras)

    return CameraActionResponse(
        success=True,
        message=f"Streaming fermato per {camera.name}",
        camera_id=str(camera_id),
    )
