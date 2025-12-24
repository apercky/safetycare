# SafetyCare - Fall Detection System via IP Cam

## Sommario Progetto

**SafetyCare** è un sistema di rilevamento cadute (fall detection) basato su telecamere IP Tapo C200, che utilizza una pipeline di computer vision combinando **MediaPipe** per pose estimation e **YOLOv8** per object detection e classificazione delle cadute.

### Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend API | Python 3.12 + FastAPI + UV |
| Frontend | Next.js 14 + TypeScript + TailwindCSS |
| Computer Vision | MediaPipe + YOLOv8 (Ultralytics) |
| Streaming | RTSP + WebSocket + MJPEG |
| Containerization | Docker + Docker Compose |
| Notifiche | Telegram Bot API |
| Sicurezza | HTTPS Self-Signed + mDNS |

---

## 1. Architettura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RETE LOCALE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     RTSP      ┌─────────────────────────────────────────┐ │
│  │  Tapo C200   │──────────────▶│           BACKEND CONTAINER              │ │
│  │  (IP Cam)    │  stream2/720p │                                          │ │
│  └──────────────┘               │  ┌─────────────────────────────────────┐ │ │
│                                 │  │         FastAPI Server               │ │ │
│  ┌──────────────┐               │  │                                      │ │ │
│  │  Tapo C200   │──────────────▶│  │  ┌─────────┐    ┌─────────────────┐ │ │ │
│  │  (IP Cam)    │               │  │  │ Stream  │───▶│ Detection       │ │ │ │
│  └──────────────┘               │  │  │ Manager │    │ Pipeline        │ │ │ │
│        ...                      │  │  └─────────┘    │                  │ │ │ │
│                                 │  │                 │ MediaPipe Pose   │ │ │ │
│                                 │  │                 │      ↓           │ │ │ │
│                                 │  │                 │ YOLOv8 Detect    │ │ │ │
│                                 │  │                 │      ↓           │ │ │ │
│                                 │  │                 │ Fall Classifier  │ │ │ │
│                                 │  │                 └─────────────────┘ │ │ │
│                                 │  │                          │          │ │ │
│                                 │  │                          ▼          │ │ │
│                                 │  │  ┌─────────────────────────────────┐│ │ │
│                                 │  │  │ WebSocket/MJPEG Broadcaster     ││ │ │
│                                 │  │  └─────────────────────────────────┘│ │ │
│                                 │  │                          │          │ │ │
│                                 │  │  ┌─────────────────────────────────┐│ │ │
│                                 │  │  │ Telegram Notifier               ││ │ │
│                                 │  │  └─────────────────────────────────┘│ │ │
│                                 │  └─────────────────────────────────────┘ │ │
│                                 └─────────────────────────────────────────┘ │
│                                              │                               │
│                                              │ WebSocket + REST API          │
│                                              ▼                               │
│                                 ┌─────────────────────────────────────────┐ │
│                                 │          FRONTEND CONTAINER              │ │
│                                 │                                          │ │
│                                 │  ┌─────────────────────────────────────┐ │ │
│                                 │  │         Next.js App                  │ │ │
│                                 │  │                                      │ │ │
│                                 │  │  • Live Video Stream                 │ │ │
│                                 │  │  • Bounding Boxes Overlay            │ │ │
│                                 │  │  • Fall Detection Alerts             │ │ │
│                                 │  │  • Camera Management                 │ │ │
│                                 │  │  • Telegram Configuration            │ │ │
│                                 │  │  • Auth (Password)                   │ │ │
│                                 │  └─────────────────────────────────────┘ │ │
│                                 └─────────────────────────────────────────┘ │
│                                              │                               │
│                                              │ HTTPS (safetycare.local)      │
│                                              ▼                               │
│                                 ┌─────────────────────────────────────────┐ │
│                                 │           Browser Client                 │ │
│                                 └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. State Machine Diagram - Detection Pipeline

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    MAIN STATE MACHINE                        │
                    └─────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        IDLE                                  │
                    │  • Sistema in attesa                                         │
                    │  • Nessuna camera attiva                                     │
                    └─────────────────────────────────────────────────────────────┘
                                                │
                                                │ add_camera()
                                                ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    CONNECTING                                │
                    │  • Tentativo connessione RTSP                               │
                    │  • Timeout: 10 secondi                                       │
                    └─────────────────────────────────────────────────────────────┘
                           │                                    │
                           │ success                            │ failure
                           ▼                                    ▼
    ┌──────────────────────────────────────┐    ┌──────────────────────────────────┐
    │              STREAMING                │    │          CONNECTION_ERROR         │
    │  • RTSP stream attivo                 │    │  • Log errore                     │
    │  • Frame acquisition loop             │    │  • Retry con backoff              │
    │  • Pipeline detection attiva          │    │  • Max 5 tentativi                │
    └──────────────────────────────────────┘    └──────────────────────────────────┘
                    │                                           │
                    │ frame_received                            │ retry/give_up
                    ▼                                           ▼
    ┌──────────────────────────────────────┐    ┌──────────────────────────────────┐
    │            PROCESSING                 │    │            DISABLED               │
    │  Per ogni frame:                      │    │  • Camera disabilitata           │
    │  1. Pose Estimation (MediaPipe)       │    │  • Richiede intervento manuale   │
    │  2. Object Detection (YOLOv8)         │    └──────────────────────────────────┘
    │  3. Fall Classification               │
    │  4. Frame Annotation                  │
    │  5. Broadcast to clients              │
    └──────────────────────────────────────┘
                    │
                    │ fall_detected
                    ▼
    ┌──────────────────────────────────────┐
    │           ALERT_TRIGGERED             │
    │  • Invia notifica Telegram           │
    │  • Log evento                         │
    │  • Cooldown 30 secondi               │
    └──────────────────────────────────────┘
                    │
                    │ cooldown_expired
                    ▼
           (torna a STREAMING)
```

---

## 3. Pipeline State Machine - Detection Flow

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │              DETECTION PIPELINE STATE MACHINE                │
                    └─────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                              FRAME ACQUIRED                                  │
    │  Input: Raw BGR frame from RTSP (720p)                                      │
    └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                            PREPROCESSING                                     │
    │  • Resize if needed                                                         │
    │  • Color conversion BGR → RGB (for MediaPipe)                               │
    │  • Frame normalization                                                      │
    └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                         MEDIAPIPE POSE ESTIMATION                            │
    │                                                                              │
    │  Input: RGB Frame                                                           │
    │  Output: 33 body landmarks (x, y, z, visibility)                            │
    │                                                                              │
    │  Key landmarks for fall detection:                                          │
    │  • LEFT_SHOULDER (11), RIGHT_SHOULDER (12)                                  │
    │  • LEFT_HIP (23), RIGHT_HIP (24)                                            │
    │  • LEFT_KNEE (25), RIGHT_KNEE (26)                                          │
    │  • LEFT_ANKLE (27), RIGHT_ANKLE (28)                                        │
    └─────────────────────────────────────────────────────────────────────────────┘
                    │                                   │
                    │ landmarks_found                   │ no_landmarks
                    ▼                                   ▼
    ┌─────────────────────────────────┐   ┌─────────────────────────────────────┐
    │      POSE ANALYSIS               │   │          NO_PERSON_DETECTED          │
    │                                  │   │  • Skip detection                    │
    │  Calculate:                      │   │  • Continue streaming                │
    │  • Body angle (torso vs ground)  │   └─────────────────────────────────────┘
    │  • Hip-Shoulder vector           │
    │  • Knee-Hip ratio                │
    │  • Velocity estimation           │
    └─────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                         YOLOV8 OBJECT DETECTION                              │
    │                                                                              │
    │  Model: yolov8n-pose or custom trained fall detection model                 │
    │  Input: RGB Frame                                                           │
    │  Output: Bounding boxes + class probabilities                               │
    │                                                                              │
    │  Classes:                                                                   │
    │  • person (0) - standard COCO                                               │
    │  • fall (custom) - if using custom model                                    │
    └─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                        FALL CLASSIFICATION                                   │
    │                                                                              │
    │  Combined Analysis:                                                         │
    │  ┌─────────────────────────────────────────────────────────────────────┐   │
    │  │  RULE-BASED CLASSIFIER                                               │   │
    │  │                                                                      │   │
    │  │  Fall Conditions (ALL must be true):                                 │   │
    │  │  1. Body angle > 45° from vertical                                   │   │
    │  │  2. Shoulder Y-coordinate > Hip Y-coordinate                         │   │
    │  │  3. Rapid vertical displacement detected                             │   │
    │  │  4. Person was previously standing (state tracking)                  │   │
    │  │                                                                      │   │
    │  │  State Classification:                                               │   │
    │  │  • STANDING: shoulders above hips, angle < 30°                       │   │
    │  │  • SITTING: shoulders ~= hips level, angle 30-60°                    │   │
    │  │  • LYING: shoulders below hips or angle > 70°                        │   │
    │  │  • FALLING: transition from STANDING to LYING in < 2 sec             │   │
    │  └─────────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
    ┌──────────────┐   ┌──────────────────────┐
    │  NORMAL      │   │   FALL_DETECTED      │
    │              │   │                      │
    │  State:      │   │  State:              │
    │  • Standing  │   │  • Confidence > 0.7  │
    │  • Sitting   │   │  • Duration check    │
    │  • Lying     │   │  • Alert trigger     │
    └──────────────┘   └──────────────────────┘
          │                   │
          └─────────┬─────────┘
                    ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                          FRAME ANNOTATION                                    │
    │                                                                              │
    │  Draw on frame:                                                             │
    │  • Bounding box around person (green/red based on state)                    │
    │  • Pose skeleton (MediaPipe landmarks connected)                            │
    │  • Classification label with confidence                                      │
    │  • Timestamp                                                                │
    └─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                            BROADCAST                                         │
    │                                                                              │
    │  • Encode frame as JPEG                                                     │
    │  • Send via WebSocket to connected clients                                  │
    │  • Include metadata (detections, classifications)                           │
    └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Struttura del Progetto

```
safetycare/
├── docker-compose.yml
├── .env.example
├── certs/
│   ├── generate-certs.sh
│   └── README.md
│
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .python-version
│   ├── Dockerfile
│   │
│   └── src/
│       └── safetycare/
│           ├── __init__.py
│           ├── main.py                 # FastAPI app entry point
│           ├── config.py               # Pydantic settings
│           │
│           ├── api/
│           │   ├── __init__.py
│           │   ├── router.py           # Main API router
│           │   ├── auth.py             # Authentication endpoints
│           │   ├── cameras.py          # Camera CRUD endpoints
│           │   ├── stream.py           # Video streaming endpoints
│           │   ├── telegram.py         # Telegram config endpoints
│           │   └── health.py           # Health check endpoint
│           │
│           ├── core/
│           │   ├── __init__.py
│           │   ├── security.py         # Password generation/validation
│           │   ├── exceptions.py       # Custom exceptions
│           │   └── dependencies.py     # FastAPI dependencies
│           │
│           ├── models/
│           │   ├── __init__.py
│           │   ├── camera.py           # Camera Pydantic models
│           │   ├── detection.py        # Detection result models
│           │   ├── auth.py             # Auth models
│           │   └── telegram.py         # Telegram config models
│           │
│           ├── services/
│           │   ├── __init__.py
│           │   ├── camera_manager.py   # Camera lifecycle management
│           │   ├── rtsp_client.py      # RTSP stream handler
│           │   ├── detection_pipeline.py # ML detection pipeline
│           │   ├── pose_estimator.py   # MediaPipe wrapper
│           │   ├── fall_detector.py    # YOLOv8 + classification
│           │   ├── frame_annotator.py  # Drawing on frames
│           │   ├── broadcaster.py      # WebSocket broadcast
│           │   └── telegram_notifier.py # Telegram notifications
│           │
│           └── utils/
│               ├── __init__.py
│               └── logging.py          # Logging configuration
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── next.config.js
    ├── tailwind.config.ts
    ├── Dockerfile
    │
    ├── public/
    │   └── logo.svg
    │
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx                # Main dashboard
        │   ├── login/
        │   │   └── page.tsx            # Login page
        │   ├── cameras/
        │   │   ├── page.tsx            # Camera list
        │   │   └── [id]/
        │   │       └── page.tsx        # Camera detail/stream
        │   ├── settings/
        │   │   ├── page.tsx            # Settings overview
        │   │   └── telegram/
        │   │       └── page.tsx        # Telegram config
        │   └── setup/
        │       └── page.tsx            # First-run setup
        │
        ├── components/
        │   ├── ui/                     # Shadcn/UI components
        │   ├── VideoStream.tsx         # Live video component
        │   ├── DetectionOverlay.tsx    # Bounding boxes overlay
        │   ├── CameraCard.tsx          # Camera status card
        │   ├── AlertBanner.tsx         # Fall detection alert
        │   └── PasswordDisplay.tsx     # Initial password display
        │
        ├── lib/
        │   ├── api.ts                  # API client
        │   ├── auth.ts                 # Auth utilities
        │   └── websocket.ts            # WebSocket manager
        │
        ├── hooks/
        │   ├── useAuth.ts
        │   ├── useCamera.ts
        │   └── useWebSocket.ts
        │
        └── types/
            ├── camera.ts
            ├── detection.ts
            └── api.ts
```

---

## 5. Configurazione RTSP per Tapo C200

### URL Format

```
# Stream 1 - Full HD (1080p) - più pesante
rtsp://{username}:{password}@{ip_address}:554/stream1

# Stream 2 - HD (720p) - raccomandato per detection
rtsp://{username}:{password}@{ip_address}:554/stream2
```

### Configurazione Camera nell'App Tapo

1. Aprire l'app Tapo
2. Selezionare la camera
3. Andare in **Impostazioni** → **Avanzate** → **Account Camera**
4. Creare un account dedicato (username/password senza caratteri speciali)
5. Annotare l'indirizzo IP della camera (visibile nelle impostazioni di rete)

---

## 6. Flow di Autenticazione

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FIRST RUN FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │  Container      │
    │  First Start    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │  Check if password exists in volume         │
    │  /data/auth/password.hash                   │
    └─────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
  exists          not exists
    │                 │
    │                 ▼
    │       ┌─────────────────────────────────────┐
    │       │  Generate secure password           │
    │       │  • 18 characters                    │
    │       │  • Upper + Lower + Numbers + Special│
    │       │  • Using secrets module             │
    │       └─────────────────────────────────────┘
    │                 │
    │                 ▼
    │       ┌─────────────────────────────────────┐
    │       │  Hash password (bcrypt)             │
    │       │  Store hash in /data/auth/          │
    │       │  Store plaintext temporarily in     │
    │       │  /data/auth/initial_password.txt    │
    │       └─────────────────────────────────────┘
    │                 │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │  User accesses https://safetycare.local     │
    └─────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │  Check if initial_password.txt exists       │
    └─────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
  exists          not exists
    │                 │
    ▼                 ▼
┌───────────────┐  ┌───────────────┐
│ SETUP PAGE    │  │ LOGIN PAGE    │
│               │  │               │
│ Show password │  │ Password      │
│ with copy btn │  │ input field   │
│               │  │               │
│ Instructions: │  │               │
│ "Save this in │  │               │
│ your password │  │               │
│ manager"      │  │               │
│               │  │               │
│ [Continue]    │  │ [Login]       │
└───────────────┘  └───────────────┘
       │                   │
       │ user clicks       │ password validated
       │ continue          │
       ▼                   │
┌───────────────────┐      │
│ Delete            │      │
│ initial_password  │      │
│ .txt              │      │
└───────────────────┘      │
       │                   │
       └─────────┬─────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Generate JWT   │
        │  Set HttpOnly   │
        │  Cookie         │
        └─────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Redirect to    │
        │  Dashboard      │
        └─────────────────┘
```

---

## 7. Telegram Bot Configuration Flow

### Creazione Bot Telegram

1. Aprire Telegram e cercare `@BotFather`
2. Inviare `/newbot`
3. Seguire le istruzioni:
   - Nome del bot: `SafetyCare Alerts`
   - Username del bot: `safetycare_yourname_bot`
4. Copiare il **Bot Token** fornito
5. Creare un gruppo o canale per le notifiche
6. Aggiungere il bot al gruppo
7. Ottenere il **Chat ID**:
   - Inviare un messaggio nel gruppo
   - Visitare `https://api.telegram.org/bot{TOKEN}/getUpdates`
   - Trovare il `chat.id` nella risposta

### API Endpoint per Configurazione

```http
POST /api/v1/telegram/configure
Content-Type: application/json

{
  "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "chat_id": "-1001234567890",
  "enabled": true,
  "alert_cooldown_seconds": 30
}
```

---

## 8. Certificati Self-Signed per mDNS

### Script di Generazione

Il file `certs/generate-certs.sh` genera:
- CA root certificate
- Server certificate per `safetycare.local`
- Istruzioni per installazione CA

### Installazione CA su Client

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain certs/ca.crt
```

**Linux (Ubuntu/Debian):**
```bash
sudo cp certs/ca.crt /usr/local/share/ca-certificates/safetycare-ca.crt
sudo update-ca-certificates
```

**Windows:**
1. Doppio click su `ca.crt`
2. "Installa certificato"
3. Selezionare "Computer locale"
4. Selezionare "Autorità di certificazione radice attendibili"

---

## 9. API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/setup-status` | GET | Check if initial setup is needed |
| `/api/v1/auth/initial-password` | GET | Get initial password (first run only) |
| `/api/v1/auth/login` | POST | Login with password |
| `/api/v1/auth/logout` | POST | Logout (clear cookie) |
| `/api/v1/auth/verify` | GET | Verify current session |

### Cameras

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cameras` | GET | List all cameras |
| `/api/v1/cameras` | POST | Add new camera |
| `/api/v1/cameras/{id}` | GET | Get camera details |
| `/api/v1/cameras/{id}` | PUT | Update camera |
| `/api/v1/cameras/{id}` | DELETE | Remove camera |
| `/api/v1/cameras/{id}/start` | POST | Start streaming |
| `/api/v1/cameras/{id}/stop` | POST | Stop streaming |

### Streaming

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stream/{camera_id}/mjpeg` | GET | MJPEG stream (for img tag) |
| `/api/v1/stream/{camera_id}/ws` | WebSocket | Real-time stream + detections |

### Telegram

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/telegram/config` | GET | Get current configuration |
| `/api/v1/telegram/configure` | POST | Configure Telegram bot |
| `/api/v1/telegram/test` | POST | Send test notification |

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/health/ready` | GET | Readiness probe |

---

## 10. WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket('wss://safetycare.local/api/v1/stream/{camera_id}/ws');
```

### Message Format (Server → Client)

```typescript
interface StreamMessage {
  type: 'frame' | 'detection' | 'alert' | 'status';
  timestamp: string;  // ISO 8601
  camera_id: string;
  payload: FramePayload | DetectionPayload | AlertPayload | StatusPayload;
}

interface FramePayload {
  frame: string;      // Base64 encoded JPEG
  width: number;
  height: number;
  fps: number;
}

interface DetectionPayload {
  persons: PersonDetection[];
  fall_detected: boolean;
  processing_time_ms: number;
}

interface PersonDetection {
  id: number;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  pose: PoseLandmark[];
  state: 'standing' | 'sitting' | 'lying' | 'falling';
  confidence: number;
}

interface AlertPayload {
  type: 'fall_detected';
  person_id: number;
  confidence: number;
  frame_snapshot: string;  // Base64 JPEG
}

interface StatusPayload {
  connected: boolean;
  streaming: boolean;
  error?: string;
}
```

---

## 11. Environment Variables

```env
# Backend
SAFETYCARE_ENV=production
SAFETYCARE_LOG_LEVEL=INFO
SAFETYCARE_DATA_DIR=/data
SAFETYCARE_JWT_SECRET=<auto-generated>
SAFETYCARE_JWT_EXPIRE_HOURS=24

# Detection
SAFETYCARE_DETECTION_CONFIDENCE=0.7
SAFETYCARE_FALL_ALERT_COOLDOWN=30
SAFETYCARE_FRAME_SKIP=2

# YOLO Model
SAFETYCARE_YOLO_MODEL=yolov8n-pose.pt

# Telegram (optional, configured via UI)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Frontend
NEXT_PUBLIC_API_URL=https://safetycare.local/api/v1
NEXT_PUBLIC_WS_URL=wss://safetycare.local/api/v1
```

