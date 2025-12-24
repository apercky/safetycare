"""Telegram notification service for fall alerts."""

import asyncio
import base64
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from safetycare.config import Settings, get_settings
from safetycare.models.detection import FallEvent
from safetycare.utils.logging import get_logger

logger = get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token: str
    chat_id: str
    enabled: bool = True
    alert_cooldown_seconds: int = 30

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return bool(self.bot_token and self.chat_id and self.enabled)


class TelegramNotifier:
    """Handles Telegram notifications for fall events."""

    def __init__(self, config: TelegramConfig | None = None, settings: Settings | None = None):
        """Initialize notifier.

        Args:
            config: Telegram configuration
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self._config = config
        self._last_alert_times: dict[str, float] = {}  # camera_id -> timestamp
        self._http_client: httpx.AsyncClient | None = None

    @property
    def config(self) -> TelegramConfig | None:
        """Current configuration."""
        return self._config

    @config.setter
    def config(self, value: TelegramConfig) -> None:
        """Set configuration."""
        self._config = value

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return self._config is not None and self._config.is_valid()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def test_connection(self) -> tuple[bool, str]:
        """Test Telegram bot connection.

        Returns:
            Tuple of (success, message)
        """
        if not self.is_configured():
            return False, "Telegram non configurato"

        try:
            client = await self._get_client()
            url = f"{TELEGRAM_API_BASE.format(token=self._config.bot_token)}/getMe"

            response = await client.get(url)
            data = response.json()

            if data.get("ok"):
                bot_info = data.get("result", {})
                bot_name = bot_info.get("username", "unknown")
                return True, f"Connesso al bot @{bot_name}"
            else:
                error = data.get("description", "Errore sconosciuto")
                return False, f"Errore API Telegram: {error}"

        except httpx.TimeoutException:
            return False, "Timeout connessione a Telegram"
        except Exception as e:
            return False, f"Errore: {str(e)}"

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send text message to configured chat.

        Args:
            text: Message text
            parse_mode: Message parse mode (HTML, Markdown, MarkdownV2)

        Returns:
            True if sent successfully
        """
        if not self.is_configured():
            logger.warning("Telegram non configurato, messaggio non inviato")
            return False

        try:
            client = await self._get_client()
            url = f"{TELEGRAM_API_BASE.format(token=self._config.bot_token)}/sendMessage"

            payload = {
                "chat_id": self._config.chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            response = await client.post(url, json=payload)
            data = response.json()

            if data.get("ok"):
                logger.info("Messaggio Telegram inviato con successo")
                return True
            else:
                error = data.get("description", "Errore sconosciuto")
                logger.error(f"Errore invio messaggio Telegram: {error}")
                return False

        except Exception as e:
            logger.error(f"Errore invio messaggio Telegram: {e}")
            return False

    async def send_photo(
        self,
        image_data: bytes,
        caption: str | None = None,
        filename: str = "alert.jpg",
    ) -> bool:
        """Send photo to configured chat.

        Args:
            image_data: JPEG image bytes
            caption: Optional caption
            filename: Filename for the image

        Returns:
            True if sent successfully
        """
        if not self.is_configured():
            logger.warning("Telegram non configurato, foto non inviata")
            return False

        try:
            client = await self._get_client()
            url = f"{TELEGRAM_API_BASE.format(token=self._config.bot_token)}/sendPhoto"

            files = {"photo": (filename, image_data, "image/jpeg")}
            data = {"chat_id": self._config.chat_id}

            if caption:
                data["caption"] = caption
                data["parse_mode"] = "HTML"

            response = await client.post(url, files=files, data=data)
            result = response.json()

            if result.get("ok"):
                logger.info("Foto Telegram inviata con successo")
                return True
            else:
                error = result.get("description", "Errore sconosciuto")
                logger.error(f"Errore invio foto Telegram: {error}")
                return False

        except Exception as e:
            logger.error(f"Errore invio foto Telegram: {e}")
            return False

    def should_alert(self, camera_id: str) -> bool:
        """Check if alert should be sent based on cooldown.

        Args:
            camera_id: Camera identifier

        Returns:
            True if alert should be sent
        """
        if not self.is_configured():
            return False

        last_alert = self._last_alert_times.get(camera_id, 0)
        cooldown = self._config.alert_cooldown_seconds

        return (time.time() - last_alert) >= cooldown

    def record_alert(self, camera_id: str) -> None:
        """Record that alert was sent for cooldown tracking."""
        self._last_alert_times[camera_id] = time.time()

    async def send_fall_alert(
        self,
        camera_id: str,
        camera_name: str,
        snapshot: bytes | None = None,
        confidence: float = 0.0,
    ) -> bool:
        """Send fall detection alert.

        Args:
            camera_id: Camera identifier
            camera_name: Human-readable camera name
            snapshot: Optional JPEG snapshot
            confidence: Detection confidence

        Returns:
            True if alert was sent
        """
        if not self.should_alert(camera_id):
            logger.debug(f"Alert per camera {camera_id} in cooldown")
            return False

        # Build alert message
        message = (
            "🚨 <b>ALLARME CADUTA RILEVATA</b> 🚨\n\n"
            f"📹 <b>Camera:</b> {camera_name}\n"
            f"⏰ <b>Ora:</b> {time.strftime('%H:%M:%S')}\n"
            f"📊 <b>Confidenza:</b> {confidence:.1%}\n\n"
            "Verifica immediatamente la situazione!"
        )

        success = False

        if snapshot:
            success = await self.send_photo(
                image_data=snapshot,
                caption=message,
                filename=f"fall_alert_{camera_id}_{int(time.time())}.jpg",
            )
        else:
            success = await self.send_message(message)

        if success:
            self.record_alert(camera_id)

        return success

    async def send_test_message(self) -> tuple[bool, str]:
        """Send test message to verify configuration.

        Returns:
            Tuple of (success, message)
        """
        message = (
            "✅ <b>Test SafetyCare</b>\n\n"
            "La configurazione Telegram è corretta!\n"
            "Riceverai notifiche in caso di rilevamento cadute."
        )

        try:
            success = await self.send_message(message)
            if success:
                return True, "Messaggio di test inviato con successo"
            else:
                return False, "Errore nell'invio del messaggio di test"
        except Exception as e:
            return False, f"Errore: {str(e)}"

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


class TelegramConfigManager:
    """Manages Telegram configuration persistence."""

    def __init__(self, config_dir: Path | None = None, settings: Settings | None = None):
        """Initialize config manager.

        Args:
            config_dir: Directory for config storage
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.config_dir = config_dir or self.settings.data_dir
        self.config_file = self.config_dir / "telegram_config.json"

    def load(self) -> TelegramConfig | None:
        """Load configuration from disk.

        Returns:
            Configuration if exists, None otherwise
        """
        if not self.config_file.exists():
            # Check environment variables
            if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
                return TelegramConfig(
                    bot_token=self.settings.telegram_bot_token,
                    chat_id=self.settings.telegram_chat_id,
                    enabled=self.settings.telegram_enabled,
                    alert_cooldown_seconds=self.settings.fall_alert_cooldown,
                )
            return None

        try:
            import json

            data = json.loads(self.config_file.read_text())
            return TelegramConfig(
                bot_token=data.get("bot_token", ""),
                chat_id=data.get("chat_id", ""),
                enabled=data.get("enabled", True),
                alert_cooldown_seconds=data.get(
                    "alert_cooldown_seconds", self.settings.fall_alert_cooldown
                ),
            )
        except Exception as e:
            logger.error(f"Errore caricamento config Telegram: {e}")
            return None

    def save(self, config: TelegramConfig) -> bool:
        """Save configuration to disk.

        Args:
            config: Configuration to save

        Returns:
            True if saved successfully
        """
        try:
            import json

            data = {
                "bot_token": config.bot_token,
                "chat_id": config.chat_id,
                "enabled": config.enabled,
                "alert_cooldown_seconds": config.alert_cooldown_seconds,
            }

            self.config_file.write_text(json.dumps(data, indent=2))
            return True

        except Exception as e:
            logger.error(f"Errore salvataggio config Telegram: {e}")
            return False


# Setup instructions for users
TELEGRAM_SETUP_INSTRUCTIONS = """
## Come configurare il Bot Telegram per SafetyCare

### Passo 1: Crea un nuovo bot
1. Apri Telegram e cerca `@BotFather`
2. Invia il comando `/newbot`
3. Scegli un nome per il bot (es. "SafetyCare Alerts")
4. Scegli uno username per il bot (deve terminare con "bot", es. "safetycare_casa_bot")
5. Copia il **Bot Token** che ti viene fornito

### Passo 2: Crea un gruppo per le notifiche
1. Crea un nuovo gruppo Telegram (o usa uno esistente)
2. Aggiungi il bot appena creato al gruppo
3. Invia un messaggio qualsiasi nel gruppo

### Passo 3: Ottieni il Chat ID
1. Visita questo URL nel browser (sostituisci TOKEN con il tuo):
   `https://api.telegram.org/bot{TOKEN}/getUpdates`
2. Cerca il campo `"chat":{"id":` nella risposta
3. Copia il numero (incluso il segno meno se presente, es. `-1001234567890`)

### Passo 4: Configura SafetyCare
1. Inserisci il Bot Token nel campo dedicato
2. Inserisci il Chat ID nel campo dedicato
3. Clicca su "Testa Connessione" per verificare
4. Salva la configurazione

### Note importanti:
- Il Chat ID per i gruppi inizia sempre con `-100`
- Assicurati che il bot sia amministratore del gruppo se vuoi che possa inviare messaggi
- Puoi usare anche una chat privata: in quel caso il Chat ID sarà un numero positivo
"""
