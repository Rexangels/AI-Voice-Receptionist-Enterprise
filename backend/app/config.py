import os
import json


def _load_dotenv_if_present(filepath: str = ".env") -> None:
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv_if_present()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PORT: int = int(os.getenv("PORT", "3000"))
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "/tmp/voice_enterprise.db")
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    VOICE_ASSISTANT_TENANT_MAP_RAW: str = os.getenv("VOICE_ASSISTANT_TENANT_MAP", "{}")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    HUMAN_ESCALATION_NUMBER: str = os.getenv("HUMAN_ESCALATION_NUMBER", "")

    SLACK_NOTIFICATION_WEBHOOK: str = os.getenv("SLACK_NOTIFICATION_WEBHOOK", "")
    DEFAULT_AVG_TICKET_USD: float = float(os.getenv("DEFAULT_AVG_TICKET_USD", "450.0"))
    DEFAULT_CLOSE_RATE: float = float(os.getenv("DEFAULT_CLOSE_RATE", "0.35"))


settings = Settings()

if settings.APP_ENV.lower() == "production":
    if len(settings.APP_SECRET_KEY) < 32:
        raise RuntimeError("APP_SECRET_KEY must be set to at least 32 characters in production.")
    if len(settings.WEBHOOK_SECRET) < 32:
        raise RuntimeError("WEBHOOK_SECRET must be set to at least 32 characters in production.")
    try:
        assistant_tenants = json.loads(settings.VOICE_ASSISTANT_TENANT_MAP_RAW)
    except json.JSONDecodeError as exc:
        raise RuntimeError("VOICE_ASSISTANT_TENANT_MAP must be a JSON object mapping provider assistant IDs to tenant IDs.") from exc
    if not isinstance(assistant_tenants, dict) or not assistant_tenants:
        raise RuntimeError("Configure VOICE_ASSISTANT_TENANT_MAP before starting production.")
