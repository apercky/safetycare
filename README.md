# SafetyCare

Sistema di rilevamento cadute in tempo reale per anziani e persone con mobilità ridotta, basato su telecamere IP e intelligenza artificiale.

## Panoramica

SafetyCare utilizza MediaPipe e YOLOv8 per rilevare automaticamente le cadute da flussi video RTSP di telecamere IP (testato con Tapo C200). Quando viene rilevata una caduta, il sistema può inviare notifiche istantanee via Telegram con snapshot del momento dell'incidente.

### Caratteristiche Principali

- **Rilevamento cadute in tempo reale** con MediaPipe Pose Estimation + YOLOv8
- **Supporto multi-camera** con gestione indipendente per ogni telecamera
- **Notifiche Telegram** con immagine dell'evento
- **Dashboard web** per monitoraggio e configurazione
- **Overlay visivo** con bounding box, skeleton pose e stato della persona
- **Autenticazione sicura** con password auto-generata e JWT

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.12, FastAPI |
| Computer Vision | MediaPipe Tasks API, YOLOv8 |
| Frontend | Next.js 16, React 19, TypeScript |
| UI Components | Shadcn/UI, Tailwind CSS |
| State Management | Zustand, React Query |
| Streaming | RTSP → WebSocket/MJPEG |
| Notifiche | Telegram Bot API |
| Container | Docker, Docker Compose |
| Reverse Proxy | Nginx con SSL |

## Quick Start

### Prerequisiti

- Docker e Docker Compose
- Telecamera IP con supporto RTSP (es. Tapo C200)
- (Opzionale) Bot Telegram per notifiche

### 1. Clona il repository

```bash
git clone https://github.com/your-repo/safetycare.git
cd safetycare
```

### 2. Configura i certificati SSL (opzionale per produzione)

```bash
# Per sviluppo locale, genera certificati self-signed
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=safetycare.local"
```

### 3. Avvia con Docker Compose

```bash
docker compose up --build
```

### 4. Accedi alla dashboard

- **Dashboard**: https://localhost (o https://safetycare.local)
- **API Docs**: http://localhost:8000/api/docs

Al primo accesso, il sistema mostrerà una password generata automaticamente. **Salvala in un password manager** - sarà mostrata una sola volta.

## Sviluppo Locale

### Backend

```bash
cd backend

# Installa UV (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Crea ambiente virtuale e installa dipendenze
uv venv
source .venv/bin/activate
uv sync

# Scarica modello MediaPipe (richiesto)
mkdir -p models
curl -L -o models/pose_landmarker_lite.task \
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

# Avvia server di sviluppo
uvicorn safetycare.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Installa dipendenze
npm install

# Avvia server di sviluppo (Turbopack)
npm run dev
```

Frontend disponibile su http://localhost:3000

## Configurazione

### Variabili d'Ambiente Backend

Crea un file `.env` nella cartella `backend/`:

```env
# Ambiente
SAFETYCARE_ENV=development
SAFETYCARE_LOG_LEVEL=DEBUG
SAFETYCARE_DATA_DIR=./data

# Detection
SAFETYCARE_DETECTION_CONFIDENCE=0.7
SAFETYCARE_FALL_ALERT_COOLDOWN=30
SAFETYCARE_FRAME_SKIP=2

# YOLO
SAFETYCARE_YOLO_MODEL=yolov8n-pose.pt
SAFETYCARE_YOLO_DEVICE=cpu  # cpu, cuda, mps

# Streaming
SAFETYCARE_STREAM_MAX_FPS=15
SAFETYCARE_STREAM_QUALITY=70
```

### Variabili d'Ambiente Frontend

Il frontend usa variabili build-time (in `frontend/.env.local`):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1
```

## Architettura

```
┌─────────────┐     RTSP      ┌──────────────────────────────────────┐
│  Tapo C200  │──────────────▶│            Backend API               │
│  (Camera)   │               │  ┌──────────┐    ┌───────────────┐   │
└─────────────┘               │  │   RTSP   │───▶│   Detection   │   │
                              │  │  Client  │    │   Pipeline    │   │
                              │  └──────────┘    │ (MP + YOLOv8) │   │
                              │                  └───────┬───────┘   │
                              │                          │           │
                              │         ┌────────────────┼───────┐   │
                              │         ▼                ▼       │   │
                              │  ┌──────────┐    ┌───────────┐   │   │
                              │  │ WebSocket│    │  Telegram │   │   │
                              │  │  Stream  │    │  Notifier │   │   │
                              │  └────┬─────┘    └─────┬─────┘   │   │
                              └───────┼────────────────┼─────────┘   │
                                      │                │
                                      ▼                ▼
                              ┌──────────────┐   ┌──────────┐
                              │   Frontend   │   │ Telegram │
                              │  (Next.js)   │   │   App    │
                              └──────────────┘   └──────────┘
```

### Algoritmo di Fall Detection

1. **Person Detection**: YOLOv8 rileva persone nel frame
2. **Pose Estimation**: MediaPipe estrae 33 landmark corporei
3. **State Classification**: Algoritmo rule-based analizza:
   - Angolo del torso (>45° da verticale → possibile caduta)
   - Posizione relativa spalle/anche
   - Velocità di movimento
   - Transizioni di stato (standing → lying in tempo breve)
4. **Alert Generation**: Se `fall_detected=true`, invia notifica Telegram con snapshot

## API Endpoints

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/v1/auth/setup-status` | GET | Stato inizializzazione sistema |
| `/api/v1/auth/login` | POST | Login con password |
| `/api/v1/cameras` | GET/POST | Lista/crea telecamere |
| `/api/v1/cameras/{id}` | GET/PATCH/DELETE | Gestione singola camera |
| `/api/v1/cameras/{id}/start` | POST | Avvia streaming |
| `/api/v1/cameras/{id}/stop` | POST | Ferma streaming |
| `/api/v1/stream/{id}/ws` | WebSocket | Stream video + detection |
| `/api/v1/stream/{id}/mjpeg` | GET | Stream MJPEG |
| `/api/v1/telegram/configure` | POST | Configura notifiche |
| `/api/v1/health` | GET | Health check |

Documentazione completa: http://localhost:8000/api/docs

## Struttura Progetto

```
safetycare/
├── backend/
│   ├── src/safetycare/
│   │   ├── api/           # FastAPI routers
│   │   ├── core/          # Security, config, dependencies
│   │   ├── models/        # Pydantic models
│   │   └── services/      # Business logic (detection, RTSP, Telegram)
│   ├── models/            # ML models (pose_landmarker_lite.task)
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router pages
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── lib/           # API client, WebSocket, auth
│   │   └── types/         # TypeScript interfaces
│   └── package.json
├── nginx/
│   └── nginx.conf         # Reverse proxy config
├── certs/                 # SSL certificates
├── docker-compose.yml
├── CLAUDE.md              # AI assistant instructions
└── README.md
```

## Telecamere Supportate

Testato con:
- **Tapo C200/C210** - Stream RTSP su porta 554
  - `stream1`: 1080p (più pesante)
  - `stream2`: 720p (raccomandato per detection)

Altre telecamere con supporto RTSP dovrebbero funzionare. L'URL RTSP viene costruito automaticamente:
```
rtsp://{username}:{password}@{ip_address}:{port}/{stream}
```

## Troubleshooting

### Il video non appare nel frontend

1. Verifica che la camera sia avviata: `POST /api/v1/cameras/{id}/start`
2. Controlla i log del backend: `docker compose logs -f backend`
3. Verifica la connettività RTSP: `ffplay rtsp://user:pass@ip:554/stream2`

### MediaPipe non funziona su Apple Silicon

Il progetto usa MediaPipe Tasks API che funziona su ARM64. Assicurati di:
1. Avere scaricato il modello `pose_landmarker_lite.task`
2. Usare `mediapipe>=0.10.9`

### Le notifiche Telegram non arrivano

1. Verifica il bot token con `POST /api/v1/telegram/test`
2. Assicurati che il bot sia stato aggiunto al gruppo/chat
3. Controlla che `enabled: true` nella configurazione

### Performance lenta

- Aumenta `SAFETYCARE_FRAME_SKIP` (processa meno frame)
- Riduci `SAFETYCARE_STREAM_QUALITY` (JPEG più compressi)
- Usa `stream2` (720p) invece di `stream1` (1080p)
- Se disponibile, usa GPU: `SAFETYCARE_YOLO_DEVICE=cuda` o `mps`

## License

MIT License - vedi [LICENSE](LICENSE) per dettagli.

## Contributing

1. Fork del repository
2. Crea un branch per la feature (`git checkout -b feature/nuova-funzione`)
3. Commit delle modifiche (`git commit -am 'Aggiunge nuova funzione'`)
4. Push del branch (`git push origin feature/nuova-funzione`)
5. Apri una Pull Request
