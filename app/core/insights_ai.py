# app/core/insights_ai.py

from datetime import datetime
from typing import List, Dict, Any
from app.utils.cache_refresh import should_refresh
from app.models import AICache, Alert, Transaction
from app.utils.hash_util import summarize_transactions, hash_alert_context
import logging

logger = logging.getLogger(__name__)

class InsightGenerator:
    """Rule-based financial insights generator"""
    
    INSIGHT_TEMPLATES = {
        'high_spending': {
            'patterns': ['spending spike', 'unusual expense', 'above average'],
            'recommendations': [
                "Consider reviewing your {category} expenses this month.",
                "This spending spike in {category} might be worth investigating.",
                "Set a specific budget limit for {category} next month."
            ]
        },
        'low_savings': {
            'patterns': ['savings low', 'savings rate', 'not saving'],
            'recommendations': [
                "Try to increase your savings rate by reducing discretionary spending.",
                "Consider automating small savings transfers each week.",
                "Even saving 5% more can make a big difference over time."
            ]
        },
        'recurring_expense': {
            'patterns': ['subscription', 'recurring', 'monthly'],
            'recommendations': [
                "Review your recurring expenses for any unused services.",
                "Consider annual billing for subscriptions to save money.",
                "Track all subscriptions in one place to avoid surprises."
            ]
        },
        'income_change': {
            'patterns': ['income change', 'salary', 'earnings'],
            'recommendations': [
                "When income changes, update your budget allocation.",
                "Consider saving a portion of any income increase.",
                "Adjust your emergency fund target based on new income levels."
            ]
        },
        'budget_category': {
            'patterns': ['category', 'budget', 'allocation'],
            'recommendations': [
                "Your {category} spending is notable. Consider setting specific limits.",
                "Track {category} expenses weekly to stay on budget.",
                "Look for ways to optimize spending in the {category} category."
            ]
        },
        'general_tip': {
            'patterns': [],
            'recommendations': [
                "Regular budget reviews help maintain financial health.",
                "Small daily savings habits lead to big annual results.",
                "Tracking expenses is the first step to financial control."
            ]
        }
    }
    
    CATEGORY_ADVICE = {
        'Food': "Consider meal planning to reduce food costs.",
        'Transport': "Explore carpooling or public transport alternatives.",
        'Entertainment': "Look for free community events or activities.",
        'Shopping': "Implement a 24-hour waiting period for non-essential purchases.",
        'Utilities': "Check for better rates with utility providers.",
        'Mobile': "Review your mobile plan for better value options.",
        'Rent': "Consider if your housing costs align with income percentage goals.",
        'Healthcare': "Explore preventive care to reduce long-term costs."
    }
    
    @staticmethod
    def extract_category(alert_text: str) -> str:
        """Extract category from alert text if present"""
        common_categories = ['Food', 'Transport', 'Entertainment', 'Shopping', 
                           'Utilities', 'Mobile', 'Rent', 'Healthcare']
        for category in common_categories:
            if category.lower() in alert_text.lower():
                return category
        return None
    
    @staticmethod
    def match_insight_pattern(alert_text: str) -> str:
        """Match alert text to insight patterns"""
        alert_lower = alert_text.lower()
        
        for insight_type, data in InsightGenerator.INSIGHT_TEMPLATES.items():
            for pattern in data['patterns']:
                if pattern in alert_lower:
                    return insight_type
        
        return 'general_tip'
    
    @staticmethod
    def generate_insight(alert_title: str, alert_message: str, tx_summary: str, category: str = None) -> str:
        """Generate a financial insight based on rules"""
        try:
            # Combine alert info for analysis
            alert_text = f"{alert_title} {alert_message}".lower()
            
            # Determine insight type
            insight_type = InsightGenerator.match_insight_pattern(alert_text)
            
            # Get appropriate recommendations
            recommendations = InsightGenerator.INSIGHT_TEMPLATES[insight_type]['recommendations']
            
            # Select a recommendation (rotate through them)
            import hashlib
            alert_hash = hashlib.md5(alert_text.encode()).hexdigest()
            idx = int(alert_hash, 16) % len(recommendations)
            selected_rec = recommendations[idx]
            
            # Insert category if template contains {category}
            if '{category}' in selected_rec and category:
                selected_rec = selected_rec.replace('{category}', category)
            elif '{category}' in selected_rec and not category:
                # Extract category from alert or use default
                extracted_category = InsightGenerator.extract_category(f"{alert_title} {alert_message}")
                if extracted_category:
                    selected_rec = selected_rec.replace('{category}', extracted_category)
                else:
                    selected_rec = selected_rec.replace('{category}', 'this category')
            
            # Add category-specific advice if available
            final_insight = selected_rec
            if category and category in InsightGenerator.CATEGORY_ADVICE:
                final_insight += f" {InsightGenerator.CATEGORY_ADVICE[category]}"
            
            # Add transaction context if provided
            if tx_summary and len(tx_summary) > 10:
                # Extract key metrics from tx_summary
                if 'total' in tx_summary.lower() or 'average' in tx_summary.lower():
                    final_insight += " Review your transaction patterns regularly."
            
            # Ensure insight is concise (3 sentences max)
            sentences = [s.strip() for s in final_insight.split('.') if s.strip()]
            sentences = sentences[:3]  # Limit to 3 sentences
            final_insight = '. '.join(sentences) + '.' if sentences else final_insight
            
            logger.debug(f"Generated {insight_type} insight: {final_insight}")
            return final_insight
            
        except Exception as e:
            logger.error(f"Error generating insight: {e}")
            return "Review your financial patterns and adjust your budget as needed."

async def generate_ai_insight(db, user_id, alert, transactions):
    """Generate financial insight without OpenAI dependency"""
    try:
        tx_summary = summarize_transactions(transactions)
        alert_hash = hash_alert_context(alert, transactions)

        cache_entry = db.query(AICache).filter_by(user_id=user_id, alert_hash=alert_hash).first()

        if cache_entry and not should_refresh(cache_entry, tx_summary):
            logger.debug("Using fresh cached insight")
            return cache_entry.ai_response

        logger.info("Generating new financial insight...")
        
        # Extract category from transactions if available
        category = None
        if transactions:
            # Find most frequent category in recent transactions
            from collections import Counter
            categories = [t.category for t in transactions if t.category]
            if categories:
                category_counts = Counter(categories)
                category = category_counts.most_common(1)[0][0]
        
        # Generate rule-based insight
        insight_generator = InsightGenerator()
        ai_text = insight_generator.generate_insight(
            alert_title=alert.title,
            alert_message=alert.message,
            tx_summary=tx_summary,
            category=category
        )

        # Update or create cache entry
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
        logger.info("Cache updated successfully")

        return ai_text

    except Exception as e:
        logger.error(f"Insight generation failed: {e}", exc_info=True)
        # Return fallback insight
        return "Review your recent transactions and adjust your budget to stay on track."

# Optional: Add batch insight generation for multiple alerts
async def generate_batch_insights(db, user_id, alerts_with_transactions: List[Dict]):
    """Generate insights for multiple alerts at once"""
    insights = {}
    
    for alert_data in alerts_with_transactions:
        alert = alert_data['alert']
        transactions = alert_data['transactions']
        
        try:
            insight = await generate_ai_insight(db, user_id, alert, transactions)
            insights[alert.id] = insight
        except Exception as e:
            logger.error(f"Failed to generate insight for alert {alert.id}: {e}")
            insights[alert.id] = "Analyze your spending patterns for better financial control."
    
    return insights