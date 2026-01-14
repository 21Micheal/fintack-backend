# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from app.config import settings
import ssl

# For async operations (FastAPI endpoints)
async_engine = create_async_engine(
    settings.async_database_url,
    echo=True if settings.ENVIRONMENT == "development" else False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args={
        "ssl": ssl.create_default_context()
    } if settings.ENVIRONMENT == "production" else {}
)

# For sync operations (alembic migrations)
sync_engine = create_engine(settings.sync_database_url)

AsyncSessionLocal = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()