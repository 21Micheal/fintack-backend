#!/bin/sh
# Simple start.sh that works with sh (not bash)

# Initialize database
echo "🔄 Initializing database..."
python -c "
import asyncio
import sys
sys.path.insert(0, '/app')

async def init_db():
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
        print('✅ Tables created')
        
        # Try to setup relationships
        try:
            from app.models import relationships
            print('✅ Relationships configured')
        except:
            print('⚠️ No relationships module')
            
    except Exception as e:
        print(f'⚠️ {e}')

asyncio.run(init_db())
"

# Start the app
echo "🚀 Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port \${PORT:-8000} --workers 1
