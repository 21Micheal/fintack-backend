# app/utils/cache_refresh.py

from datetime import datetime, timedelta

def context_drift(old_summary, new_summary, threshold=0.3):
    """
    Compare old vs new transaction summaries and measure drift.
    Returns True if change is significant enough to warrant reanalysis.
    """
    if not old_summary or not new_summary:
        return True

    old_total = sum([t.get("amount", 0) for t in old_summary])
    new_total = sum([t.get("amount", 0) for t in new_summary])

    if old_total == 0:
        return True

    drift_ratio = abs(new_total - old_total) / old_total
    return drift_ratio > threshold


def should_refresh(cache_entry, new_summary):
    """
    Check if cache entry should be refreshed based on time or data drift.
    """
    if not cache_entry:
        return True

    # Time-based refresh (e.g., every 30 days)
    if cache_entry.last_refreshed_at < datetime.utcnow() - timedelta(days=30):
        return True

    # Context drift (transactional change)
    if context_drift(cache_entry.transaction_summary, new_summary):
        return True

    return False
