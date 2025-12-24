# SafetyCare Backend

Backend API per il sistema di rilevamento cadute SafetyCare, basato su FastAPI con pipeline di computer vision MediaPipe + YOLOv8.

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Framework | Python 3.12 + FastAPI |
| Package Manager | UV |
| Computer Vision | MediaPipe Pose + YOLOv8 |
| Streaming | RTSP → WebSocket/MJPEG |
| Autenticazione | JWT (HttpOnly Cookie) + bcrypt |
| Notifiche | Telegram Bot API |

## Quick Start

### 1. Installazione

```bash
# Installa UV (se non presente)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup ambiente
cd backend
uv venv
source .venv/bin/activate  # Linux/macOS
uv sync
```

### 2. Configurazione

Crea il file `.env` nella cartella `backend/`:

```env
SAFETYCARE_ENV=development
SAFETYCARE_LOG_LEVEL=DEBUG
SAFETYCARE_DATA_DIR=./data
SAFETYCARE_HOST=0.0.0.0
SAFETYCARE_PORT=8000
```

### 3. Avvio

```bash
# Con hot-reload
uvicorn safetycare.main:app --reload

# Oppure tramite entry point
safetycare
```

**Server disponibile su:**
- API: http://localhost:8000/api/v1
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

---

## API Reference

### Autenticazione (`/api/v1/auth/`)

Il sistema usa un'autenticazione single-password con JWT tokens memorizzati in cookie HttpOnly.

#### `GET /setup-status`

**Quando usarlo:** All'avvio dell'applicazione frontend per determinare quale pagina mostrare.

```bash
curl http://localhost:8000/api/v1/auth/setup-status
```

**Risposta:**
```json
{
  "is_initialized": false,
  "has_initial_password": true,
  "requires_setup": true
}
```

| Campo | Significato |
|-------|-------------|
| `is_initialized` | `true` se esiste già un hash password salvato |
| `has_initial_password` | `true` se la password in chiaro è ancora disponibile (primo avvio) |
| `requires_setup` | `true` se l'utente deve vedere la pagina di setup |

---

#### `GET /initial-password`

**Quando usarlo:** Solo durante il primo avvio, per mostrare all'utente la password generata automaticamente.

```bash
curl http://localhost:8000/api/v1/auth/initial-password
```

**Risposta (primo avvio):**
```json
{
  "password": "xK9#mP2$vL5@nQ8&wR3",
  "message": "Questa è la tua password di accesso. Salvala nel tuo password manager..."
}
```

**Risposta (setup già completato):**
```json
{
  "detail": "Password iniziale non disponibile. Il setup è già stato completato."
}
```

> ⚠️ **Importante:** Questa password viene mostrata UNA SOLA VOLTA. L'utente deve salvarla prima di procedere.

---

#### `POST /acknowledge-password`

**Quando usarlo:** Dopo che l'utente conferma di aver salvato la password. Questo elimina il file plaintext dal server.

```bash
curl -X POST http://localhost:8000/api/v1/auth/acknowledge-password
```

**Risposta:**
```json
{
  "message": "Password iniziale confermata e rimossa dal sistema."
}
```

---

#### `POST /login`

**Quando usarlo:** Per autenticarsi e ricevere il cookie di sessione JWT.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "xK9#mP2$vL5@nQ8&wR3"}' \
  -c cookies.txt
```

**Risposta (successo):**
```json
{
  "success": true,
  "message": "Accesso effettuato con successo."
}
```

**Risposta (password errata):**
```json
{
  "detail": "Password non valida."
}
```

> Il cookie `access_token` viene settato automaticamente (HttpOnly, Secure, SameSite=Strict).

---

#### `POST /logout`

**Quando usarlo:** Per terminare la sessione ed eliminare il cookie.

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -b cookies.txt
```

---

#### `GET /verify`

**Quando usarlo:** Per verificare se la sessione corrente è ancora valida (es. al caricamento di ogni pagina protetta).

```bash
curl http://localhost:8000/api/v1/auth/verify \
  -b cookies.txt
```

**Risposta:**
```json
{
  "valid": true,
  "expires_in_hours": 23.5
}
```

---

### Cameras (`/api/v1/cameras/`)

Gestione CRUD delle telecamere IP. Tutti gli endpoint richiedono autenticazione.

#### `GET /`

**Quando usarlo:** Per ottenere la lista di tutte le camere configurate.

```bash
curl http://localhost:8000/api/v1/cameras \
  -b cookies.txt
```

**Risposta:**
```json
{
  "cameras": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Soggiorno",
      "ip_address": "192.168.1.100",
      "status": "streaming",
      "enabled": true,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

---

#### `POST /`

**Quando usarlo:** Per aggiungere una nuova telecamera al sistema.

```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "Camera Soggiorno",
    "ip_address": "192.168.1.100",
    "username": "admin",
    "password": "camera_password",
    "rtsp_port": 554,
    "stream_path": "stream2"
  }'
```

**Parametri:**

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `name` | string | ✓ | Nome identificativo della camera |
| `ip_address` | string | ✓ | Indirizzo IP della camera |
| `username` | string | ✓ | Username per autenticazione RTSP |
| `password` | string | ✓ | Password per autenticazione RTSP |
| `rtsp_port` | int | ✗ | Porta RTSP (default: 554) |
| `stream_path` | string | ✗ | Path dello stream (default: "stream2" per 720p) |

**Risposta (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Camera Soggiorno",
  "ip_address": "192.168.1.100",
  "status": "idle",
  "enabled": true
}
```

---

#### `GET /{camera_id}`

**Quando usarlo:** Per ottenere i dettagli completi di una camera specifica.

```bash
curl http://localhost:8000/api/v1/cameras/550e8400-e29b-41d4-a716-446655440000 \
  -b cookies.txt
```

---

#### `PUT /{camera_id}`

**Quando usarlo:** Per modificare la configurazione di una camera esistente.

```bash
curl -X PUT http://localhost:8000/api/v1/cameras/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "Camera Soggiorno (Nuovo Nome)",
    "enabled": false
  }'
```

> Solo i campi specificati vengono aggiornati.

---

#### `DELETE /{camera_id}`

**Quando usarlo:** Per rimuovere definitivamente una camera dal sistema.

```bash
curl -X DELETE http://localhost:8000/api/v1/cameras/550e8400-e29b-41d4-a716-446655440000 \
  -b cookies.txt
```

---

#### `POST /{camera_id}/start`

**Quando usarlo:** Per avviare lo streaming e la detection da una camera.

```bash
curl -X POST http://localhost:8000/api/v1/cameras/550e8400-e29b-41d4-a716-446655440000/start \
  -b cookies.txt
```

**Cosa succede:**
1. Viene stabilita la connessione RTSP alla camera
2. La pipeline di detection (MediaPipe + YOLOv8) viene attivata
3. Lo stato della camera passa a `connecting` → `streaming`

**Risposta:**
```json
{
  "success": true,
  "message": "Streaming avviato per Camera Soggiorno",
  "camera_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

#### `POST /{camera_id}/stop`

**Quando usarlo:** Per fermare lo streaming e liberare le risorse.

```bash
curl -X POST http://localhost:8000/api/v1/cameras/550e8400-e29b-41d4-a716-446655440000/stop \
  -b cookies.txt
```

---

### Streaming (`/api/v1/stream/`)

Endpoint per visualizzare il video in tempo reale. Richiedono autenticazione.

#### `GET /{camera_id}/mjpeg`

**Quando usarlo:** Per incorporare lo stream in un tag `<img>` HTML. Ideale per visualizzazioni semplici.

```html
<img src="http://localhost:8000/api/v1/stream/550e8400.../mjpeg" />
```

```bash
# Test con curl (stream continuo)
curl http://localhost:8000/api/v1/stream/550e8400-e29b-41d4-a716-446655440000/mjpeg \
  -b cookies.txt \
  --output stream.mjpeg
```

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

#### `WebSocket /{camera_id}/ws`

**Quando usarlo:** Per applicazioni che necessitano sia del video che dei dati di detection (bounding boxes, pose, alert).

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/stream/550e8400.../ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch(message.type) {
    case 'frame':
      // message.payload.frame = base64 JPEG
      // message.payload.width, height, fps
      break;
    case 'detection':
      // message.payload.persons = array di PersonDetection
      // message.payload.fall_detected = boolean
      // message.payload.processing_time_ms
      break;
    case 'alert':
      // message.payload.person_id
      // message.payload.confidence
      // message.payload.frame_snapshot = base64 JPEG
      break;
    case 'status':
      // message.payload.connected, streaming, fps
      break;
  }
};
```

**Tipi di messaggio:**

| Tipo | Descrizione | Frequenza |
|------|-------------|-----------|
| `frame` | Frame video codificato base64 | Ogni frame (max 15 fps) |
| `detection` | Risultati detection (persone, pose, stato) | Ogni frame processato |
| `alert` | Notifica caduta rilevata | Solo quando `fall_detected=true` |
| `status` | Stato connessione | Heartbeat ogni 30s |

---

#### `GET /{camera_id}/snapshot`

**Quando usarlo:** Per ottenere una singola immagine JPEG (es. anteprima, thumbnail).

```bash
curl http://localhost:8000/api/v1/stream/550e8400-e29b-41d4-a716-446655440000/snapshot \
  -b cookies.txt \
  --output snapshot.jpg
```

---

### Telegram (`/api/v1/telegram/`)

Configurazione delle notifiche Telegram per gli alert di caduta.

#### `GET /instructions`

**Quando usarlo:** Per mostrare all'utente come creare e configurare un bot Telegram.

```bash
curl http://localhost:8000/api/v1/telegram/instructions
```

> Questo endpoint NON richiede autenticazione.

---

#### `GET /config`

**Quando usarlo:** Per vedere se Telegram è configurato e quale chat ID è in uso.

```bash
curl http://localhost:8000/api/v1/telegram/config \
  -b cookies.txt
```

**Risposta:**
```json
{
  "configured": true,
  "enabled": true,
  "chat_id_masked": "-10***890",
  "alert_cooldown_seconds": 30
}
```

> Il `bot_token` non viene mai esposto per sicurezza.

---

#### `POST /configure`

**Quando usarlo:** Per salvare la configurazione del bot Telegram. Testa automaticamente la connessione.

```bash
curl -X POST http://localhost:8000/api/v1/telegram/configure \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "-1001234567890",
    "enabled": true,
    "alert_cooldown_seconds": 30
  }'
```

**Parametri:**

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `bot_token` | string | Token ottenuto da @BotFather |
| `chat_id` | string | ID della chat/gruppo (negativo per gruppi) |
| `enabled` | bool | Abilita/disabilita notifiche |
| `alert_cooldown_seconds` | int | Secondi minimi tra due alert (5-300) |

---

#### `POST /test`

**Quando usarlo:** Per verificare che la configurazione funzioni inviando un messaggio di test.

```bash
curl -X POST http://localhost:8000/api/v1/telegram/test \
  -b cookies.txt
```

---

#### `DELETE /config`

**Quando usarlo:** Per rimuovere completamente la configurazione Telegram.

```bash
curl -X DELETE http://localhost:8000/api/v1/telegram/config \
  -b cookies.txt
```

---

### Health (`/api/v1/`)

Endpoint per monitoraggio e orchestrazione container.

#### `GET /health`

**Quando usarlo:** Health check base per verificare che il servizio sia attivo.

```bash
curl http://localhost:8000/api/v1/health
```

**Risposta:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600.5
}
```

---

#### `GET /ready`

**Quando usarlo:** Readiness probe per Kubernetes/Docker. Verifica che tutti i servizi siano pronti.

```bash
curl http://localhost:8000/api/v1/ready
```

**Risposta:**
```json
{
  "ready": true,
  "checks": {
    "rtsp_manager": true,
    "password_manager": true,
    "detection_models": true
  }
}
```

---

#### `GET /live`

**Quando usarlo:** Liveness probe per Kubernetes/Docker. Endpoint minimo per verificare che il processo sia vivo.

```bash
curl http://localhost:8000/api/v1/live
```

**Risposta:**
```json
{
  "status": "alive"
}
```

---

## Flussi di Utilizzo

### Flusso Primo Avvio

```
1. GET /auth/setup-status
   └─> requires_setup: true

2. GET /auth/initial-password
   └─> Mostra password all'utente

3. POST /auth/acknowledge-password
   └─> Utente conferma di aver salvato

4. POST /auth/login
   └─> Riceve cookie JWT

5. GET /cameras
   └─> Lista vuota, procedi ad aggiungere camere
```

### Flusso Aggiunta e Avvio Camera

```
1. POST /cameras
   └─> Crea camera con credenziali RTSP

2. POST /cameras/{id}/start
   └─> Avvia streaming

3. GET /stream/{id}/mjpeg  (o WebSocket /ws)
   └─> Visualizza video con detection
```

### Flusso Configurazione Telegram

```
1. GET /telegram/instructions
   └─> Mostra guida creazione bot

2. POST /telegram/configure
   └─> Salva token e chat_id

3. POST /telegram/test
   └─> Verifica funzionamento

4. (Automatico) Quando fall_detected=true
   └─> Invia alert con snapshot al bot
```

---

## Variabili d'Ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `SAFETYCARE_ENV` | production | `development` abilita auto-reload |
| `SAFETYCARE_LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR |
| `SAFETYCARE_DATA_DIR` | /data | Directory per dati persistenti |
| `SAFETYCARE_HOST` | 0.0.0.0 | Bind address |
| `SAFETYCARE_PORT` | 8000 | Porta server |
| `SAFETYCARE_JWT_SECRET` | (auto) | Generato automaticamente se vuoto |
| `SAFETYCARE_JWT_EXPIRE_HOURS` | 24 | Durata sessione in ore |
| `SAFETYCARE_DETECTION_CONFIDENCE` | 0.7 | Soglia minima detection (0.1-1.0) |
| `SAFETYCARE_FALL_ALERT_COOLDOWN` | 30 | Secondi tra alert per camera |
| `SAFETYCARE_FRAME_SKIP` | 2 | Processa ogni N frame |
| `SAFETYCARE_YOLO_MODEL` | yolov8n-pose.pt | Modello YOLO da usare |
| `SAFETYCARE_YOLO_DEVICE` | cpu | `cpu`, `cuda`, `mps` |
| `SAFETYCARE_STREAM_QUALITY` | 80 | Qualità JPEG (10-100) |
| `SAFETYCARE_STREAM_MAX_FPS` | 15 | FPS massimo output |

---

## Troubleshooting

### "Camera non trovata o non attiva"
La camera non è stata avviata. Chiama `POST /cameras/{id}/start` prima di accedere allo stream.

### "Password iniziale non disponibile"
Il setup è già stato completato. Usa la password salvata per fare login.

### "Configurazione non valida" (Telegram)
Verifica che:
- Il `bot_token` sia corretto (formato: `123456789:ABC...`)
- Il `chat_id` sia corretto (negativo per gruppi: `-100...`)
- Il bot sia stato aggiunto al gruppo/chat

### Stream lento o a scatti
Prova a:
- Aumentare `SAFETYCARE_FRAME_SKIP` (processa meno frame)
- Ridurre `SAFETYCARE_STREAM_QUALITY` (file più piccoli)
- Usare `stream2` invece di `stream1` sulla camera (720p vs 1080p)

---

## Sviluppo

### Test

```bash
pytest                                    # Tutti i test
pytest tests/test_auth.py                # Test specifico
pytest --cov=safetycare --cov-report=html # Con coverage
```

### Linting

```bash
ruff check src/                          # Lint
ruff format src/                         # Format
mypy src/                                # Type check
```

### Docker

```bash
docker build -t safetycare-backend .
docker run -p 8000:8000 -v safetycare-data:/data safetycare-backend
```

---

## License

MIT License
