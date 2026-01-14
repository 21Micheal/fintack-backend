#!/bin/bash
# start.sh

# Activate virtual environment if it exists
if [ -d "/app/.venv" ]; then
    source /app/.venv/bin/activate
fi

# Initialize database
echo "🔄 Initializing database..."
python -c "
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def init_db():
    from app.database import engine, Base
    from app.models import User, Transaction, Alert, AICache, FinancialProfile, AdvisorContext, Goal
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Database tables created successfully')
    except Exception as e:
        print(f'❌ Error: {e}')
        sys.exit(1)

asyncio.run(init_db())
"

# Start the application
echo "🚀 Starting application..."
exec uvicorn main:app --host=0.0.0.0 --port=${PORT:-8000} --workers=1
