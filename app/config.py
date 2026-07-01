from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Recall
    recall_api_key: str = ""
    recall_region: str = "us-west-2"
    recall_webhook_secret: str = ""
    bot_name: str = "Notetaker"

    public_base_url: str = ""

    # DB
    database_url: str

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email: str = ""

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/calendars/google/callback"

    # Microsoft (Outlook) OAuth
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_redirect_uri: str = "http://localhost:8000/calendars/microsoft/callback"

    # How far ahead to scan calendars (hours) and how often to sync (minutes)
    calendar_window_hours: int = 24
    calendar_sync_minutes: int = 5

    @property
    def recall_base_url(self) -> str:
        return f"https://{self.recall_region}.recall.ai/api/v1"


settings = Settings()
