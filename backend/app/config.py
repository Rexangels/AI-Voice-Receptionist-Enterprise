import os


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
    PORT: int = int(os.getenv("PORT", "8000"))
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "/tmp/voice_enterprise.db")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "dev_secret_key")

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "+15550199999")
    HUMAN_ESCALATION_NUMBER: str = os.getenv("HUMAN_ESCALATION_NUMBER", "+15550123456")

    SLACK_NOTIFICATION_WEBHOOK: str = os.getenv("SLACK_NOTIFICATION_WEBHOOK", "")
    DEFAULT_AVG_TICKET_USD: float = float(os.getenv("DEFAULT_AVG_TICKET_USD", "450.0"))
    DEFAULT_CLOSE_RATE: float = float(os.getenv("DEFAULT_CLOSE_RATE", "0.35"))


settings = Settings()
