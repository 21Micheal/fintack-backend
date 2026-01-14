from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
import numpy as np
import pandas as pd
from uuid import UUID
from typing import Union
# Removed sklearn dependency and use numpy.polyfit for simple linear regression fallback
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.transaction import Transaction, User
# Import current user dependency and User model for authentication
from app.api.deps import get_current_user
from prophet import Prophet
import logging
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Insights"])

# ---------- Models ----------
class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"

# RENAMED: Changed from Transaction to TransactionData to avoid conflict
class TransactionData(BaseModel):  # ← Changed name here
    id: Union[int, str, UUID]
    date: str
    amount: float
    type: TransactionType = Field(default=TransactionType.EXPENSE)
    category: str = Field(default="Other")
    description: Optional[str] = None
    
    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            # Try alternative formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    datetime.strptime(v, fmt)
                    return v
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format: {v}. Expected ISO format (YYYY-MM-DD)")

class AIRequest(BaseModel):
    # UPDATED: Changed from Transaction to TransactionData
    transactions: List[TransactionData]  # ← Updated here
    currency: str = "KES"
    savingsGoal: Optional[float] = Field(default=0.0, ge=0)
    
    @validator('transactions')
    def validate_transactions(cls, v):
        if not v:
            raise ValueError("At least one transaction is required")
        return v

# ---------- Helper Functions ----------
def format_currency(amount: float, currency: str) -> str:
    """Format amount with currency symbol and proper formatting"""
    if currency == "KES":
        return f"KES {amount:,.2f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def calculate_percentage_change(current: float, previous: float) -> float:
    """Safely calculate percentage change with zero division protection"""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100

def detect_trend(amounts: List[float]) -> str:
    """Detect spending trend from historical amounts"""
    if len(amounts) < 2:
        return "insufficient data"
    
    # Calculate simple moving average trend
    if len(amounts) >= 3:
        recent_avg = np.mean(amounts[-3:])
        older_avg = np.mean(amounts[:-3]) if len(amounts) > 3 else amounts[0]
        change = calculate_percentage_change(recent_avg, older_avg)
    else:
        change = calculate_percentage_change(amounts[-1], amounts[0])
    
    if change > 15:
        return "rising quickly"
    elif change > 5:
        return "rising"
    elif change < -15:
        return "dropping quickly"
    elif change < -5:
        return "dropping"
    else:
        return "stable"

# UPDATED: Parameter type changed
def categorize_spending(transactions: List[TransactionData]) -> Dict[str, float]:  # ← Updated here
    """Categorize expenses with proper grouping"""
    categories = defaultdict(float)
    
    # Common category groupings for Kenyan context
    category_groups = {
        'Transport': ['uber', 'bolt', 'taxi', 'fuel', 'matatu', 'bus'],
        'Utilities': ['kplc', 'zuku', 'water', 'electricity', 'internet'],
        'Food': ['restaurant', 'supermarket', 'groceries', 'food', 'eating'],
        'Shopping': ['clothing', 'electronics', 'shopping', 'mall'],
        'Entertainment': ['netflix', 'movie', 'concert', 'entertainment'],
        'Bills': ['paybill', 'bill', 'rent', 'loan'],
        'Mobile': ['airtime', 'data', 'safaricom', 'airtel'],
        'Savings': ['savings', 'investment', 'shares']
    }
    
    for tx in transactions:
        if tx.type != TransactionType.EXPENSE:
            continue
            
        amount = float(Decimal(str(tx.amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        category = tx.category.lower()
        description = (tx.description or "").lower()
        
        # Find matching category group
        matched = False
        for group_name, keywords in category_groups.items():
            if any(keyword in category or keyword in description for keyword in keywords):
                categories[group_name] += amount
                matched = True
                break
        
        # If no match, use original category
        if not matched:
            categories[tx.category.title()] += amount
    
    return dict(categories)

# UPDATED: Parameter type changed
def generate_spending_insights(transactions: List[TransactionData], currency: str) -> Dict[str, Any]:  # ← Updated here
    """Generate comprehensive spending insights"""
    expenses = [t for t in transactions if t.type == TransactionType.EXPENSE]
    income = [t for t in transactions if t.type == TransactionType.INCOME]
    
    if not expenses:
        return {"message": "No expense data available for analysis"}
    
    # Basic calculations
    total_expense = sum(t.amount for t in expenses)
    total_income = sum(t.amount for t in income)
    avg_monthly_expense = total_expense / max(1, len(set(t.date[:7] for t in expenses)))  # Per month
    
    # Categorization
    categories = categorize_spending(expenses)
    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Monthly analysis
    monthly_data = defaultdict(lambda: {"expenses": 0.0, "income": 0.0})
    for tx in transactions:
        try:
            month = tx.date[:7]  # YYYY-MM
            if tx.type == TransactionType.EXPENSE:
                monthly_data[month]["expenses"] += tx.amount
            else:
                monthly_data[month]["income"] += tx.amount
        except:
            continue
    
    sorted_months = sorted(monthly_data.items())
    monthly_expenses = [data["expenses"] for _, data in sorted_months]
    
    # Trend detection
    trend = detect_trend(monthly_expenses) if len(monthly_expenses) >= 2 else "insufficient data"
    
    # Overspending detection
    overspending_months = sum(1 for data in monthly_data.values() 
                            if data["expenses"] > data["income"] and data["income"] > 0)
    
    # Savings analysis
    savings = total_income - total_expense
    savings_rate = (savings / total_income * 100) if total_income > 0 else 0
    
    return {
        "total_expense": total_expense,
        "total_income": total_income,
        "avg_monthly_expense": avg_monthly_expense,
        "top_categories": top_categories,
        "trend": trend,
        "overspending_months": overspending_months,
        "savings": savings,
        "savings_rate": savings_rate,
        "monthly_data": dict(monthly_data)
    }

# ---------- /api/ai_insights ----------
@router.post("/ai_insights")
async def ai_insights(request: AIRequest):
    """
    Generate AI-powered financial insights from transaction data
    Optimized for Kenyan M-Pesa transaction patterns
    """
    try:
        logger.info(f"📊 Processing insights for {len(request.transactions)} transactions")
        
        # Validate and process transactions
        validated_transactions = []
        for tx in request.transactions:
            try:
                # Ensure amount is positive
                tx.amount = abs(tx.amount)
                validated_transactions.append(tx)
            except Exception as e:
                logger.warning(f"Skipping invalid transaction {tx.id}: {e}")
                continue
        
        if not validated_transactions:
            raise HTTPException(status_code=400, detail="No valid transactions provided")
        
        # Generate insights
        insights_data = generate_spending_insights(validated_transactions, request.currency)
        
        # Format top categories for display
        top_cats_formatted = []
        for category, amount in insights_data["top_categories"]:
            percentage = (amount / insights_data["total_expense"] * 100) if insights_data["total_expense"] > 0 else 0
            top_cats_formatted.append({
                "category": category,
                "amount": amount,
                "percentage": round(percentage, 1),
                "formatted": f"{category} ({format_currency(amount, request.currency)}, {percentage:.1f}%)"
            })
        
        # Generate human-readable insights
        spending_overview = (
            f"You've spent {format_currency(insights_data['total_expense'], request.currency)} "
            f"with an average of {format_currency(insights_data['avg_monthly_expense'], request.currency)} per month. "
            f"Top spending areas: {', '.join([cat['formatted'] for cat in top_cats_formatted])}."
        )
        
        trend_analysis = (
            f"Your spending trend is {insights_data['trend']}. "
            f"You've spent more than you earned in {insights_data['overspending_months']} month(s)."
        )
        
        savings_analysis = (
            f"Savings: {format_currency(insights_data['savings'], request.currency)} "
            f"({insights_data['savings_rate']:.1f}% of income)."
        )
        
        # Goal projection
        goal_eta = "Set a savings goal for personalized projections."
        if request.savingsGoal > 0 and insights_data["savings"] > 0:
            months_to_goal = (request.savingsGoal - insights_data["savings"]) / insights_data["savings"]
            if months_to_goal > 0:
                goal_eta = f"At current rate, you'll reach your goal in approximately {months_to_goal:.1f} months."
            elif months_to_goal <= 0:
                goal_eta = "Congratulations! You've already reached your savings goal!"
        
        # Income stability
        monthly_incomes = [data["income"] for _, data in insights_data["monthly_data"].items()]
        income_stability = "✅ Income appears stable."
        if len(monthly_incomes) >= 3:
            income_cv = (np.std(monthly_incomes) / np.mean(monthly_incomes)) * 100
            if income_cv > 30:
                income_stability = "⚠️ Income shows significant variability. Consider building a buffer."
        
        # Generate alerts
        alerts = []
        if insights_data["savings_rate"] < 10:
            alerts.append("⚠️ Low savings rate — consider automating monthly transfers to savings.")
        if insights_data["total_expense"] > insights_data["total_income"]:
            alerts.append("🚨 Expenses exceed income — review budget allocations immediately.")
        if insights_data["trend"] in ["rising", "rising quickly"]:
            alerts.append(f"📈 Spending is {insights_data['trend']} — monitor discretionary spending.")
        if insights_data["overspending_months"] >= 2:
            alerts.append("🔴 Multiple months of overspending detected — review recurring expenses.")
        
        insights = {
            "spending_overview": spending_overview,
            "trend_analysis": trend_analysis,
            "savings_analysis": savings_analysis,
            "goal_projection": goal_eta,
            "income_stability": income_stability,
            "alerts": alerts,
            "metrics": {
                "total_income": insights_data["total_income"],
                "total_expenses": insights_data["total_expense"],
                "net_savings": insights_data["savings"],
                "savings_rate": round(insights_data["savings_rate"], 1),
                "avg_monthly_expense": insights_data["avg_monthly_expense"],
                "top_categories": top_cats_formatted
            }
        }
        
        logger.info(f"✅ Generated insights with {len(alerts)} alerts")
        return {"insights": insights}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating insights: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process insights: {str(e)}")

# ---------- /api/ai_spending_trends ----------
@router.post("/ai_spending_trends")
async def ai_spending_trends(request: AIRequest):
    """Analyze spending trends by category with M-Pesa context awareness"""
    try:
        logger.info(f"📈 Analyzing trends for {len(request.transactions)} transactions")
        
        if not request.transactions:
            return {"trends": [], "message": "No transactions to analyze"}
        
        # Convert to DataFrame for easier analysis
        data = []
        for tx in request.transactions:
            try:
                data.append({
                    "id": str(tx.id),
                    "date": tx.date,
                    "amount": abs(tx.amount),
                    "type": tx.type.value,
                    "category": tx.category,
                    "description": tx.description or ""
                })
            except Exception as e:
                logger.warning(f"Skipping transaction {tx.id}: {e}")
                continue
        
        if not data:
            return {"trends": [], "message": "No valid transaction data"}
        
        df = pd.DataFrame(data)
        
        # Parse dates safely
        try:
            df["date"] = pd.to_datetime(df["date"], errors='coerce')
            df = df.dropna(subset=["date"])  # Remove rows with invalid dates
        except Exception as e:
            logger.warning(f"Date parsing issues: {e}")
            return {"trends": ["Unable to analyze trends due to date format issues"]}
        
        # Group by month and category
        df["month"] = df["date"].dt.to_period("M")
        
        # Filter for expenses only
        expense_df = df[df["type"] == "expense"].copy()
        
        if expense_df.empty:
            return {"trends": ["No expense data available for trend analysis"]}
        
        # Aggregate monthly expenses by category
        monthly_expenses = (
            expense_df.groupby(["category", "month"])["amount"]
            .sum()
            .reset_index()
            .sort_values(["category", "month"])
        )
        
        trends = []
        analyzed_categories = set()
        
        for category, group in monthly_expenses.groupby("category"):
            if len(group) < 2:
                # For single month data
                total = group["amount"].sum()
                trends.append(f"📊 Started tracking {category} this month: {format_currency(total, request.currency)}")
                continue
            
            # Sort by month and get last two periods
            group = group.sort_values("month")
            current = group.iloc[-1]
            previous = group.iloc[-2]
            
            # Calculate percentage change
            change_pct = calculate_percentage_change(current["amount"], previous["amount"])
            
            # Generate trend message
            if change_pct > 20:
                emoji = "📈"
                descriptor = "significant increase"
            elif change_pct > 5:
                emoji = "↗️"
                descriptor = "increase"
            elif change_pct < -20:
                emoji = "📉"
                descriptor = "significant decrease"
            elif change_pct < -5:
                emoji = "↘️"
                descriptor = "decrease"
            else:
                emoji = "➡️"
                descriptor = "stable spending"
            
            message = (
                f"{emoji} {category}: {descriptor} ({change_pct:+.1f}%). "
                f"This month: {format_currency(current['amount'], request.currency)} vs "
                f"last: {format_currency(previous['amount'], request.currency)}"
            )
            trends.append(message)
            analyzed_categories.add(category)
        
        # Check for categories with no recent activity
        all_categories = set(expense_df["category"].unique())
        inactive_categories = all_categories - analyzed_categories
        
        for category in inactive_categories:
            last_transaction = expense_df[expense_df["category"] == category]["month"].max()
            if last_transaction:
                months_inactive = (pd.Period.now('M') - last_transaction).n
                if months_inactive >= 2:
                    trends.append(f"⏸️ {category}: No spending for {months_inactive} months")
        
        logger.info(f"✅ Generated {len(trends)} trend insights")
        return {"trends": trends, "analyzed_categories": len(analyzed_categories)}
        
    except Exception as e:
        logger.error(f"❌ Error analyzing trends: {str(e)}", exc_info=True)
        return {"trends": [f"Unable to analyze trends: {str(e)[:100]}"]}

@router.get("/predict")
async def predict_financial_trends(
    granularity: str = Query("monthly", enum=["weekly", "monthly"]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 1. Fetch data - now using SQLAlchemy Transaction model (not Pydantic)
        transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()

        if len(transactions) < 3:
            return {"forecast": [], "message": "Need at least 3 transactions to generate a forecast."}

        # 2. Preparation
        df = pd.DataFrame([{"date": t.date, "amount": t.amount, "type": t.type} for t in transactions])
        df["date"] = pd.to_datetime(df["date"])

        # Calculate Historical Baseline (The "Dynamic Budget")
        # We take the average of historical monthly expenses to act as a benchmark
        hist_monthly = df[df["type"] == "expense"].set_index("date").resample("ME")["amount"].sum()
        avg_monthly_spend = float(hist_monthly.mean()) if not hist_monthly.empty else 0

        if granularity == "weekly":
            df["period"] = df["date"].dt.to_period("W").dt.to_timestamp()
            freq_code, periods_to_predict, date_format = "W", 4, "Week %U"
            benchmark = avg_monthly_spend / 4
        else:
            df["period"] = df["date"].dt.to_period("M").dt.to_timestamp()
            freq_code, periods_to_predict, date_format = "MS", 3, "%B %Y"
            benchmark = avg_monthly_spend

        # Aggregate metrics for Prophet
        data_grouped = df.groupby(["period", "type"])["amount"].sum().unstack(fill_value=0).reset_index()
        for col in ["income", "expense"]:
            if col not in data_grouped.columns: data_grouped[col] = 0.0
        
        if len(data_grouped) < 2:
            return {"forecast": [], "message": "Insufficient history for this view."}

        # 3. Prediction Logic
        forecasts = {}
        def prophet_forecast(series_name):
            sub_df = pd.DataFrame({"ds": data_grouped["period"], "y": data_grouped[series_name]})
            model = Prophet(yearly_seasonality=False, weekly_seasonality=(granularity == "weekly"), daily_seasonality=False)
            model.fit(sub_df)
            future = model.make_future_dataframe(periods=periods_to_predict, freq=freq_code)
            return model.predict(future)[["ds", "yhat"]].tail(periods_to_predict)

        for metric in ["income", "expense"]:
            forecasts[metric] = prophet_forecast(metric)

        # 4. Format Output with "Smart Baseline" Alerts
        forecast_result = []
        for i in range(periods_to_predict):
            ds = forecasts["income"].iloc[i]["ds"]
            pred_expense = round(float(forecasts["expense"].iloc[i]["yhat"]), 2)
            pred_income = round(float(forecasts["income"].iloc[i]["yhat"]), 2)
            
            # Alert logic: Is predicted spending > historical average?
            is_unusual = benchmark > 0 and pred_expense > (benchmark * 1.1) # 10% buffer
            
            forecast_result.append({
                "label": ds.strftime(date_format),
                "date": ds.strftime("%Y-%m-%d"),
                "income": pred_income,
                "expense": pred_expense,
                "savings": round(pred_income - pred_expense, 2),
                "insight": {
                    "baseline_limit": round(benchmark, 2),
                    "is_above_average": is_unusual,
                    "difference_from_avg": round(pred_expense - benchmark, 2)
                }
            })

        return {
            "granularity": granularity,
            "historical_avg_spending": round(avg_monthly_spend, 2),
            "forecast": forecast_result,
            "alerts": [f"Heads up! Your spending in {f['label']} is predicted to be higher than your usual average." for f in forecast_result if f['insight']['is_above_average']]
        }

    except Exception as e:
        logger.error(f"Prediction Error: {str(e)}")
        return {"forecast": [], "error": "Could not generate forecast"}