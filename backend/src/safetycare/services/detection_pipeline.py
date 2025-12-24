"""Detection pipeline combining MediaPipe pose estimation and YOLOv8."""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from ultralytics import YOLO

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

# Try to import MediaPipe Tasks API (works on Apple Silicon)
try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        PoseLandmarker,
        PoseLandmarkerOptions,
        RunningMode,
    )

    MEDIAPIPE_AVAILABLE = True
    logger.info("MediaPipe Tasks API available for pose estimation")
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False
    logger.warning(f"MediaPipe not available: {e}")


# MediaPipe landmark indices for key body parts
class LandmarkIndex(int, Enum):
    """MediaPipe pose landmark indices."""

    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28


@dataclass
class PersonTracker:
    """Tracks person state over time for fall detection."""

    person_id: int
    state_history: deque = field(default_factory=lambda: deque(maxlen=30))
    position_history: deque = field(default_factory=lambda: deque(maxlen=10))
    last_standing_time: float = 0.0
    fall_detected_time: float | None = None

    def add_state(self, state: PersonState, position: tuple[float, float]) -> None:
        """Add state observation."""
        self.state_history.append((time.time(), state))
        self.position_history.append((time.time(), position))

        if state == PersonState.STANDING:
            self.last_standing_time = time.time()

    def get_velocity(self) -> float | None:
        """Calculate vertical velocity from position history."""
        if len(self.position_history) < 2:
            return None

        # Get last two positions
        t1, (_, y1) = self.position_history[-2]
        t2, (_, y2) = self.position_history[-1]

        dt = t2 - t1
        if dt <= 0:
            return None

        return (y2 - y1) / dt

    def detect_rapid_fall(self, threshold: float = 0.3) -> bool:
        """Detect rapid downward movement indicative of fall."""
        velocity = self.get_velocity()
        if velocity is None:
            return False

        # Positive velocity means moving down (Y increases downward)
        return velocity > threshold

    def was_recently_standing(self, seconds: float = 3.0) -> bool:
        """Check if person was standing recently."""
        return (time.time() - self.last_standing_time) < seconds


class DetectionPipeline:
    """Combined detection pipeline using MediaPipe and YOLOv8."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize detection pipeline.

        Args:
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.person_trackers: dict[int, PersonTracker] = {}
        self.frame_count = 0
        self.pose_available = False
        self.pose_landmarker: Any = None

        # Initialize MediaPipe Pose using Tasks API
        if MEDIAPIPE_AVAILABLE:
            self._init_mediapipe()
        else:
            logger.info("Running without MediaPipe pose estimation (YOLO-only mode)")

        # Initialize YOLOv8
        self._init_yolo()

        logger.info("Detection pipeline initialized")

    def _init_mediapipe(self) -> None:
        """Initialize MediaPipe PoseLandmarker using Tasks API."""
        # Find the model file
        model_paths = [
            Path(self.settings.data_dir) / "models" / "pose_landmarker_lite.task",
            Path(__file__).parent.parent.parent.parent / "models" / "pose_landmarker_lite.task",
            Path("models") / "pose_landmarker_lite.task",
        ]

        model_path = None
        for path in model_paths:
            if path.exists():
                model_path = path
                break

        if model_path is None:
            logger.warning(
                "MediaPipe pose model not found. Please download it:\n"
                "curl -L -o models/pose_landmarker_lite.task "
                '"https://storage.googleapis.com/mediapipe-models/pose_landmarker/'
                'pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"'
            )
            return

        try:
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=RunningMode.IMAGE,
                num_poses=self.settings.max_persons_per_frame,
                min_pose_detection_confidence=self.settings.mediapipe_min_detection_confidence,
                min_tracking_confidence=self.settings.mediapipe_min_tracking_confidence,
            )
            self.pose_landmarker = PoseLandmarker.create_from_options(options)
            self.pose_available = True
            logger.info(f"MediaPipe PoseLandmarker initialized from {model_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize MediaPipe PoseLandmarker: {e}")
            self.pose_available = False

    def _init_yolo(self) -> None:
        """Initialize YOLO model."""
        try:
            self.yolo = YOLO(self.settings.yolo_model)
            self.yolo.to(self.settings.yolo_device)
            logger.info(f"YOLO model loaded: {self.settings.yolo_model}")
        except Exception as e:
            logger.warning(f"Failed to load custom YOLO model, using default: {e}")
            self.yolo = YOLO("yolov8n.pt")

    def process_frame(
        self, frame: NDArray[np.uint8], camera_id: str
    ) -> tuple[NDArray[np.uint8], DetectionResult]:
        """Process a single frame through the detection pipeline.

        Args:
            frame: BGR frame from camera
            camera_id: Camera identifier for tracking

        Returns:
            Tuple of (annotated_frame, detection_result)
        """
        start_time = time.time()
        self.frame_count += 1

        height, width = frame.shape[:2]

        # Run YOLO detection
        yolo_detections = self._run_yolo(frame)

        # Run MediaPipe pose estimation (if available)
        pose_landmarks_list = []
        if self.pose_available and self.pose_landmarker is not None:
            pose_landmarks_list = self._run_pose_estimation(frame)

        # Combine results
        persons = self._combine_detections(
            yolo_detections, pose_landmarks_list, width, height, camera_id
        )

        # Check for falls
        fall_detected = False
        fall_person_ids = []

        for person in persons:
            if person.state == PersonState.FALLING:
                fall_detected = True
                fall_person_ids.append(person.id)

        # Create result
        processing_time = (time.time() - start_time) * 1000
        result = DetectionResult(
            frame_number=self.frame_count,
            persons=persons,
            fall_detected=fall_detected,
            fall_person_ids=fall_person_ids,
            processing_time_ms=processing_time,
        )

        # Annotate frame
        annotated_frame = self._annotate_frame(frame.copy(), result)

        return annotated_frame, result

    def _run_pose_estimation(self, frame: NDArray[np.uint8]) -> list[list[Any]]:
        """Run MediaPipe pose estimation using Tasks API.

        Returns:
            List of pose landmarks for each detected person
        """
        if not self.pose_available or self.pose_landmarker is None:
            return []

        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Detect poses
            result = self.pose_landmarker.detect(mp_image)

            return result.pose_landmarks if result.pose_landmarks else []
        except Exception as e:
            logger.error(f"Pose estimation error: {e}")
            return []

    def _run_yolo(self, frame: NDArray[np.uint8]) -> list[dict[str, Any]]:
        """Run YOLO detection on frame.

        Returns:
            List of detection dictionaries with bbox and class info
        """
        results = self.yolo(
            frame,
            imgsz=self.settings.yolo_imgsz,
            conf=self.settings.detection_confidence,
            classes=[0],  # Person class only
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": conf,
                        "class": "person",
                    })

        return detections

    def _combine_detections(
        self,
        yolo_detections: list[dict[str, Any]],
        pose_landmarks_list: list[list[Any]],
        width: int,
        height: int,
        camera_id: str,
    ) -> list[PersonDetection]:
        """Combine YOLO and MediaPipe detections."""
        persons = []

        # Use YOLO bounding boxes as primary detection
        for idx, detection in enumerate(yolo_detections[: self.settings.max_persons_per_frame]):
            x1, y1, x2, y2 = detection["bbox"]

            # Normalize coordinates
            bbox = BoundingBox(
                x=x1 / width,
                y=y1 / height,
                width=(x2 - x1) / width,
                height=(y2 - y1) / height,
            )

            # Extract pose landmarks if available for this person
            landmarks = []
            body_angle = None

            # Try to match pose landmarks with YOLO detection
            if idx < len(pose_landmarks_list) and pose_landmarks_list[idx]:
                landmarks = self._extract_landmarks(pose_landmarks_list[idx])
                body_angle = self._calculate_body_angle(landmarks)

            # Classify state (pass bbox for fallback when no pose data)
            state, confidence = self._classify_state(landmarks, body_angle, idx, camera_id, bbox)

            # Get or create tracker
            tracker = self._get_or_create_tracker(idx)

            # Calculate center position
            center_y = (y1 + y2) / 2 / height
            center_x = (x1 + x2) / 2 / width
            tracker.add_state(state, (center_x, center_y))

            # Check for fall
            if self._is_fall(state, tracker, body_angle):
                state = PersonState.FALLING
                confidence = max(confidence, 0.8)

            # Calculate fall risk
            fall_risk = self._calculate_fall_risk(state, tracker, body_angle)

            persons.append(
                PersonDetection(
                    id=idx,
                    bbox=bbox,
                    pose_landmarks=landmarks,
                    state=state,
                    confidence=confidence,
                    body_angle=body_angle,
                    fall_risk_score=fall_risk,
                )
            )

        return persons

    def _extract_landmarks(self, mp_landmarks: list[Any]) -> list[PoseLandmark]:
        """Extract pose landmarks from MediaPipe Tasks API results."""
        landmark_names = [
            "nose", "left_eye_inner", "left_eye", "left_eye_outer",
            "right_eye_inner", "right_eye", "right_eye_outer",
            "left_ear", "right_ear", "mouth_left", "mouth_right",
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_pinky", "right_pinky",
            "left_index", "right_index", "left_thumb", "right_thumb",
            "left_hip", "right_hip", "left_knee", "right_knee",
            "left_ankle", "right_ankle", "left_heel", "right_heel",
            "left_foot_index", "right_foot_index",
        ]

        landmarks = []
        for idx, lm in enumerate(mp_landmarks):
            landmarks.append(
                PoseLandmark(
                    id=idx,
                    name=landmark_names[idx] if idx < len(landmark_names) else f"landmark_{idx}",
                    x=lm.x,
                    y=lm.y,
                    z=lm.z if hasattr(lm, 'z') else 0.0,
                    visibility=lm.visibility if hasattr(lm, 'visibility') else 1.0,
                )
            )

        return landmarks

    def _calculate_body_angle(self, landmarks: list[PoseLandmark]) -> float | None:
        """Calculate body angle from vertical (0 = upright, 90 = horizontal)."""
        if len(landmarks) < 25:
            return None

        # Get shoulder and hip landmarks
        left_shoulder = landmarks[LandmarkIndex.LEFT_SHOULDER]
        right_shoulder = landmarks[LandmarkIndex.RIGHT_SHOULDER]
        left_hip = landmarks[LandmarkIndex.LEFT_HIP]
        right_hip = landmarks[LandmarkIndex.RIGHT_HIP]

        # Check visibility
        min_visibility = 0.5
        if any(
            lm.visibility < min_visibility
            for lm in [left_shoulder, right_shoulder, left_hip, right_hip]
        ):
            return None

        # Calculate midpoints
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_mid_x = (left_hip.x + right_hip.x) / 2
        hip_mid_y = (left_hip.y + right_hip.y) / 2

        # Calculate angle from vertical
        dx = shoulder_mid_x - hip_mid_x
        dy = shoulder_mid_y - hip_mid_y

        # Angle in degrees (0 = vertical, positive = leaning)
        angle = np.degrees(np.arctan2(abs(dx), abs(dy)))

        return float(angle)

    def _classify_state(
        self,
        landmarks: list[PoseLandmark],
        body_angle: float | None,
        person_id: int,
        camera_id: str,
        bbox: BoundingBox | None = None,
    ) -> tuple[PersonState, float]:
        """Classify person state based on pose or bounding box aspect ratio."""
        # If we have landmarks and body angle, use pose-based classification
        if landmarks and body_angle is not None:
            # Rule-based classification
            if body_angle < 30:
                return PersonState.STANDING, 0.9
            elif body_angle < 60:
                # Check shoulder vs hip position
                left_shoulder = landmarks[LandmarkIndex.LEFT_SHOULDER]
                left_hip = landmarks[LandmarkIndex.LEFT_HIP]

                if left_shoulder.y > left_hip.y:  # Shoulder below hip (inverted in image coords)
                    return PersonState.LYING, 0.7
                return PersonState.SITTING, 0.7
            else:
                return PersonState.LYING, 0.85

        # Fallback: use bounding box aspect ratio (less accurate but works without MediaPipe)
        if bbox is not None:
            aspect_ratio = bbox.height / bbox.width if bbox.width > 0 else 1.0
            # Standing person: tall and narrow (aspect ratio > 1.5)
            # Lying person: wide and short (aspect ratio < 1.0)
            if aspect_ratio > 1.5:
                return PersonState.STANDING, 0.6
            elif aspect_ratio > 1.0:
                return PersonState.SITTING, 0.5
            else:
                return PersonState.LYING, 0.5

        return PersonState.UNKNOWN, 0.0

    def _get_or_create_tracker(self, person_id: int) -> PersonTracker:
        """Get or create person tracker."""
        if person_id not in self.person_trackers:
            self.person_trackers[person_id] = PersonTracker(person_id=person_id)
        return self.person_trackers[person_id]

    def _is_fall(
        self, current_state: PersonState, tracker: PersonTracker, body_angle: float | None
    ) -> bool:
        """Determine if a fall has occurred."""
        # Fall detection criteria:
        # 1. Person was recently standing
        # 2. Current state is lying or near-horizontal
        # 3. Rapid downward movement detected
        # 4. Body angle > 60 degrees

        if not tracker.was_recently_standing(seconds=3.0):
            return False

        if current_state not in [PersonState.LYING, PersonState.SITTING]:
            return False

        if body_angle is not None and body_angle < 45:
            return False

        if tracker.detect_rapid_fall(threshold=0.2):
            return True

        # Check state transition
        if len(tracker.state_history) >= 5:
            recent_states = [s for _, s in list(tracker.state_history)[-5:]]
            standing_count = sum(1 for s in recent_states[:3] if s == PersonState.STANDING)
            lying_count = sum(1 for s in recent_states[-2:] if s == PersonState.LYING)

            if standing_count >= 2 and lying_count >= 1:
                return True

        return False

    def _calculate_fall_risk(
        self, state: PersonState, tracker: PersonTracker, body_angle: float | None
    ) -> float:
        """Calculate fall risk score (0-1)."""
        risk = 0.0

        # State-based risk
        state_risks = {
            PersonState.STANDING: 0.1,
            PersonState.SITTING: 0.3,
            PersonState.LYING: 0.6,
            PersonState.FALLING: 1.0,
            PersonState.UNKNOWN: 0.5,
        }
        risk = state_risks.get(state, 0.5)

        # Adjust based on angle
        if body_angle is not None:
            angle_factor = min(body_angle / 90.0, 1.0)
            risk = risk * 0.5 + angle_factor * 0.5

        # Adjust based on velocity
        velocity = tracker.get_velocity()
        if velocity is not None and velocity > 0:
            velocity_factor = min(velocity / 0.5, 1.0)
            risk = min(risk + velocity_factor * 0.3, 1.0)

        return risk

    def _annotate_frame(
        self, frame: NDArray[np.uint8], result: DetectionResult
    ) -> NDArray[np.uint8]:
        """Draw annotations on frame."""
        height, width = frame.shape[:2]

        for person in result.persons:
            # Get pixel coordinates
            x1, y1, x2, y2 = person.bbox.to_pixels(width, height)

            # Color based on state
            colors = {
                PersonState.STANDING: (0, 255, 0),    # Green
                PersonState.SITTING: (255, 255, 0),   # Cyan
                PersonState.LYING: (0, 165, 255),     # Orange
                PersonState.FALLING: (0, 0, 255),     # Red
                PersonState.UNKNOWN: (128, 128, 128), # Gray
            }
            color = colors.get(person.state, (128, 128, 128))

            # Draw bounding box
            thickness = 3 if person.state == PersonState.FALLING else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Draw label
            label = f"{person.state.value} ({person.confidence:.2f})"
            if person.body_angle is not None:
                label += f" {person.body_angle:.0f}°"

            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(
                frame,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                color,
                -1,
            )
            cv2.putText(
                frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            # Draw pose skeleton if available
            if person.pose_landmarks:
                self._draw_pose(frame, person.pose_landmarks, width, height, color)

        # Draw fall alert if detected
        if result.fall_detected:
            alert_text = "! FALL DETECTED"
            text_size = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
            text_x = (width - text_size[0]) // 2
            cv2.rectangle(
                frame,
                (text_x - 10, 10),
                (text_x + text_size[0] + 10, 60),
                (0, 0, 255),
                -1,
            )
            cv2.putText(
                frame,
                alert_text,
                (text_x, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (255, 255, 255),
                3,
            )

        # Draw timestamp
        timestamp_text = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            timestamp_text,
            (10, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

        # Draw processing time
        fps_text = f"{result.processing_time_ms:.1f}ms"
        cv2.putText(
            frame,
            fps_text,
            (width - 80, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

        return frame

    def _draw_pose(
        self,
        frame: NDArray[np.uint8],
        landmarks: list[PoseLandmark],
        width: int,
        height: int,
        color: tuple[int, int, int],
    ) -> None:
        """Draw pose skeleton on frame."""
        # Connection pairs for skeleton
        connections = [
            (11, 12),  # Shoulders
            (11, 13), (13, 15),  # Left arm
            (12, 14), (14, 16),  # Right arm
            (11, 23), (12, 24),  # Torso
            (23, 24),  # Hips
            (23, 25), (25, 27),  # Left leg
            (24, 26), (26, 28),  # Right leg
        ]

        # Draw connections
        for start_idx, end_idx in connections:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start = landmarks[start_idx]
                end = landmarks[end_idx]

                if start.visibility > 0.5 and end.visibility > 0.5:
                    start_point = (int(start.x * width), int(start.y * height))
                    end_point = (int(end.x * width), int(end.y * height))
                    cv2.line(frame, start_point, end_point, color, 2)

        # Draw key landmarks
        key_landmarks = [11, 12, 23, 24, 25, 26, 27, 28]
        for idx in key_landmarks:
            if idx < len(landmarks):
                lm = landmarks[idx]
                if lm.visibility > 0.5:
                    point = (int(lm.x * width), int(lm.y * height))
                    cv2.circle(frame, point, 5, color, -1)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.pose_landmarker is not None:
            self.pose_landmarker.close()
        logger.info("Detection pipeline cleaned up")
