"""Video streaming API endpoints."""

import asyncio
import base64
import time
from typing import Annotated, AsyncGenerator
from uuid import UUID

import cv2
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from safetycare.config import Settings
from safetycare.core.dependencies import get_settings, require_auth
from safetycare.models.detection import (
    DetectionPayload,
    FramePayload,
    PersonDetection,
    StatusPayload,
    StreamMessage,
)
from safetycare.services.detection_pipeline import DetectionPipeline
from safetycare.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Global detection pipeline instance
_detection_pipeline: DetectionPipeline | None = None


def get_detection_pipeline() -> DetectionPipeline:
    """Get or create detection pipeline."""
    global _detection_pipeline
    if _detection_pipeline is None:
        _detection_pipeline = DetectionPipeline()
    return _detection_pipeline


async def generate_mjpeg_stream(
    camera_id: str, settings: Settings
) -> AsyncGenerator[bytes, None]:
    """Generate MJPEG stream from camera.

    Args:
        camera_id: Camera identifier
        settings: Application settings

    Yields:
        MJPEG frame data
    """
    from safetycare.main import get_rtsp_manager

    rtsp_manager = get_rtsp_manager()
    client = rtsp_manager.get_client(camera_id)

    if client is None:
        logger.warning(f"No client found for camera {camera_id}")
        return

    pipeline = get_detection_pipeline()
    frame_count = 0

    while True:
        frame = client.last_frame

        if frame is None:
            await asyncio.sleep(0.05)
            continue

        # Process frame through detection pipeline
        try:
            annotated_frame, result = pipeline.process_frame(frame, camera_id)

            # Check for fall and notify
            if result.fall_detected:
                await _handle_fall_detection(camera_id, annotated_frame, result)

            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), settings.stream_quality]
            _, jpeg = cv2.imencode(".jpg", annotated_frame, encode_param)

            # Yield MJPEG frame
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )

            frame_count += 1

            # Rate limiting
            await asyncio.sleep(1.0 / settings.stream_max_fps)

        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            await asyncio.sleep(0.1)


async def _handle_fall_detection(camera_id: str, frame, result) -> None:
    """Handle fall detection event."""
    from safetycare.main import get_telegram_notifier
    from safetycare.api.cameras import load_cameras
    from safetycare.config import get_settings

    settings = get_settings()
    notifier = get_telegram_notifier()

    if not notifier.is_configured():
        return

    # Get camera name
    cameras = load_cameras(settings)
    camera = cameras.get(camera_id)
    camera_name = camera.name if camera else camera_id

    # Encode snapshot
    _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    snapshot = jpeg.tobytes()

    # Get max confidence
    confidence = max(
        (p.confidence for p in result.persons if p.id in result.fall_person_ids),
        default=0.0,
    )

    # Send notification
    await notifier.send_fall_alert(
        camera_id=camera_id,
        camera_name=camera_name,
        snapshot=snapshot,
        confidence=confidence,
    )


@router.get("/{camera_id}/mjpeg")
async def mjpeg_stream(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Get MJPEG video stream from camera.

    This endpoint provides a continuous MJPEG stream suitable for
    embedding in an <img> tag.
    """
    from safetycare.main import get_rtsp_manager

    rtsp_manager = get_rtsp_manager()
    client = rtsp_manager.get_client(str(camera_id))

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata o non attiva.",
        )

    return StreamingResponse(
        generate_mjpeg_stream(str(camera_id), settings),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.websocket("/{camera_id}/ws")
async def websocket_stream(
    websocket: WebSocket,
    camera_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """WebSocket endpoint for real-time video and detection data.

    Provides both video frames (as base64 JPEG) and structured
    detection results for overlay rendering.
    """
    from safetycare.main import get_rtsp_manager

    # Accept connection
    await websocket.accept()

    rtsp_manager = get_rtsp_manager()
    client = rtsp_manager.get_client(str(camera_id))

    logger.info(f"WebSocket connection for camera {camera_id}, client exists: {client is not None}")

    if client is None:
        logger.warning(f"No RTSP client for camera {camera_id}")
        await websocket.send_json(
            StreamMessage(
                type="status",
                camera_id=str(camera_id),
                payload=StatusPayload(
                    connected=False,
                    streaming=False,
                    error="Camera non trovata o non attiva.",
                ),
            ).model_dump(mode="json")
        )
        await websocket.close()
        return

    logger.info(f"RTSP client state: {client.state.value}, has frame: {client.last_frame is not None}")

    pipeline = get_detection_pipeline()
    frame_count = 0
    last_heartbeat = time.time()
    connection_open = True

    async def safe_send(message: dict) -> bool:
        """Safely send message, return False if connection is closed."""
        nonlocal connection_open
        if not connection_open:
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            connection_open = False
            return False

    try:
        # Send initial status
        if not await safe_send(
            StreamMessage(
                type="status",
                camera_id=str(camera_id),
                payload=StatusPayload(
                    connected=True,
                    streaming=True,
                    fps=client.stats.avg_fps,
                ),
            ).model_dump(mode="json")
        ):
            return

        no_frame_count = 0
        while connection_open:
            frame = client.last_frame

            if frame is None:
                no_frame_count += 1
                if no_frame_count == 1 or no_frame_count % 100 == 0:
                    logger.debug(f"Camera {camera_id}: waiting for frame (count={no_frame_count}, state={client.state.value})")
                # Send heartbeat if no frame
                if (time.time() - last_heartbeat) > settings.websocket_heartbeat_interval:
                    if not await safe_send(
                        StreamMessage(
                            type="status",
                            camera_id=str(camera_id),
                            payload=StatusPayload(
                                connected=True,
                                streaming=client.state.value == "streaming",
                                fps=client.stats.avg_fps,
                                frame_count=frame_count,
                            ),
                        ).model_dump(mode="json")
                    ):
                        break
                    last_heartbeat = time.time()

                await asyncio.sleep(0.05)
                continue

            try:
                # Process frame
                annotated_frame, result = pipeline.process_frame(frame, str(camera_id))
                frame_count += 1
                no_frame_count = 0  # Reset counter when we get a frame

                if frame_count == 1 or frame_count % 100 == 0:
                    logger.info(f"Camera {camera_id}: processed frame {frame_count}, persons={len(result.persons)}")

                # Handle fall detection
                if result.fall_detected:
                    await _handle_fall_detection(str(camera_id), annotated_frame, result)

                    # Send alert message
                    from safetycare.models.detection import AlertPayload

                    _, alert_jpeg = cv2.imencode(
                        ".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                    )

                    for person_id in result.fall_person_ids:
                        person = next(
                            (p for p in result.persons if p.id == person_id), None
                        )
                        if person:
                            if not await safe_send(
                                StreamMessage(
                                    type="alert",
                                    camera_id=str(camera_id),
                                    payload=AlertPayload(
                                        person_id=person_id,
                                        confidence=person.confidence,
                                        frame_snapshot=base64.b64encode(
                                            alert_jpeg.tobytes()
                                        ).decode(),
                                    ),
                                ).model_dump(mode="json")
                            ):
                                break

                if not connection_open:
                    break

                # Encode frame
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), settings.stream_quality]
                _, jpeg = cv2.imencode(".jpg", annotated_frame, encode_param)
                frame_b64 = base64.b64encode(jpeg.tobytes()).decode()

                height, width = annotated_frame.shape[:2]

                # Send frame message
                if not await safe_send(
                    StreamMessage(
                        type="frame",
                        camera_id=str(camera_id),
                        payload=FramePayload(
                            frame=frame_b64,
                            width=width,
                            height=height,
                            fps=client.stats.avg_fps,
                        ),
                    ).model_dump(mode="json")
                ):
                    break

                # Send detection message
                if not await safe_send(
                    StreamMessage(
                        type="detection",
                        camera_id=str(camera_id),
                        payload=DetectionPayload(
                            persons=[
                                PersonDetection(
                                    id=p.id,
                                    bbox=p.bbox,
                                    pose_landmarks=p.pose_landmarks,
                                    state=p.state,
                                    confidence=p.confidence,
                                    body_angle=p.body_angle,
                                    fall_risk_score=p.fall_risk_score,
                                )
                                for p in result.persons
                            ],
                            fall_detected=result.fall_detected,
                            processing_time_ms=result.processing_time_ms,
                        ),
                    ).model_dump(mode="json")
                ):
                    break

                # Rate limiting
                await asyncio.sleep(1.0 / settings.stream_max_fps)

            except Exception as e:
                logger.error(f"WebSocket frame processing error: {e}")
                await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connection_open = False
        logger.debug(f"WebSocket closed for camera {camera_id}")


@router.get("/{camera_id}/snapshot")
async def get_snapshot(
    camera_id: UUID,
    _: Annotated[None, Depends(require_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Get single snapshot from camera."""
    from safetycare.main import get_rtsp_manager

    rtsp_manager = get_rtsp_manager()
    client = rtsp_manager.get_client(str(camera_id))

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera non trovata o non attiva.",
        )

    frame = client.last_frame

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nessun frame disponibile.",
        )

    # Process through detection pipeline
    pipeline = get_detection_pipeline()
    annotated_frame, _ = pipeline.process_frame(frame, str(camera_id))

    # Encode as JPEG
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    _, jpeg = cv2.imencode(".jpg", annotated_frame, encode_param)

    return StreamingResponse(
        iter([jpeg.tobytes()]),
        media_type="image/jpeg",
    )
