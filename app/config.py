# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # --- App ---
    PROJECT_NAME: str = "Finance Tracker"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    API_BASE_URL: str

    # --- Database ---
    DATABASE_URL: str
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None


    # --- Plaid ---
    PLAID_CLIENT_ID: str
    PLAID_SECRET: str
    PLAID_ENV: str = "sandbox"
    PLAID_REDIRECT_URI: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    ENV: str = "development"

    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str | None = None

    # --- Safaricom M-Pesa ---
    MPESA_ENVIRONMENT: str = "sandbox"
    MPESA_ENABLED: bool = True
    MPESA_CONSUMER_KEY: str
    MPESA_CONSUMER_SECRET: str
    MPESA_SHORTCODE: str = "174379"
    MPESA_PASSKEY: str
    MPESA_CALLBACK_URL: str

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()
