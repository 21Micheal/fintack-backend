# app/core/advisor_ai.py
from sqlalchemy.orm import Session
from app.models.transaction import FinancialProfile, AdvisorContext
import openai
import logging
from typing import Optional

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
            logger.info("No financial profiles found, returning default advice")
            return "No financial data available yet to generate advice. Start adding transactions to get personalized recommendations."

        # Validate that we have at least one valid profile
        current_profile = profiles[0]
        if not current_profile:
            logger.warning("Current profile is None, returning default advice")
            return "We're still processing your financial data. Please check back in a moment for personalized advice."

        # Get advisor context
        context = (
            db.query(AdvisorContext)
            .filter(AdvisorContext.user_id == user_id)
            .first()
        )

        # Safely access profile attributes with defaults
        current_income = getattr(current_profile, 'total_income', 0) or 0
        current_expenses = getattr(current_profile, 'total_expenses', 0) or 0
        current_savings = getattr(current_profile, 'savings', 0) or 0
        current_top_category = getattr(current_profile, 'top_category', 'None') or 'None'
        current_month = getattr(current_profile, 'month', 'Current') or 'Current'

        # Get previous profile if available
        previous_profile = profiles[1] if len(profiles) > 1 else None
        previous_income = getattr(previous_profile, 'total_income', 0) if previous_profile else 0
        previous_expenses = getattr(previous_profile, 'total_expenses', 0) if previous_profile else 0
        previous_savings = getattr(previous_profile, 'savings', 0) if previous_profile else 0
        previous_month = getattr(previous_profile, 'month', 'Previous') if previous_profile else 'N/A'

        alert_summary = getattr(context, 'alert_summary', 'No recent alerts') if context else 'No recent alerts'
        ai_summary = getattr(context, 'ai_summary', 'No previous insights') if context else 'No previous insights'

        # Calculate month-over-month changes if we have valid previous data
        changes = {}
        if previous_profile and previous_income > 0 and current_income > 0:
            try:
                income_change = ((current_income - previous_income) / previous_income) * 100
                expense_change = ((current_expenses - previous_expenses) / previous_expenses) * 100 if previous_expenses > 0 else 0
                savings_change = ((current_savings - previous_savings) / previous_savings) * 100 if previous_savings > 0 else 0
                changes = {
                    "income_change": round(income_change, 1),
                    "expense_change": round(expense_change, 1),
                    "savings_change": round(savings_change, 1)
                }
                logger.info(f"Calculated changes: {changes}")
            except (ZeroDivisionError, TypeError) as calc_error:
                logger.warning(f"Error calculating changes: {calc_error}")
                changes = {}

        # Format values for the prompt - FIXED THE STRING FORMATTING ISSUE
        current_income_str = f"KES {current_income:,.2f}" if current_income > 0 else "KES 0.00"
        current_expenses_str = f"KES {current_expenses:,.2f}" if current_expenses > 0 else "KES 0.00"
        current_savings_str = f"KES {current_savings:,.2f}" if current_savings > 0 else "KES 0.00"
        
        previous_income_str = f"KES {previous_income:,.2f}" if previous_income > 0 else "N/A"
        previous_expenses_str = f"KES {previous_expenses:,.2f}" if previous_expenses > 0 else "N/A"
        previous_savings_str = f"KES {previous_savings:,.2f}" if previous_savings > 0 else "N/A"

        # Build the prompt with corrected formatting
        prompt = f"""
        You are a smart financial advisor analyzing user spending patterns.

        USER FINANCIAL CONTEXT:
        - Latest alerts: {alert_summary}
        - Previous AI insights: {ai_summary}

        CURRENT MONTH ({current_month}):
        - Income: {current_income_str}
        - Expenses: {current_expenses_str}
        - Savings: {current_savings_str}
        - Top Spending Category: {current_top_category}

        PREVIOUS MONTH ({previous_month}):
        - Income: {previous_income_str}
        - Expenses: {previous_expenses_str}
        - Savings: {previous_savings_str}

        {f"MONTHLY CHANGES:" if changes else "TREND ANALYSIS:"}
        {f"- Income change: {changes.get('income_change', 0):+.1f}%" if changes else "- Not enough data for trend analysis yet"}
        {f"- Expense change: {changes.get('expense_change', 0):+.1f}%" if changes else ""}
        {f"- Savings change: {changes.get('savings_change', 0):+.1f}%" if changes and changes.get('savings_change') is not None else ""}

        Task: Provide 2-3 short, actionable, and motivational financial recommendations based on this data.
        Focus on specific behavior changes, trend analysis, and practical budgeting improvements.
        Make it personal and relevant to their spending patterns.
        Format as bullet points with clear, concise language.
        Be encouraging and helpful.

        If the user has no transactions yet, provide welcoming advice about getting started with financial tracking.
        If they have low savings, suggest practical ways to increase savings.
        If they have consistent spending, acknowledge good habits.
        """

        logger.info("Calling OpenAI for AI-generated advice")
        logger.debug(f"Prompt sent to OpenAI: {prompt}")
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )

        advice = response.choices[0].message.content.strip()
        logger.info("Successfully generated AI advice")
        return advice

    except Exception as e:
        logger.error(f"Error generating personalized advice: {str(e)}", exc_info=True)
        # Return helpful default advice instead of error message
        return """Based on your current financial setup, here are some general tips to get started:

• **Track your daily expenses** to understand where your money goes
• **Set a monthly savings goal**, even if it's small to begin with  
• **Review your spending categories** regularly to identify patterns
• **Consider using budgeting categories** like Food, Transport, Entertainment

As you add more transactions, I'll provide more personalized recommendations tailored to your spending habits!"""