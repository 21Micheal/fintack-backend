#!/bin/sh
# start.sh

# Set port
PORT=${PORT:-8000}
echo "🚀 Starting on port $PORT"

# Initialize database
python -c "
import asyncio
import sys
sys.path.insert(0, '/app')

async def init():
    try:
        from app.database import engine, Base
        from app.models.user import User
        from app.models.transaction import Transaction
        from app.models.alert import Alert
        from app.models.ai_cache import AICache
        from app.models.financial_profile import FinancialProfile
        from app.models.advisor_context import AdvisorContext
        from app.models.goal import Goal
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Database ready')
    except Exception as e:
        print(f'⚠️ Note: {e}')

asyncio.run(init())
"

# Start the app
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1