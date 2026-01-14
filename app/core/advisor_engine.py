# app/core/advisor_engine.py
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session

from app.models.transaction import AdvisorContext, FinancialProfile, Transaction as TransactionModel
from app.core.advisor_cache_manager import calculate_change
from app.core.advisor_ai import generate_personalized_advice
from app.core.advisor_context_manager import update_advisor_context


async def analyze_transactions_for_insights(
    transactions: List[Dict[str, Any]],
    db: Optional[Session] = None,
    user_id: Optional[str] = None,
    days_back: int = 90
) -> Dict[str, Any]:
    """
    Analyze transactions to generate actionable insights.
    Optimized for Kenyan M-Pesa transaction patterns.
    
    Can work with:
    - Directly provided transaction list (preferred)
    - Or fetch from database when transactions is empty and db + user_id are provided
    
    Args:
        transactions: List of transaction dictionaries (required parameter)
        db: Optional database session (for fallback fetching)
        user_id: Optional user ID (required when using database fallback)
        days_back: Number of days to look back when fetching from DB (default: 90)
    
    Returns:
        Dict containing analysis metrics, patterns, insights and recommendations
    """
    try:
        # 1. If no transactions provided → try to fetch from database
        if not transactions:
            if not (db and user_id):
                return {
                    "status": "no_data",
                    "message": "No transactions provided and database access not available",
                    "insights": [],
                    "metrics": {},
                    "trends": []
                }

            transactions_query = (
                db.query(TransactionModel)
                .filter(TransactionModel.user_id == user_id)
                .filter(TransactionModel.created_at >= datetime.utcnow() - timedelta(days=days_back))
                .order_by(TransactionModel.created_at.desc())
                .all()
            )

            transactions = [
                {
                    "id": tx.id,
                    "date": tx.created_at.isoformat(),
                    "amount": float(tx.amount),
                    "type": tx.type,
                    "category": tx.category,
                    "description": tx.description,
                    "counterparty": tx.counterparty
                }
                for tx in transactions_query
            ]

        # 2. Still no data?
        if not transactions:
            return {
                "status": "no_data",
                "message": "No transaction data available for analysis",
                "insights": [],
                "metrics": {},
                "trends": []
            }

        # 3. Normalize/prepare transaction data
        structured_tx = [
            {
                "id": str(tx.get("id", f"tx-{i}")),
                "date": tx.get("date", datetime.utcnow().isoformat()),
                "amount": float(Decimal(str(tx.get("amount", 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                "type": tx.get("type", "expense").lower(),
                "category": tx.get("category", "Other").title(),
                "description": tx.get("description", ""),
                "counterparty": tx.get("counterparty", "")
            }
            for i, tx in enumerate(transactions)
        ]

        # ───────────────────────────────────────────────────────
        #                     ANALYSIS LOGIC
        #               (same as original implementation)
        # ───────────────────────────────────────────────────────

        income_transactions = [tx for tx in structured_tx if tx["type"] == "income"]
        expense_transactions = [tx for tx in structured_tx if tx["type"] == "expense"]

        total_income = sum(tx["amount"] for tx in income_transactions)
        total_expenses = sum(tx["amount"] for tx in expense_transactions)
        net_savings = total_income - total_expenses
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0

        # Category analysis
        category_totals = defaultdict(float)
        category_counts = Counter()
        for tx in expense_transactions:
            category = tx["category"]
            category_totals[category] += tx["amount"]
            category_counts[category] += 1

        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        top_categories_formatted = [
            {
                "category": cat,
                "total": amount,
                "percentage": (amount / total_expenses * 100) if total_expenses > 0 else 0,
                "transaction_count": category_counts[cat]
            }
            for cat, amount in top_categories
        ]

        # Time-based analysis
        monthly_data = defaultdict(lambda: {"income": 0.0, "expenses": 0.0, "count": 0})
        daily_patterns = defaultdict(lambda: {"total": 0.0, "count": 0})
        day_of_week_patterns = defaultdict(lambda: {"total": 0.0, "count": 0})

        for tx in structured_tx:
            try:
                tx_date = datetime.fromisoformat(tx["date"].replace("Z", "+00:00"))
                month_key = tx_date.strftime("%Y-%m")
                day_key = tx_date.strftime("%Y-%m-%d")
                day_of_week = tx_date.strftime("%A")

                monthly_data[month_key]["count"] += 1

                if tx["type"] == "income":
                    monthly_data[month_key]["income"] += tx["amount"]
                else:
                    monthly_data[month_key]["expenses"] += tx["amount"]
                    daily_patterns[day_key]["total"] += tx["amount"]
                    daily_patterns[day_key]["count"] += 1
                    day_of_week_patterns[day_of_week]["total"] += tx["amount"]
                    day_of_week_patterns[day_of_week]["count"] += 1

            except (ValueError, AttributeError):
                continue

        # Monthly trends
        sorted_months = sorted(monthly_data.items())
        monthly_trends = []
        if len(sorted_months) >= 2:
            for i in range(1, len(sorted_months)):
                current_month, current = sorted_months[i]
                prev_month, prev = sorted_months[i-1]

                expense_change_pct = 0
                if prev["expenses"] > 0:
                    expense_change_pct = ((current["expenses"] - prev["expenses"]) / prev["expenses"]) * 100

                monthly_trends.append({
                    "month": current_month,
                    "expense_change": round(expense_change_pct, 1),
                    "expense_trend": "increasing" if expense_change_pct > 10 else "decreasing" if expense_change_pct < -10 else "stable",
                    "income": current["income"],
                    "expenses": current["expenses"]
                })

        # Pattern detection
        avg_daily_spending = np.mean([d["total"] for d in daily_patterns.values()]) if daily_patterns else 0
        highest_spending_day = max(daily_patterns.items(), key=lambda x: x[1]["total"], default=None)

        # Counterparty analysis (M-Pesa context)
        counterparty_analysis = defaultdict(float)
        for tx in expense_transactions:
            if tx["counterparty"]:
                counterparty_analysis[tx["counterparty"]] += tx["amount"]

        top_counterparties = sorted(counterparty_analysis.items(), key=lambda x: x[1], reverse=True)[:5]

        # ───────────────────────────────────────────────────────
        #                   INSIGHT GENERATION
        # ───────────────────────────────────────────────────────

        insights = []

        # Savings insight
        if savings_rate < 10:
            insights.append({
                "type": "savings",
                "priority": "high",
                "title": "Low Savings Rate",
                "description": f"Your savings rate is {savings_rate:.1f}%. Aim for at least 20% for better financial health.",
                "action": "Consider automating transfers to savings or money market accounts."
            })

        # Category concentration
        if top_categories_formatted and top_categories_formatted[0]["percentage"] > 40:
            top_cat = top_categories_formatted[0]
            insights.append({
                "type": "spending",
                "priority": "medium",
                "title": "High Concentration in One Category",
                "description": f"{top_cat['category']} accounts for {top_cat['percentage']:.1f}% of expenses.",
                "action": "Review whether this spending aligns with your priorities."
            })

        # Rising expenses trend
        if monthly_trends and monthly_trends[-1]["expense_trend"] == "increasing":
            latest = monthly_trends[-1]
            insights.append({
                "type": "trend",
                "priority": "medium",
                "title": "Rising Expenses",
                "description": f"Expenses rose by {latest['expense_change']:.1f}% compared to previous month.",
                "action": "Monitor discretionary spending closely this month."
            })

        # M-Pesa usage insight
        mpesa_transactions = [tx for tx in structured_tx if "mpesa" in tx.get("description", "").lower()]
        if mpesa_transactions and total_expenses > 0:
            mpesa_total = sum(tx["amount"] for tx in mpesa_transactions)
            mpesa_pct = (mpesa_total / total_expenses) * 100
            insights.append({
                "type": "mpesa",
                "priority": "info",
                "title": "M-Pesa Usage Pattern",
                "description": f"{mpesa_pct:.1f}% of expenses ({len(mpesa_transactions)} transactions) via M-Pesa.",
                "action": "Consider using M-Pesa Lock Savings or M-Shwari for better interest."
            })

        # ───────────────────────────────────────────────────────
        #                     FINAL RESULT
        # ───────────────────────────────────────────────────────

        return {
            "status": "success",
            "period_days": days_back,
            "transaction_count": len(structured_tx),
            "analysis_date": datetime.utcnow().isoformat(),
            "metrics": {
                "total_income": round(total_income, 2),
                "total_expenses": round(total_expenses, 2),
                "net_savings": round(net_savings, 2),
                "savings_rate": round(savings_rate, 1),
                "avg_daily_spending": round(avg_daily_spending, 2),
                "expense_income_ratio": round((total_expenses / total_income * 100) if total_income > 0 else 100, 1)
            },
            "categories": {
                "top_categories": top_categories_formatted,
                "category_count": len(category_totals)
            },
            "patterns": {
                "monthly_trends": monthly_trends,
                "highest_spending_day": {
                    "date": highest_spending_day[0] if highest_spending_day else None,
                    "amount": highest_spending_day[1]["total"] if highest_spending_day else 0
                },
                "day_of_week_analysis": [
                    {
                        "day": day,
                        "total": data["total"],
                        "avg_per_day": data["total"] / data["count"] if data["count"] > 0 else 0
                    }
                    for day, data in sorted(day_of_week_patterns.items())
                ]
            },
            "counterparties": {
                "top_counterparties": [
                    {"name": name, "total": round(amount, 2)}
                    for name, amount in top_counterparties
                ]
            },
            "insights": insights[:8],  # reasonable limit
            "recommendations": generate_recommendations(structured_tx, total_income, total_expenses, savings_rate)
        }

    except Exception as e:
        print(f"❌ Error in transaction analysis: {str(e)}")
        return {
            "status": "error",
            "message": f"Analysis failed: {str(e)}",
            "insights": [],
            "metrics": {},
            "trends": []
        }

def generate_recommendations(transactions: List[Dict], total_income: float, total_expenses: float, savings_rate: float) -> List[Dict]:
    """Generate personalized recommendations based on transaction analysis"""
    recommendations = []
    
    # Savings recommendations
    if savings_rate < 15:
        if savings_rate < 5:
            recommendations.append({
                "category": "savings",
                "title": "Start Small Savings",
                "description": "Begin with saving 5% of your income and gradually increase.",
                "action": "Set up automatic transfer of KES 500-1000 weekly."
            })
        else:
            recommendations.append({
                "category": "savings",
                "title": "Increase Savings Rate",
                "description": "Try to increase your savings rate by 5% each month.",
                "action": "Review one discretionary expense to reduce each month."
            })
    
    # Expense management
    expense_categories = defaultdict(float)
    for tx in transactions:
        if tx["type"] == "expense":
            expense_categories[tx["category"]] += tx["amount"]
    
    if expense_categories:
        largest_category = max(expense_categories.items(), key=lambda x: x[1])
        if largest_category[1] > total_expenses * 0.3:  # More than 30% of expenses
            recommendations.append({
                "category": "spending",
                "title": f"Review {largest_category[0]} Spending",
                "description": f"This category takes {largest_category[1]/total_expenses*100:.1f}% of your expenses.",
                "action": "Look for alternatives or set a monthly limit."
            })
    
    # Income optimization
    if total_income < 50000:  # Assuming KES
        recommendations.append({
            "category": "income",
            "title": "Explore Income Streams",
            "description": "Consider diversifying your income sources.",
            "action": "Look for freelance opportunities or side hustles in your field."
        })
    
    # Debt management (if detected)
    loan_transactions = [tx for tx in transactions if "loan" in tx.get("description", "").lower()]
    if loan_transactions:
        loan_total = sum(tx["amount"] for tx in loan_transactions)
        recommendations.append({
            "category": "debt",
            "title": "Loan Repayment Strategy",
            "description": f"You have {len(loan_transactions)} loan-related transactions.",
            "action": "Consider consolidating loans or prioritizing high-interest debt."
        })
    
    return recommendations


async def get_or_generate_advice(db, user_id, additional_insights: Optional[Dict] = None):
    """
    Get or generate financial advice for a user
    """
    try:
        # Retrieve last context
        context = db.query(AdvisorContext).filter_by(user_id=user_id).first()

        # Get latest profile
        profile = (
            db.query(FinancialProfile)
            .filter(FinancialProfile.user_id == user_id)
            .order_by(FinancialProfile.month.desc())
            .first()
        )

        if not profile:
            return {
                "advice": "Welcome! Start tracking your expenses to get personalized financial advice.",
                "source": "none", 
                "profile": {}
            }

        # Build profile data with fallbacks
        current_profile = {
            "total_income": getattr(profile, 'total_income', 0),
            "total_expenses": getattr(profile, 'total_expenses', 0),
            "savings": getattr(profile, 'savings', 0),
            "top_category": getattr(profile, 'top_category', 'None'),
        }
        
        # Add updated_at if available
        if hasattr(profile, 'updated_at') and profile.updated_at:
            current_profile["last_updated"] = profile.updated_at.isoformat()
        elif hasattr(profile, 'created_at') and profile.created_at:
            current_profile["last_updated"] = profile.created_at.isoformat()
        else:
            current_profile["last_updated"] = datetime.utcnow().isoformat()

        # Merge with additional insights if provided
        if additional_insights:
            current_profile.update({
                "insights": additional_insights.get("insights", []),
                "metrics": additional_insights.get("metrics", {}),
                "recommendations": additional_insights.get("recommendations", [])
            })

        # Decide if we should regenerate (simplified logic)
        should_regenerate = False
        regeneration_reason = ""

        if not context or not context.ai_summary:
            should_regenerate = True
            regeneration_reason = "First time advice generation"
        elif hasattr(context, 'is_stale') and context.is_stale(days=7):
            should_regenerate = True
            regeneration_reason = "Advice is stale"
        else:
            # Simple regeneration logic
            should_regenerate = True  # Always generate fresh for now
            regeneration_reason = "Always generate fresh advice"

        # Generate advice
        if should_regenerate:
            print(f"🧠 Generating advice... ({regeneration_reason})")
            
            # Simple advice generation based on profile
            savings_rate = 0
            if current_profile["total_income"] > 0:
                savings_rate = (current_profile["savings"] / current_profile["total_income"]) * 100
            
            if savings_rate < 0:
                new_advice = "Your expenses exceed your income. Focus on creating a budget and reducing discretionary spending."
            elif savings_rate < 10:
                new_advice = f"Your savings rate is {savings_rate:.1f}%. Try to save at least 20% by automating transfers to savings."
            elif savings_rate < 20:
                new_advice = f"Good progress! You're saving {savings_rate:.1f}% of your income. Consider increasing it gradually."
            else:
                new_advice = f"Excellent! You're saving {savings_rate:.1f}% of your income. Consider investing for long-term growth."
            
            return {
                "advice": new_advice,
                "source": "generated",
                "profile": current_profile,
                "regeneration_reason": regeneration_reason
            }
        else:
            print("♻️ Using cached advice")
            return {
                "advice": context.ai_summary if context else "No advice available",
                "source": "cache",
                "profile": current_profile
            }
            
    except Exception as e:
        print(f"❌ Error in get_or_generate_advice: {str(e)}")
        return {
            "advice": "We're having trouble generating advice right now. General tip: Track all expenses and review weekly.",
            "source": "error",
            "profile": {},
            "error": str(e)
        }