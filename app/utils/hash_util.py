# app/utils/hash_utils.py
import hashlib
import json

def summarize_transactions(transactions):
    """
    Reduce transaction data into a lightweight summary (category, type, and total).
    """
    if not transactions:
        return []

    summary = []
    for tx in transactions[:10]:  # Only summarize recent few
        summary.append({
            "category": tx.get("category", ""),
            "type": tx.get("transaction_type", ""),
            "amount": round(float(tx.get("amount", 0)), 2)
        })
    return summary


def hash_alert_context(alert, transactions):
    """
    Generate a unique hash for an alert + transaction context.
    """
    tx_summary = summarize_transactions(transactions)
    base_str = f"{alert.title}|{alert.message}|{json.dumps(tx_summary, sort_keys=True)}"
    return hashlib.sha256(base_str.encode()).hexdigest()
