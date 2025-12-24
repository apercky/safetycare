# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SafetyCare is a fall detection system using IP cameras (Tapo C200). It combines MediaPipe pose estimation with YOLOv8 object detection for real-time fall detection, with Telegram notifications for alerts.

**Stack**: Python 3.12/FastAPI backend + Next.js 16/React 19/TypeScript frontend + Nginx reverse proxy, all containerized with Docker.

## Build & Run Commands

### Backend (in `backend/` directory)

```bash
# Install dependencies (requires UV package manager)
uv pip install -e ".[dev]"

# Download MediaPipe pose model (required for pose estimation)
curl -L -o models/pose_landmarker_lite.task \
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

# Run development server
uvicorn safetycare.main:app --reload --host 0.0.0.0 --port 8000

# Linting
ruff check src/
ruff format src/

# Type checking
mypy src/

# Run tests
pytest
pytest tests/test_specific.py::test_function  # single test
pytest --cov=safetycare --cov-report=html     # with coverage
```

### Frontend (in `frontend/` directory)

```bash
# Install dependencies
npm install

# Run development server (uses Turbopack)
npm run dev

# Build for production
npm run build

# Linting
npm run lint
```

### Docker (from root directory)

```bash
# Build and run all services
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f backend
```

## Architecture

### Backend Structure (`backend/src/safetycare/`)

- **api/**: FastAPI routers - auth, cameras, stream (MJPEG/WebSocket), telegram, health
- **services/**: Core business logic
  - `detection_pipeline.py`: ML pipeline combining MediaPipe Tasks API + YOLOv8 for fall detection
  - `rtsp_client.py`: RTSP stream handling from IP cameras with auto-reconnection
  - `telegram_notifier.py`: Alert notifications via Telegram Bot API
- **models/**: Pydantic models for request/response validation
  - `camera.py`: Camera configuration with URL-encoded RTSP credentials
  - `detection.py`: Detection results, WebSocket message payloads
- **core/**: Security (bcrypt password hashing, JWT tokens), dependencies, exceptions
- **config.py**: Pydantic BaseSettings for environment variable configuration

### Frontend Structure (`frontend/src/`)

- **app/**: Next.js App Router pages (dashboard, cameras, settings, login, setup)
- **components/**: React components including Shadcn/UI primitives in `ui/`
  - `VideoStream.tsx`: WebSocket-based video stream with detection overlay
- **hooks/**: Custom hooks (useAuth, useCamera, useWebSocket)
- **lib/**: API client, auth utilities (Zustand store), WebSocket manager
- **types/**: TypeScript interfaces aligned with backend Pydantic models

### Key Patterns

- **Streaming**: RTSP input → Frame processing → Detection → WebSocket/MJPEG output
- **Fall Detection**:
  - MediaPipe Tasks API extracts 33 body landmarks (works on Apple Silicon)
  - YOLOv8 detects person bounding boxes
  - Rule-based classifier checks: body angle (>45° from vertical), shoulder/hip positions, velocity, state transitions
  - Fallback to bbox aspect ratio when pose unavailable
- **Auth Flow**: Auto-generated 18-char password on first run, bcrypt hashed, JWT tokens in HttpOnly cookies
- **State Management**: Zustand for frontend global state, React Query for server state
- **WebSocket Protocol**: Messages use `{type, camera_id, payload, timestamp}` format

## Configuration

Backend environment variables (prefix `SAFETYCARE_`):
- `ENV`: development/production (default: production)
- `LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR (default: INFO)
- `DATA_DIR`: Persistent data location (default: /data)
- `DETECTION_CONFIDENCE`: Threshold 0.1-1.0 (default: 0.7)
- `FALL_ALERT_COOLDOWN`: Seconds between alerts (default: 30)
- `FRAME_SKIP`: Process every Nth frame (default: 2)
- `YOLO_MODEL`: Model file (default: yolov8n-pose.pt)
- `YOLO_DEVICE`: cpu/cuda/mps (default: cpu)
- `STREAM_MAX_FPS`: Max frames per second for WebSocket stream (default: 15)
- `STREAM_QUALITY`: JPEG quality 1-100 (default: 70)

## Code Quality

- **Backend**: Ruff (linting + formatting), MyPy (strict mode), pytest
- **Frontend**: ESLint with Next.js config, TypeScript strict mode
- **Line length**: 100 chars (backend)
- **Python imports**: isort via Ruff, first-party package is `safetycare`

## Important Notes

- **MediaPipe on Apple Silicon**: Uses MediaPipe Tasks API (`mediapipe.tasks.python.vision.PoseLandmarker`) instead of legacy `mp.solutions.pose` which doesn't work on ARM64
- **RTSP Credentials**: Special characters in passwords are URL-encoded automatically
- **Camera API**: Uses PATCH for updates (not PUT)
- **WebSocket Messages**: Frontend expects `payload` field (not `data`) containing frame/detection data
