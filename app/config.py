# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, PostgresDsn
from typing import Optional


class Settings(BaseSettings):
    # --- App ---
    PROJECT_NAME: str = "Finance Tracker"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    API_BASE_URL: str = "http://localhost:8000"
    
    # --- Supabase Database (Production) ---
    # This should be your Supabase PostgreSQL connection string
    # Format: postgresql://postgres:[YOUR-PASSWORD]@db.jusvwaobbuiqblwnjler.supabase.co:5432/postgres
    SUPABASE_DB_URL: str
    
    # For backward compatibility, alias DATABASE_URL to SUPABASE_DB_URL
    DATABASE_URL: Optional[str] = None
    
    # --- Supabase API ---
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    
    # --- Auth ---
    SECRET_KEY: str = "LGBTQ"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # --- Environment ---
    ENVIRONMENT: str = "production"  # or "production"
    
    @property
    def sync_database_url(self) -> str:
        """Get SQLAlchemy sync connection URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return self.SUPABASE_DB_URL
    
    @property
    def async_database_url(self) -> str:
        """Get SQLAlchemy async connection URL"""
        url = self.sync_database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()