# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import os
import ssl

# DEBUG: Log what URL we're using
print(f"🔗 Database URL: {settings.DATABASE_URL[:50]}..." if settings.DATABASE_URL else "❌ DATABASE_URL not set!")

# Convert to async if needed
def get_database_url():
    db_url = settings.DATABASE_URL
    
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Ensure it's postgresql:// format
    if not db_url.startswith("postgresql://"):
        print(f"⚠️ Warning: DATABASE_URL doesn't start with postgresql://: {db_url[:50]}...")
    
    # Convert to asyncpg for async operations
    if db_url.startswith("postgresql://"):
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = db_url
    
    return async_url

# Create engine with SSL for production
def create_engine_with_ssl():
    db_url = get_database_url()
    
    # SSL context for Supabase/Railway
    ssl_context = None
    if settings.ENVIRONMENT == "production":
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    return create_async_engine(
        db_url,
        echo=True,  # Keep echo for debugging
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args={
            "ssl": ssl_context
        } if ssl_context else {}
    )

# Create engine
engine = create_engine_with_ssl()
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()