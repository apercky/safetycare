"""RTSP stream client for IP cameras."""

import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from safetycare.config import Settings, get_settings
from safetycare.utils.logging import get_logger

logger = get_logger(__name__)


class StreamState(str, Enum):
    """RTSP stream connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class StreamStats:
    """Statistics for stream monitoring."""

    frames_received: int = 0
    frames_dropped: int = 0
    bytes_received: int = 0
    last_frame_time: float = 0.0
    avg_fps: float = 0.0
    connection_time: float = 0.0
    reconnect_count: int = 0


class RTSPClient:
    """RTSP stream client with automatic reconnection."""

    def __init__(
        self,
        rtsp_url: str,
        camera_id: str,
        on_frame: Callable[[NDArray[np.uint8], str], None] | None = None,
        on_state_change: Callable[[StreamState, str | None], None] | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize RTSP client.

        Args:
            rtsp_url: Full RTSP URL with credentials
            camera_id: Unique camera identifier
            on_frame: Callback for received frames
            on_state_change: Callback for state changes
            settings: Application settings
        """
        self.rtsp_url = rtsp_url
        self.camera_id = camera_id
        self.on_frame = on_frame
        self.on_state_change = on_state_change
        self.settings = settings or get_settings()

        self._state = StreamState.DISCONNECTED
        self._capture: cv2.VideoCapture | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stats = StreamStats()
        self._last_frame: NDArray[np.uint8] | None = None
        self._error_message: str | None = None

    @property
    def state(self) -> StreamState:
        """Current stream state."""
        return self._state

    @property
    def stats(self) -> StreamStats:
        """Stream statistics."""
        return self._stats

    @property
    def last_frame(self) -> NDArray[np.uint8] | None:
        """Last received frame."""
        with self._lock:
            return self._last_frame.copy() if self._last_frame is not None else None

    @property
    def error_message(self) -> str | None:
        """Last error message if in ERROR state."""
        return self._error_message

    def _set_state(self, state: StreamState, error: str | None = None) -> None:
        """Update state and notify callback."""
        self._state = state
        self._error_message = error

        if self.on_state_change:
            try:
                self.on_state_change(state, error)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        logger.info(f"Camera {self.camera_id} state: {state.value}" + (f" - {error}" if error else ""))

    def start(self) -> bool:
        """Start streaming in background thread.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning(f"Camera {self.camera_id} already running")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

        return True

    def stop(self) -> None:
        """Stop streaming and cleanup."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._cleanup_capture()
        self._set_state(StreamState.DISCONNECTED)

        logger.info(f"Camera {self.camera_id} stopped")

    def _cleanup_capture(self) -> None:
        """Clean up video capture resources."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as e:
                logger.error(f"Error releasing capture: {e}")
            self._capture = None

    def _connect(self) -> bool:
        """Establish RTSP connection.

        Returns:
            True if connected successfully
        """
        self._set_state(StreamState.CONNECTING)

        # Clean up any existing capture
        self._cleanup_capture()

        try:
            # Configure OpenCV capture
            self._capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            # Set capture properties for better performance
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._capture.set(cv2.CAP_PROP_FPS, self.settings.stream_max_fps)

            # Test connection with timeout
            start_time = time.time()
            while (time.time() - start_time) < self.settings.rtsp_timeout:
                if self._capture.isOpened():
                    ret, frame = self._capture.read()
                    if ret and frame is not None:
                        self._set_state(StreamState.CONNECTED)
                        self._stats.connection_time = time.time() - start_time
                        logger.info(
                            f"Camera {self.camera_id} connected in "
                            f"{self._stats.connection_time:.2f}s"
                        )
                        return True
                time.sleep(0.1)

            raise TimeoutError(f"Connection timeout after {self.settings.rtsp_timeout}s")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Camera {self.camera_id} connection failed: {error_msg}")
            self._set_state(StreamState.ERROR, error_msg)
            self._cleanup_capture()
            return False

    def _stream_loop(self) -> None:
        """Main streaming loop running in background thread."""
        reconnect_attempts = 0
        frame_times: list[float] = []

        while self._running:
            # Connect if not connected
            if self._state not in [StreamState.CONNECTED, StreamState.STREAMING]:
                if reconnect_attempts >= self.settings.rtsp_max_reconnect_attempts:
                    self._set_state(
                        StreamState.ERROR,
                        f"Max reconnection attempts ({self.settings.rtsp_max_reconnect_attempts}) reached",
                    )
                    break

                if reconnect_attempts > 0:
                    self._set_state(StreamState.RECONNECTING)
                    delay = min(
                        self.settings.rtsp_reconnect_delay * (2 ** reconnect_attempts),
                        60,  # Max 60 seconds
                    )
                    logger.info(
                        f"Camera {self.camera_id} reconnecting in {delay}s "
                        f"(attempt {reconnect_attempts + 1})"
                    )
                    time.sleep(delay)
                    self._stats.reconnect_count += 1

                if not self._connect():
                    reconnect_attempts += 1
                    continue

                reconnect_attempts = 0
                self._set_state(StreamState.STREAMING)

            # Read frame
            if self._capture is None:
                continue

            try:
                ret, frame = self._capture.read()

                if not ret or frame is None:
                    logger.warning(f"Camera {self.camera_id} frame read failed")
                    self._stats.frames_dropped += 1
                    self._cleanup_capture()
                    reconnect_attempts += 1
                    continue

                # Update stats
                current_time = time.time()
                frame_times.append(current_time)

                # Keep only last 30 frame times for FPS calculation
                if len(frame_times) > 30:
                    frame_times = frame_times[-30:]

                if len(frame_times) >= 2:
                    time_span = frame_times[-1] - frame_times[0]
                    if time_span > 0:
                        self._stats.avg_fps = (len(frame_times) - 1) / time_span

                self._stats.frames_received += 1
                self._stats.last_frame_time = current_time
                self._stats.bytes_received += frame.nbytes

                # Store last frame
                with self._lock:
                    self._last_frame = frame

                # Call frame callback
                if self.on_frame:
                    try:
                        self.on_frame(frame, self.camera_id)
                    except Exception as e:
                        logger.error(f"Frame callback error: {e}")

                # Frame rate limiting
                if self.settings.frame_skip > 0:
                    if self._stats.frames_received % (self.settings.frame_skip + 1) != 0:
                        continue

            except Exception as e:
                logger.error(f"Camera {self.camera_id} stream error: {e}")
                self._cleanup_capture()
                reconnect_attempts += 1

        # Cleanup on exit
        self._cleanup_capture()
        self._set_state(StreamState.DISCONNECTED)

    async def async_start(self) -> bool:
        """Async wrapper for starting stream."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.start)

    async def async_stop(self) -> None:
        """Async wrapper for stopping stream."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.stop)


class RTSPClientManager:
    """Manages multiple RTSP clients."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize manager."""
        self.settings = settings or get_settings()
        self._clients: dict[str, RTSPClient] = {}
        self._lock = threading.Lock()

    def create_client(
        self,
        camera_id: str,
        rtsp_url: str,
        on_frame: Callable[[NDArray[np.uint8], str], None] | None = None,
        on_state_change: Callable[[StreamState, str | None], None] | None = None,
    ) -> RTSPClient:
        """Create and register new RTSP client.

        Args:
            camera_id: Unique camera identifier
            rtsp_url: RTSP URL
            on_frame: Frame callback
            on_state_change: State change callback

        Returns:
            Created client
        """
        with self._lock:
            if camera_id in self._clients:
                # Stop existing client first
                self._clients[camera_id].stop()

            client = RTSPClient(
                rtsp_url=rtsp_url,
                camera_id=camera_id,
                on_frame=on_frame,
                on_state_change=on_state_change,
                settings=self.settings,
            )

            self._clients[camera_id] = client

        return client

    def get_client(self, camera_id: str) -> RTSPClient | None:
        """Get client by camera ID."""
        return self._clients.get(camera_id)

    def remove_client(self, camera_id: str) -> None:
        """Stop and remove client."""
        with self._lock:
            if camera_id in self._clients:
                self._clients[camera_id].stop()
                del self._clients[camera_id]

    def stop_all(self) -> None:
        """Stop all clients."""
        with self._lock:
            for client in self._clients.values():
                client.stop()
            self._clients.clear()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all clients."""
        return {
            camera_id: {
                "state": client.state.value,
                "frames_received": client.stats.frames_received,
                "frames_dropped": client.stats.frames_dropped,
                "avg_fps": client.stats.avg_fps,
                "reconnect_count": client.stats.reconnect_count,
                "error": client.error_message,
            }
            for camera_id, client in self._clients.items()
        }
