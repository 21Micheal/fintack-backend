# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from sqlalchemy.pool import NullPool
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
# app/database.py

# app/database.py
def create_engine_for_railway():
    db_url = get_database_url() # This will now be the Railway internal URL
    
    return create_async_engine(
        db_url,
        echo=True,
        # We don't need NullPool or complex SSL for internal Railway traffic
    )
# Create engine
engine = create_engine_for_railway()
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()