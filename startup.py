#!/usr/bin/env python3
# startup.py

import asyncio
import os
import sys

def setup():
    """Setup environment and initialize database"""
    print("🚀 Setting up Finance Tracker API...")
    
    # Add app to path
    sys.path.insert(0, '/app')
    
    # Get port
    port = int(os.getenv("PORT", "8000"))
    print(f"🌐 Will start on port: {port}")
    
    return port

async def init_database():
    """Initialize database tables"""
    print("🔄 Initializing database...")
    
    try:
        from app.database import engine, Base
        
        # Import all models to register them with Base
        from app.models.user import User
        from app.models.transaction import Transaction
        from app.models.alert import Alert
        from app.models.ai_cache import AICache
        from app.models.financial_profile import FinancialProfile
        from app.models.advisor_context import AdvisorContext
        from app.models.goal import Goal
        
        print("📊 Models imported successfully")
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Database tables created")
            
    except Exception as e:
        print(f"⚠️ Database initialization note: {e}")
        print("ℹ️ This might be normal if tables already exist")

def start_app(port: int):
    """Start the FastAPI application"""
    print(f"🚀 Starting FastAPI on port {port}...")
    
    import uvicorn
    
    # Use subprocess to start uvicorn
    import subprocess
    import signal
    
    cmd = [
        "uvicorn", 
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--workers", "1"
    ]
    
    print(f"📋 Command: {' '.join(cmd)}")
    
    # Start the process
    process = subprocess.Popen(cmd)
    
    # Handle shutdown
    def signal_handler(sig, frame):
        print("🛑 Received shutdown signal")
        process.terminate()
        process.wait()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait for process
    process.wait()

async def main():
    """Main startup sequence"""
    port = setup()
    await init_database()
    start_app(port)

if __name__ == "__main__":
    asyncio.run(main())
