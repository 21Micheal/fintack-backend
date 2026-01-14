# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os

Base = declarative_base()

def get_database_url():
    """Get database URL with proper asyncpg format"""
    db_url = os.getenv("DATABASE_URL", "")
    
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Ensure it starts with postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    # Convert to asyncpg
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return db_url

# Create engine
engine = create_async_engine(
    get_database_url(),
    echo=True,
    poolclass=NullPool,  # Use NullPool for serverless
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()