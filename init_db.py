# init_db.py
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def init_database():
    """Initialize database with all tables"""
    from app.database import engine, Base
    from app.models import User, Transaction, Alert, AICache, FinancialProfile, AdvisorContext, Goal
    
    print("🔄 Initializing database...")
    
    try:
        async with engine.begin() as conn:
            # Drop all tables (for development only - remove in production)
            # await conn.run_sync(Base.metadata.drop_all)
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        print("✅ Database initialized successfully!")
        print("📊 Tables created:")
        print(f"   - {User.__tablename__}")
        print(f"   - {Transaction.__tablename__}")
        print(f"   - {Alert.__tablename__}")
        print(f"   - {AICache.__tablename__}")
        print(f"   - {FinancialProfile.__tablename__}")
        print(f"   - {AdvisorContext.__tablename__}")
        print(f"   - {Goal.__tablename__}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_database())