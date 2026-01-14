# advisor.py (FastAPI backend)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.transaction import User, Transaction as TransactionModel, FinancialProfile
from app.core.advisor_engine import get_or_generate_advice, analyze_transactions_for_insights
from app.core.insights_ai import generate_ai_insight as InsightGenerator

router = APIRouter(prefix="/api/advisor", tags=["Advisor"])
logger = logging.getLogger(__name__)

# Request/Response Models
class TransactionRequest(BaseModel):
    id: str
    date: str
    amount: float
    type: str = "expense"
    category: str = "Other"
    description: Optional[str] = None
    counterparty: Optional[str] = None

class ContextualAdviceRequest(BaseModel):
    transactions: List[TransactionRequest]

class GoalsRequest(BaseModel):
    goals: List[Dict[str, Any]]

# GET /api/advisor/{user_id}
@router.get("/{user_id}")
async def get_personal_advice(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalized financial advice for user"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")

    try:
        result = await get_or_generate_advice(db, user_id)
        return {
            "advice": result.get("advice", "No advice available at the moment."),
            "profile": result.get("profile", {}),
            "summary": result.get("summary", ""),
            "cached": "cache" in result.get("source", ""),
            "source": result.get("source", "unknown")
        }
    except Exception as e:
        logger.error(f"Error generating advice for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate advice: {str(e)}")

# POST /api/advisor/contextual-insights/{user_id}
# advisor.py - Fix the FinancialProfile model usage
@router.post("/contextual-insights/{user_id}")
async def get_contextual_insights(
    user_id: UUID,
    request: ContextualAdviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get contextual insights based on recent transactions"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")

    try:
        if not request.transactions:
            # Don't throw error, just return basic advice
            return {
                "contextual_advice": "No recent transactions provided. Start tracking your expenses to get personalized financial advice.",
                "insights": {
                    "status": "no_data",
                    "message": "No transactions provided for analysis"
                },
                "profile": {},
                "generated_at": datetime.utcnow().isoformat(),
                "fresh": False
            }
        
        # Convert Pydantic models to dictionaries
        transaction_dicts = [
            {
                "id": str(tx.id),
                "date": tx.date,
                "amount": tx.amount,
                "type": tx.type,
                "category": tx.category,
                "description": tx.description or "",
                "counterparty": tx.counterparty or ""
            }
            for tx in request.transactions
        ]
        
        # Get or create financial profile
        profile = db.query(FinancialProfile).filter(FinancialProfile.user_id == user_id).first()
        
        if not profile:
            # Create a basic profile if none exists
            profile_data = {
                "total_income": 0,
                "total_expenses": 0,
                "savings": 0,
                "top_category": "None",
                "updated_at": datetime.utcnow()  # Add updated_at if your model supports it
            }
        else:
            # Use profile data, handle missing updated_at gracefully
            profile_data = {
                "total_income": profile.total_income if hasattr(profile, 'total_income') else 0,
                "total_expenses": profile.total_expenses if hasattr(profile, 'total_expenses') else 0,
                "savings": profile.savings if hasattr(profile, 'savings') else 0,
                "top_category": profile.top_category if hasattr(profile, 'top_category') else "None",
            }
            
            # Add updated_at if it exists
            if hasattr(profile, 'updated_at') and profile.updated_at:
                profile_data["updated_at"] = profile.updated_at.isoformat()
            else:
                profile_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Analyze transactions for insights
        insights = await analyze_transactions_for_insights(
            transactions=transaction_dicts,
            db=db,
            user_id=str(user_id)
        )
        
        # Generate simple advice based on analysis
        if insights.get("status") == "success":
            metrics = insights.get("metrics", {})
            savings_rate = metrics.get("savings_rate", 0)
            
            if savings_rate < 0:
                advice = "⚠️ Your expenses exceed your income. Consider reviewing discretionary spending and creating a budget."
            elif savings_rate < 10:
                advice = "📊 Your savings rate is low. Try to save at least 20% of your income by automating transfers to savings."
            elif savings_rate < 20:
                advice = "✅ Good start! Your savings habit is developing. Consider increasing your savings rate gradually."
            else:
                advice = "🎉 Excellent savings rate! You're on track for financial security. Consider investing some of your savings."
        else:
            advice = "Start tracking your M-Pesa transactions consistently to get personalized financial advice tailored to your spending patterns."
        
        return {
            "contextual_advice": advice,
            "insights": insights,
            "profile": profile_data,
            "generated_at": datetime.utcnow().isoformat(),
            "fresh": True
        }
        
    except Exception as e:
        logger.error(f"Error generating contextual insights for user {user_id}: {str(e)}", exc_info=True)
        # Return fallback instead of throwing
        return {
            "contextual_advice": "We're having trouble analyzing your transactions right now. General advice: Review your monthly expenses and identify areas where you can save.",
            "insights": {
                "status": "error",
                "message": str(e)
            },
            "profile": {},
            "generated_at": datetime.utcnow().isoformat(),
            "fresh": False
        }

# POST /api/advisor/goals/{user_id}
@router.post("/goals/{user_id}")
async def update_goals(
    user_id: UUID,
    request: GoalsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's financial goals"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    
    try:
        # Get or create financial profile
        profile = db.query(FinancialProfile).filter(FinancialProfile.user_id == user_id).first()
        if not profile:
            profile = FinancialProfile(user_id=user_id, goals={})
            db.add(profile)
        
        # Update goals
        profile.goals = request.goals
        profile.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True, 
            "goals": request.goals,
            "updated_at": profile.updated_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating goals for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update goals: {str(e)}")

# GET /api/advisor/health/{user_id}
@router.get("/health/{user_id}")
async def get_financial_health(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get financial health score and metrics"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    
    try:
        # Get user's financial profile
        profile = db.query(FinancialProfile).filter(FinancialProfile.user_id == user_id).first()
        
        # Get recent transactions
        recent_transactions = (
            db.query(TransactionModel)
            .filter(TransactionModel.user_id == user_id)
            .filter(TransactionModel.created_at >= datetime.utcnow() - timedelta(days=90))
            .all()
        )
        
        # Calculate metrics
        total_income = sum(t.amount for t in recent_transactions if t.type == "income")
        total_expenses = sum(t.amount for t in recent_transactions if t.type == "expense")
        savings = total_income - total_expenses
        savings_rate = (savings / total_income * 100) if total_income > 0 else 0
        
        # Calculate health score
        health_score = 50  # Base score
        
        # Savings rate bonus
        if savings_rate > 20:
            health_score += 30
        elif savings_rate > 10:
            health_score += 20
        elif savings_rate > 5:
            health_score += 10
        elif savings_rate > 0:
            health_score += 5
        
        # Expense control bonus
        expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else 100
        if expense_ratio < 60:
            health_score += 20
        elif expense_ratio < 80:
            health_score += 10
        elif expense_ratio < 100:
            health_score += 5
        
        # Cap score at 100
        health_score = min(100, max(0, health_score))
        
        # Determine health level
        if health_score >= 80:
            health_level = "excellent"
        elif health_score >= 60:
            health_level = "good"
        elif health_score >= 40:
            health_level = "fair"
        else:
            health_level = "needs_attention"
        
        return {
            "health_score": health_score,
            "health_level": health_level,
            "metrics": {
                "total_income": total_income,
                "total_expenses": total_expenses,
                "savings": savings,
                "savings_rate": round(savings_rate, 1),
                "expense_ratio": round(expense_ratio, 1)
            },
            "profile": profile.to_dict() if profile else {},
            "calculated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error calculating financial health for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate financial health: {str(e)}")