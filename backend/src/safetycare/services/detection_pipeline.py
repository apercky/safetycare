"""Fall detection pipeline using MediaPipe Pose (Apache 2.0 License).

This module implements fall detection using MediaPipe Tasks API, which provides:
- Person detection (built into pose estimation)
- 33-point pose landmark detection
- Real-time tracking optimized for CPU
- Multi-person support

License: MediaPipe is licensed under Apache 2.0, making it suitable for
commercial use without requiring source code disclosure or licensing fees.

Note: Uses MediaPipe Tasks API instead of legacy mp.solutions.pose
for compatibility with Apple Silicon (ARM64).
"""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
)
from numpy.typing import NDArray

from safetycare.config import Settings, get_settings
from safetycare.models.detection import (
    BoundingBox,
    DetectionResult,
    PersonDetection,
    PersonState,
    PoseLandmark,
)
from safetycare.utils.logging import get_logger

logger = get_logger(__name__)


# Pose skeleton connections for drawing
POSE_CONNECTIONS = [
    # Face
    (0, 1), (1, 2), (2, 3), (3, 7),  # Left eye
    (0, 4), (4, 5), (5, 6), (6, 8),  # Right eye
    (9, 10),  # Mouth
    # Arms
    (11, 13), (13, 15),  # Left arm
    (12, 14), (14, 16),  # Right arm
    (15, 17), (15, 19), (15, 21),  # Left hand
    (16, 18), (16, 20), (16, 22),  # Right hand
    # Torso
    (11, 12),  # Shoulders
    (11, 23), (12, 24),  # Torso sides
    (23, 24),  # Hips
    # Legs
    (23, 25), (25, 27), (27, 29), (27, 31),  # Left leg
    (24, 26), (26, 28), (28, 30), (28, 32),  # Right leg
]


class LandmarkIndex(int, Enum):
    """MediaPipe Pose landmark indices (33 points total)."""

    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass
class PersonTracker:
    """Tracks person state over time for fall detection.

    Uses temporal analysis to distinguish falls from normal movements
    like sitting or lying down intentionally.
    """

    person_id: int
    state_history: deque = field(default_factory=lambda: deque(maxlen=30))
    position_history: deque = field(default_factory=lambda: deque(maxlen=15))
    last_standing_time: float = 0.0
    fall_detected_time: float | None = None
    fall_cooldown_until: float = 0.0

    def add_observation(
        self,
        state: PersonState,
        hip_center_y: float,
        body_angle: float | None,
    ) -> None:
        """Record a state observation with position data."""
        now = time.time()
        self.state_history.append((now, state, body_angle))
        self.position_history.append((now, hip_center_y))

        if state == PersonState.STANDING:
            self.last_standing_time = now

    def get_vertical_velocity(self) -> float | None:
        """Calculate vertical velocity (positive = falling down).

        Returns velocity in normalized units per second.
        """
        if len(self.position_history) < 3:
            return None

        # Use 3 points to smooth out noise
        positions = list(self.position_history)[-3:]
        t_start, y_start = positions[0]
        t_end, y_end = positions[-1]

        dt = t_end - t_start
        if dt <= 0.01:  # Avoid division by very small numbers
            return None

        # Positive velocity = moving down (Y increases downward in image coords)
        return (y_end - y_start) / dt

    def detect_rapid_descent(self, threshold: float = 0.25) -> bool:
        """Detect if person is falling rapidly.

        Args:
            threshold: Minimum velocity to consider as rapid descent

        Returns:
            True if descending faster than threshold
        """
        velocity = self.get_vertical_velocity()
        return velocity is not None and velocity > threshold

    def was_recently_upright(self, seconds: float = 2.5) -> bool:
        """Check if person was standing or sitting upright recently."""
        if not self.state_history:
            return False

        now = time.time()
        for timestamp, state, _ in reversed(self.state_history):
            if now - timestamp > seconds:
                break
            if state in (PersonState.STANDING, PersonState.SITTING):
                return True
        return False

    def get_angle_change_rate(self) -> float | None:
        """Calculate how fast body angle is changing (degrees per second)."""
        if len(self.state_history) < 3:
            return None

        recent = [(t, angle) for t, _, angle in list(self.state_history)[-5:] if angle is not None]
        if len(recent) < 2:
            return None

        t_start, angle_start = recent[0]
        t_end, angle_end = recent[-1]

        dt = t_end - t_start
        if dt <= 0.01:
            return None

        return abs(angle_end - angle_start) / dt

    def is_in_fall_cooldown(self) -> bool:
        """Check if we're in cooldown period after a fall detection."""
        return time.time() < self.fall_cooldown_until

    def mark_fall_detected(self, cooldown_seconds: float = 10.0) -> None:
        """Mark that a fall was detected and start cooldown."""
        now = time.time()
        self.fall_detected_time = now
        self.fall_cooldown_until = now + cooldown_seconds


class DetectionPipeline:
    """Fall detection pipeline using MediaPipe Pose Tasks API.

    Uses MediaPipe's PoseLandmarker which provides:
    - Automatic person detection
    - 33-point body pose estimation
    - Multi-person tracking
    - Real-time performance on CPU

    Fall detection is based on:
    1. Body angle relative to vertical
    2. Vertical position change velocity
    3. Transition from upright to horizontal
    4. Temporal consistency to avoid false positives
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the detection pipeline.

        Args:
            settings: Application settings (uses defaults if None)
        """
        self.settings = settings or get_settings()
        self.person_trackers: dict[str, PersonTracker] = {}
        self.frame_count = 0
        self._next_person_id = 0
        self._last_timestamp_ms = 0

        # Determine model based on complexity setting
        model_map = {
            0: "pose_landmarker_lite.task",
            1: "pose_landmarker_full.task",
            2: "pose_landmarker_heavy.task",
        }
        model_name = model_map.get(
            self.settings.mediapipe_model_complexity,
            "pose_landmarker_full.task"
        )

        # Look for model in multiple locations:
        # 1. Project's models/ directory (backend/models for local development)
        # 2. settings.models_dir (data/models for production)
        from pathlib import Path
        project_models_dir = Path(__file__).parent.parent.parent.parent / "models"

        model_path = None
        for search_dir in [project_models_dir, self.settings.models_dir]:
            candidate = search_dir / model_name
            if candidate.exists():
                model_path = candidate
                break

        if model_path is None:
            raise FileNotFoundError(
                f"MediaPipe model '{model_name}' not found. "
                f"Searched in: {project_models_dir}, {self.settings.models_dir}. "
                f"Download it with: curl -L -o {project_models_dir / model_name} "
                f"'https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                f"{model_name.replace('.task', '')}/float16/latest/{model_name}'"
            )

        # Initialize MediaPipe PoseLandmarker with Tasks API
        base_options = BaseOptions(model_asset_path=str(model_path))
        options = PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.VIDEO,
            num_poses=self.settings.max_persons_per_frame,
            min_pose_detection_confidence=self.settings.mediapipe_min_detection_confidence,
            min_tracking_confidence=self.settings.mediapipe_min_tracking_confidence,
        )
        self.pose_landmarker = PoseLandmarker.create_from_options(options)

        logger.info(
            "MediaPipe detection pipeline initialized",
            model=model_name,
            model_complexity=self.settings.mediapipe_model_complexity,
            min_detection_confidence=self.settings.mediapipe_min_detection_confidence,
            num_poses=self.settings.max_persons_per_frame,
        )

    def process_frame(
        self,
        frame: NDArray[np.uint8],
        camera_id: str
    ) -> tuple[NDArray[np.uint8], DetectionResult]:
        """Process a video frame for fall detection.

        Args:
            frame: BGR frame from camera (OpenCV format)
            camera_id: Unique camera identifier

        Returns:
            Tuple of (annotated_frame, detection_result)
        """
        start_time = time.time()
        self.frame_count += 1

        height, width = frame.shape[:2]

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Ensure monotonically increasing timestamps
        current_timestamp_ms = int(time.time() * 1000)
        if current_timestamp_ms <= self._last_timestamp_ms:
            current_timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = current_timestamp_ms

        # Process with PoseLandmarker
        pose_results = self.pose_landmarker.detect_for_video(mp_image, current_timestamp_ms)

        # Process detections
        persons: list[PersonDetection] = []
        fall_detected = False
        fall_person_ids: list[str] = []

        # pose_results.pose_landmarks is a list of landmark lists (one per person)
        for person_idx, landmarks in enumerate(pose_results.pose_landmarks):
            person = self._process_pose(
                landmarks,
                width,
                height,
                camera_id,
                person_idx,
            )
            persons.append(person)

            if person.state == PersonState.FALLING:
                fall_detected = True
                fall_person_ids.append(person.id)

        # Build result
        processing_time_ms = (time.time() - start_time) * 1000
        result = DetectionResult(
            frame_number=self.frame_count,
            persons=persons,
            fall_detected=fall_detected,
            fall_person_ids=fall_person_ids,
            processing_time_ms=processing_time_ms,
        )

        # Annotate frame
        annotated = self._annotate_frame(frame.copy(), result, pose_results)

        return annotated, result

    def _process_pose(
        self,
        landmarks: Any,
        width: int,
        height: int,
        camera_id: str,
        person_idx: int,
    ) -> PersonDetection:
        """Process MediaPipe pose landmarks into a PersonDetection.

        Args:
            landmarks: MediaPipe pose landmarks (list of NormalizedLandmark)
            width: Frame width in pixels
            height: Frame height in pixels
            camera_id: Camera identifier
            person_idx: Index of this person in multi-person detection

        Returns:
            PersonDetection with state classification
        """
        # Extract landmarks to our format
        pose_landmarks = self._extract_landmarks(landmarks)

        # Calculate bounding box from landmarks
        bbox = self._calculate_bounding_box(pose_landmarks)

        # Calculate body angle (torso orientation)
        body_angle = self._calculate_body_angle(pose_landmarks)

        # Get hip center position for velocity tracking
        hip_center_y = self._get_hip_center_y(pose_landmarks)

        # Get or create tracker for this person
        tracker_key = f"{camera_id}_person_{person_idx}"
        tracker = self._get_or_create_tracker(tracker_key)

        # Classify current state
        current_state, confidence = self._classify_state(pose_landmarks, body_angle)

        # Record observation
        if hip_center_y is not None:
            tracker.add_observation(current_state, hip_center_y, body_angle)

        # Check for fall
        final_state = current_state
        if self._is_fall(current_state, tracker, body_angle):
            final_state = PersonState.FALLING
            confidence = max(confidence, 0.85)
            tracker.mark_fall_detected(cooldown_seconds=self.settings.fall_alert_cooldown)

        return PersonDetection(
            id=tracker_key,
            bbox=bbox,
            confidence=confidence,
            state=final_state,
            pose_landmarks=pose_landmarks,
            body_angle=body_angle,
        )

    def _extract_landmarks(self, landmarks: Any) -> list[PoseLandmark]:
        """Convert MediaPipe landmarks to our format."""
        result = []
        for idx, lm in enumerate(landmarks):
            result.append(PoseLandmark(
                id=idx,
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=lm.visibility,
                name=LandmarkIndex(idx).name if idx < 33 else f"POINT_{idx}",
            ))
        return result

    def _calculate_bounding_box(self, landmarks: list[PoseLandmark]) -> BoundingBox:
        """Calculate bounding box from pose landmarks."""
        if not landmarks:
            return BoundingBox(x=0, y=0, width=1, height=1)

        # Filter visible landmarks
        visible = [lm for lm in landmarks if lm.visibility > 0.3]
        if not visible:
            visible = landmarks

        xs = [lm.x for lm in visible]
        ys = [lm.y for lm in visible]

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Add padding
        padding_x = (x_max - x_min) * 0.1
        padding_y = (y_max - y_min) * 0.1

        return BoundingBox(
            x=max(0, x_min - padding_x),
            y=max(0, y_min - padding_y),
            width=min(1, x_max - x_min + 2 * padding_x),
            height=min(1, y_max - y_min + 2 * padding_y),
        )

    def _calculate_body_angle(self, landmarks: list[PoseLandmark]) -> float | None:
        """Calculate body angle from vertical (0° = standing, 90° = horizontal).

        Uses the torso orientation (shoulder midpoint to hip midpoint).
        """
        if len(landmarks) < 25:
            return None

        left_shoulder = landmarks[LandmarkIndex.LEFT_SHOULDER]
        right_shoulder = landmarks[LandmarkIndex.RIGHT_SHOULDER]
        left_hip = landmarks[LandmarkIndex.LEFT_HIP]
        right_hip = landmarks[LandmarkIndex.RIGHT_HIP]

        # Check visibility
        min_visibility = 0.5
        if any(lm.visibility < min_visibility for lm in
               [left_shoulder, right_shoulder, left_hip, right_hip]):
            return None

        # Calculate midpoints
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_mid_x = (left_hip.x + right_hip.x) / 2
        hip_mid_y = (left_hip.y + right_hip.y) / 2

        # Vector from hip to shoulder
        dx = shoulder_mid_x - hip_mid_x
        dy = shoulder_mid_y - hip_mid_y  # Note: Y increases downward

        # Angle from vertical
        # When standing: dy is negative (shoulders above hips), angle ≈ 0
        # When lying: dy is near 0, dx is large, angle ≈ 90
        angle = np.degrees(np.arctan2(abs(dx), -dy))

        return float(max(0, min(90, angle)))

    def _get_hip_center_y(self, landmarks: list[PoseLandmark]) -> float | None:
        """Get the Y coordinate of hip center (for velocity tracking)."""
        if len(landmarks) < 25:
            return None

        left_hip = landmarks[LandmarkIndex.LEFT_HIP]
        right_hip = landmarks[LandmarkIndex.RIGHT_HIP]

        if left_hip.visibility < 0.5 or right_hip.visibility < 0.5:
            return None

        return (left_hip.y + right_hip.y) / 2

    def _classify_state(
        self,
        landmarks: list[PoseLandmark],
        body_angle: float | None
    ) -> tuple[PersonState, float]:
        """Classify person state based on pose geometry.

        Returns:
            Tuple of (state, confidence)
        """
        if body_angle is None:
            return PersonState.UNKNOWN, 0.3

        # Primary classification based on body angle
        if body_angle < 25:
            # Nearly vertical - standing
            return PersonState.STANDING, 0.9
        elif body_angle < 50:
            # Moderate angle - could be sitting or bending
            # Check if shoulders are still above hips
            if self._are_shoulders_above_hips(landmarks):
                return PersonState.SITTING, 0.75
            else:
                return PersonState.LYING, 0.6
        elif body_angle < 70:
            # High angle - likely lying or fallen
            return PersonState.LYING, 0.8
        else:
            # Very horizontal
            return PersonState.LYING, 0.9

    def _are_shoulders_above_hips(self, landmarks: list[PoseLandmark]) -> bool:
        """Check if shoulders are positioned above hips (in image coordinates)."""
        if len(landmarks) < 25:
            return True  # Default assumption

        shoulder_y = (landmarks[LandmarkIndex.LEFT_SHOULDER].y +
                      landmarks[LandmarkIndex.RIGHT_SHOULDER].y) / 2
        hip_y = (landmarks[LandmarkIndex.LEFT_HIP].y +
                 landmarks[LandmarkIndex.RIGHT_HIP].y) / 2

        # In image coordinates, Y increases downward
        # So shoulders above hips means shoulder_y < hip_y
        return shoulder_y < hip_y

    def _get_or_create_tracker(self, tracker_key: str) -> PersonTracker:
        """Get existing tracker or create new one."""
        if tracker_key not in self.person_trackers:
            self._next_person_id += 1
            self.person_trackers[tracker_key] = PersonTracker(
                person_id=self._next_person_id
            )
        return self.person_trackers[tracker_key]

    def _is_fall(
        self,
        current_state: PersonState,
        tracker: PersonTracker,
        body_angle: float | None
    ) -> bool:
        """Determine if a fall has occurred.

        Fall detection criteria (must meet multiple):
        1. Current state is LYING (body near horizontal)
        2. Was upright (standing/sitting) within last 2.5 seconds
        3. Either rapid descent OR rapid angle change detected
        4. Not in cooldown period from previous fall

        This multi-criteria approach reduces false positives from:
        - Person intentionally lying down slowly
        - Person already lying/sitting when camera starts
        - Brief detection glitches
        """
        # Skip if in cooldown
        if tracker.is_in_fall_cooldown():
            return False

        # Must be in lying state
        if current_state != PersonState.LYING:
            return False

        # Must have been upright recently
        if not tracker.was_recently_upright(seconds=2.5):
            return False

        # Body angle must be significant (> 50°)
        if body_angle is not None and body_angle < 50:
            return False

        # Check for rapid motion indicators
        rapid_descent = tracker.detect_rapid_descent(threshold=0.2)
        angle_change_rate = tracker.get_angle_change_rate()
        rapid_angle_change = angle_change_rate is not None and angle_change_rate > 30

        # Need at least one rapid motion indicator
        if not (rapid_descent or rapid_angle_change):
            # Also check state history for standing -> lying transition
            if len(tracker.state_history) >= 5:
                recent = list(tracker.state_history)[-5:]
                had_standing = any(s == PersonState.STANDING for _, s, _ in recent[:3])
                now_lying = current_state == PersonState.LYING

                if had_standing and now_lying:
                    return True

            return False

        logger.info(
            "Fall detected",
            rapid_descent=rapid_descent,
            angle_change_rate=angle_change_rate,
            body_angle=body_angle,
        )

        return True

    def _draw_skeleton(
        self,
        frame: NDArray[np.uint8],
        landmarks: list[PoseLandmark],
        color: tuple[int, int, int] = (0, 255, 0),
    ) -> None:
        """Draw pose skeleton on frame.

        Args:
            frame: BGR frame to draw on
            landmarks: List of pose landmarks
            color: BGR color for skeleton
        """
        height, width = frame.shape[:2]

        # Draw connections
        for start_idx, end_idx in POSE_CONNECTIONS:
            if start_idx >= len(landmarks) or end_idx >= len(landmarks):
                continue

            start = landmarks[start_idx]
            end = landmarks[end_idx]

            if start.visibility > 0.5 and end.visibility > 0.5:
                start_pt = (int(start.x * width), int(start.y * height))
                end_pt = (int(end.x * width), int(end.y * height))
                cv2.line(frame, start_pt, end_pt, color, 2)

        # Draw landmarks
        for lm in landmarks:
            if lm.visibility > 0.5:
                pt = (int(lm.x * width), int(lm.y * height))
                cv2.circle(frame, pt, 3, color, -1)

    def _annotate_frame(
        self,
        frame: NDArray[np.uint8],
        result: DetectionResult,
        pose_results: Any,
    ) -> NDArray[np.uint8]:
        """Draw detection visualizations on frame."""
        height, width = frame.shape[:2]

        # Draw skeletons for each person
        for person in result.persons:
            # Choose color based on state
            colors = {
                PersonState.STANDING: (0, 255, 0),     # Green
                PersonState.SITTING: (255, 200, 0),   # Cyan
                PersonState.LYING: (0, 165, 255),     # Orange
                PersonState.FALLING: (0, 0, 255),     # Red
                PersonState.UNKNOWN: (128, 128, 128), # Gray
            }
            color = colors.get(person.state, (128, 128, 128))

            # Draw skeleton
            if person.pose_landmarks:
                self._draw_skeleton(frame, person.pose_landmarks, color)

            # Draw bounding box
            x1, y1, x2, y2 = person.bbox.to_pixels(width, height)
            thickness = 4 if person.state == PersonState.FALLING else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Draw label background
            label = f"{person.state.value}"
            if person.body_angle is not None:
                label += f" {person.body_angle:.0f}°"
            label += f" ({person.confidence:.0%})"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            label_size = cv2.getTextSize(label, font, font_scale, 2)[0]

            cv2.rectangle(
                frame,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0] + 6, y1),
                color,
                -1,
            )
            cv2.putText(
                frame, label, (x1 + 3, y1 - 5),
                font, font_scale, (255, 255, 255), 2,
            )

        # Draw fall alert banner
        if result.fall_detected:
            banner_text = "CADUTA RILEVATA!"
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size = cv2.getTextSize(banner_text, font, 1.2, 3)[0]
            text_x = (width - text_size[0]) // 2

            # Red banner background
            cv2.rectangle(frame, (0, 5), (width, 65), (0, 0, 200), -1)
            cv2.putText(
                frame, banner_text, (text_x, 50),
                font, 1.2, (255, 255, 255), 3,
            )

        # Draw timestamp
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame, timestamp, (10, height - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )

        # Draw processing time
        fps_text = f"{result.processing_time_ms:.1f}ms"
        cv2.putText(
            frame, fps_text, (width - 70, height - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )

        return frame

    def cleanup(self) -> None:
        """Release resources."""
        self.pose_landmarker.close()
        self.person_trackers.clear()
        logger.info("Detection pipeline cleaned up")
