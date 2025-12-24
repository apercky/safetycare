export interface User {
  username: string;
  created_at: string;
}

export type CameraStream = "stream1" | "stream2";
export type CameraStatus = "idle" | "connecting" | "streaming" | "error" | "disabled";

export interface Camera {
  id: string;
  name: string;
  ip_address: string;
  username: string;
  stream: CameraStream;
  port: number;
  enabled: boolean;
  status: CameraStatus;
  last_seen: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraCreate {
  name: string;
  ip_address: string;
  username: string;
  password: string;
  stream?: CameraStream;
  port?: number;
  enabled?: boolean;
}

export interface CameraUpdate {
  name?: string;
  ip_address?: string;
  username?: string;
  password?: string;
  stream?: CameraStream;
  port?: number;
  enabled?: boolean;
}

export interface Detection {
  id: string;
  camera_id: string;
  timestamp: string;
  type: DetectionType;
  confidence: number;
  bounding_box: BoundingBox;
  pose_landmarks?: PoseLandmark[];
  person_state: PersonState;
}

export type DetectionType = "person" | "fall";
export type PersonState = "unknown" | "standing" | "sitting" | "lying" | "falling";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PoseLandmark {
  x: number;
  y: number;
  z: number;
  visibility: number;
  name: string;
}

export interface FallAlert {
  id: string;
  camera_id: string;
  camera_name: string;
  timestamp: string;
  confidence: number;
  snapshot_url?: string;
  acknowledged: boolean;
}

// Response from GET /telegram/config
export interface TelegramConfig {
  configured: boolean;
  enabled: boolean;
  chat_id_masked: string | null;
  alert_cooldown_seconds: number;
}

// Request for POST /telegram/configure
export interface TelegramConfigUpdate {
  bot_token: string;
  chat_id: string;
  enabled?: boolean;
  alert_cooldown_seconds?: number;
}

// WebSocket message types - aligned with backend StreamMessage
export interface WebSocketMessage {
  type: "frame" | "detection" | "alert" | "status";
  camera_id: string;
  payload: unknown;
  timestamp: string;
}

export interface FramePayload {
  frame: string; // base64 encoded JPEG
  width: number;
  height: number;
  fps: number;
}

export interface FrameMessage {
  type: "frame";
  camera_id: string;
  payload: FramePayload;
  timestamp: string;
}

export interface DetectionPayload {
  persons: PersonDetectionResult[];
  fall_detected: boolean;
  processing_time_ms: number;
}

export interface PersonDetectionResult {
  id: number;
  bbox: BoundingBox;
  pose_landmarks: PoseLandmark[];
  state: PersonState;
  confidence: number;
  body_angle: number | null;
  fall_risk_score: number | null;
}

export interface DetectionMessage {
  type: "detection";
  camera_id: string;
  payload: DetectionPayload;
  timestamp: string;
}

export interface AlertPayload {
  type: "fall_detected";
  person_id: number;
  confidence: number;
  frame_snapshot: string; // base64 encoded JPEG
}

export interface AlertMessage {
  type: "alert";
  camera_id: string;
  payload: AlertPayload;
  timestamp: string;
}

export interface StatusPayload {
  connected: boolean;
  streaming: boolean;
  error?: string | null;
  fps?: number | null;
  frame_count?: number;
}

export interface StatusMessage {
  type: "status";
  camera_id: string;
  payload: StatusPayload;
  timestamp: string;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface LoginRequest {
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
}

export interface SetupResponse {
  password: string;
  message: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
}
