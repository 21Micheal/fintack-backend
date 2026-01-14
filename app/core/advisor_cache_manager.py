# app/core/advisor_cache_manager.py

import json
from datetime import datetime
from app.core.advisor_ai import generate_personalized_advice
from app.core.advisor_context_manager import update_advisor_context

def calculate_change(old_data: dict, new_data: dict) -> float:
    """Compute relative % change between profiles."""
    try:
        old_expenses = float(old_data.get("total_expenses", 0))
        new_expenses = float(new_data.get("total_expenses", 0))
        if old_expenses == 0:
            return 100
        return abs((new_expenses - old_expenses) / old_expenses) * 100
    except Exception:
        return 100  # fallback — trigger regeneration
