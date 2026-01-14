#!/bin/sh
# start.sh - Simple startup script for Railway

# Set Python path
export PYTHONPATH=/app:$PYTHONPATH

# Initialize database tables
echo "🔄 Initializing database tables..."
python -c "
import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, '/app')

async def init_tables():
    try:
        from app.database import engine, Base
        from app.models import User, Transaction, Alert, AICache, FinancialProfile, AdvisorContext, Goal
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print('✅ Database tables created successfully')
    except Exception as e:
        print(f'⚠️ Warning during table creation: {e}')
        print('ℹ️ Continuing anyway...')

# Run async function
asyncio.run(init_tables())
"

echo "🚀 Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
