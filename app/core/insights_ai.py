# app/core/insights_ai.py

from datetime import datetime
from app.utils.cache_refresh import should_refresh
from app.models.transaction import AICache
from app.utils.hash_util import summarize_transactions, hash_alert_context
import openai

async def generate_ai_insight(db, user_id, alert, transactions):
    try:
        tx_summary = summarize_transactions(transactions)
        alert_hash = hash_alert_context(alert, transactions)

        cache_entry = db.query(AICache).filter_by(user_id=user_id, alert_hash=alert_hash).first()

        if cache_entry and not should_refresh(cache_entry, tx_summary):
            print("🧠 Using fresh cached insight")
            return cache_entry.ai_response

        print("🔄 Refreshing AI insight...")

        # Generate updated LLM insight
        prompt = f"""
        Financial Insight Update:
        Alert: "{alert.title}" - {alert.message}
        Transaction context: {tx_summary}

        Provide a concise and actionable recommendation (max 3 sentences).
        """

        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        ai_text = response.choices[0].message.content.strip()

        # If entry exists, update it
        if cache_entry:
            cache_entry.ai_response = ai_text
            cache_entry.transaction_summary = tx_summary
            cache_entry.last_refreshed_at = datetime.utcnow()
            cache_entry.refresh_needed = False
        else:
            cache_entry = AICache(
                user_id=user_id,
                alert_hash=alert_hash,
                alert_title=alert.title,
                alert_message=alert.message,
                transaction_summary=tx_summary,
                ai_response=ai_text,
            )
            db.add(cache_entry)

        db.commit()
        print("💾 Cache updated successfully")

        return ai_text

    except Exception as e:
        print("⚠️ AI Insight refresh failed:", e)
        return None
