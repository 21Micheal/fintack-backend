# app/core/advisor_ai.py
from sqlalchemy.orm import Session
from app.models.transaction import FinancialProfile, AdvisorContext
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

async def generate_personalized_advice(db: Session, user_id: str) -> str:
    try:
        logger.info(f"Generating personalized advice for user {user_id}")
        
        # Get recent profiles (last 3 months)
        profiles = (
            db.query(FinancialProfile)
            .filter(FinancialProfile.user_id == user_id)
            .order_by(FinancialProfile.month.desc())
            .limit(3)
            .all()
        )

        if not profiles:
            return "No financial data available yet to generate advice. Start adding transactions to get personalized recommendations."

        current_profile = profiles[0]
        if not current_profile:
            return "We're still processing your financial data. Please check back in a moment for personalized advice."

        # Get advisor context
        context = (
            db.query(AdvisorContext)
            .filter(AdvisorContext.user_id == user_id)
            .first()
        )

        # Extract data
        current_income = getattr(current_profile, 'total_income', 0) or 0
        current_expenses = getattr(current_profile, 'total_expenses', 0) or 0
        current_savings = getattr(current_profile, 'savings', 0) or 0
        current_top_category = getattr(current_profile, 'top_category', 'None') or 'None'
        
        # Calculate savings rate
        savings_rate = (current_savings / current_income * 100) if current_income > 0 else 0
        
        # Get previous data for trends
        previous_profile = profiles[1] if len(profiles) > 1 else None
        previous_income = getattr(previous_profile, 'total_income', 0) if previous_profile else 0
        previous_expenses = getattr(previous_profile, 'total_expenses', 0) if previous_profile else 0
        previous_savings = getattr(previous_profile, 'savings', 0) if previous_profile else 0
        
        # Calculate trends
        income_trend = "stable"
        expense_trend = "stable"
        savings_trend = "stable"
        
        if previous_profile and previous_income > 0:
            income_change = ((current_income - previous_income) / previous_income) * 100
            income_trend = "increasing" if income_change > 5 else "decreasing" if income_change < -5 else "stable"
            
            if previous_expenses > 0:
                expense_change = ((current_expenses - previous_expenses) / previous_expenses) * 100
                expense_trend = "increasing" if expense_change > 5 else "decreasing" if expense_change < -5 else "stable"
            
            if previous_savings > 0:
                savings_change = ((current_savings - previous_savings) / previous_savings) * 100
                savings_trend = "increasing" if savings_change > 5 else "decreasing" if savings_change < -5 else "stable"
        
        # Generate advice based on rules
        advice_points = []
        
        # Savings rate advice
        if savings_rate < 10:
            advice_points.append(f"• Your savings rate is {savings_rate:.1f}%, consider aiming for at least 20% by reducing discretionary spending")
        elif savings_rate >= 20:
            advice_points.append(f"• Great work! Your savings rate of {savings_rate:.1f}% is excellent")
        else:
            advice_points.append(f"• Your savings rate is {savings_rate:.1f}%, try to increase it by 5% next month")
        
        # Expense to income ratio
        expense_ratio = (current_expenses / current_income * 100) if current_income > 0 else 0
        if expense_ratio > 80:
            advice_points.append("• Your expenses are high relative to income. Review your top category spending")
        elif expense_ratio < 50:
            advice_points.append("• Your spending is well-controlled relative to income")
        
        # Trend-based advice
        if expense_trend == "increasing" and income_trend != "increasing":
            advice_points.append(f"• Expenses are trending up while income is {income_trend}. Monitor your {current_top_category} spending")
        elif savings_trend == "increasing":
            advice_points.append("• Great progress! Your savings are trending upward")
        
        # Category-specific advice
        category_advice = {
            "Food": "Consider meal planning to reduce food expenses",
            "Transport": "Explore carpooling or public transport options",
            "Entertainment": "Look for free entertainment alternatives",
            "Shopping": "Implement a 24-hour rule before non-essential purchases",
            "Utilities": "Check for better utility provider rates",
            "Mobile": "Review your mobile plan for better value"
        }
        
        if current_top_category in category_advice:
            advice_points.append(f"• {category_advice[current_top_category]}")
        
        # Check for alerts from context
        if context:
            alert_summary = getattr(context, 'alert_summary', '')
            if "overspending" in alert_summary.lower():
                advice_points.append("• You've had overspending alerts. Create a stricter budget for problem categories")
            if "savings" in alert_summary.lower() and "low" in alert_summary.lower():
                advice_points.append("• Set up automatic transfers to savings on payday")
        
        # If no specific advice generated, provide general tips
        if not advice_points:
            advice_points = [
                "• Track all expenses daily to build awareness",
                "• Set specific financial goals for motivation",
                "• Review your budget weekly and adjust as needed",
                "• Celebrate small financial wins to stay motivated"
            ]
        
        # Add motivational message
        if savings_rate > 15:
            motivational = "Keep up the great financial habits!"
        elif len(profiles) < 2:
            motivational = "You're just getting started - consistency is key!"
        else:
            motivational = "Every small improvement adds up over time."
        
        advice = "\n".join(advice_points[:3])  # Limit to 3 points
        advice += f"\n\n{motivational}"
        
        logger.info("Successfully generated rule-based advice")
        return advice

    except Exception as e:
        logger.error(f"Error generating advice: {str(e)}", exc_info=True)
        return """Based on your current financial setup, here are some tips:
        
• Track your daily expenses to understand spending patterns
• Set achievable monthly savings goals
• Review spending categories regularly
• Use budgeting tools to stay on track

As you add more transactions, you'll get more personalized recommendations!"""