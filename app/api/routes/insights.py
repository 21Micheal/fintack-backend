# app/api/routes/insights.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.transaction import AICache, FinancialProfile, AdvisorContext, User
from app.core.profile_engine import update_financial_profile
from app.core.advisor_ai import generate_personalized_advice
from app.core.advisor_context_manager import update_advisor_context
from typing import List, Dict
import logging
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI Insights"])


# Schema for the mark-applied request
class MarkAppliedRequest(BaseModel):
    applied: bool = True

@router.get("/history/{user_id}")
async def get_ai_insight_history(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieve historical AI insights and their associated alert context.
    """
    try:
        results = (
            db.query(AICache)
            .filter(AICache.user_id == user_id)
            .order_by(AICache.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "id": str(r.id),
                "alert_title": r.alert_title,
                "alert_message": r.alert_message,
                "transactions": r.transaction_summary if isinstance(r.transaction_summary, (list, dict)) else [],
                "ai_response": r.ai_response,
                "applied": getattr(r, 'applied', False), # Safe access
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching AI insight history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch insight history")
    
  

@router.post("/insights/{insight_id}/mark-applied")
async def mark_insight_applied(
    insight_id: str, 
    request: MarkAppliedRequest,
    db: Session = Depends(get_db)
):
    """
    Mark a specific AI insight as 'applied' or 'acknowledged' by the user.
    """
    try:
        # Find the record in the AICache table
        insight = db.query(AICache).filter(AICache.id == insight_id).first()

        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")

        # Update the status
        # Note: Ensure your AICache model has an 'applied' boolean column
        insight.applied = request.applied
        insight.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True, 
            "id": insight_id, 
            "applied": insight.applied
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking insight applied: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/advisor/{user_id}")
async def contextual_advice(user_id: str, db: Session = Depends(get_db)):
    """
    Get contextual financial advice for user.
    """
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update profile and generate advice
        profile = update_financial_profile(db, user_id)
        advice = await generate_personalized_advice(db, user_id)
        
        return {
            "profile": {
                "user_id": profile.user_id,
                "month": profile.month,
                "total_income": profile.total_income,
                "total_expenses": profile.total_expenses,
                "savings": profile.savings,
                "top_category": profile.top_category,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
            },
            "advice": advice
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in contextual_advice endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate financial advice")

# app/api/routes/insights.py - Update the get_contextual_advice function
@router.get("/advisor/contextual-insights/{user_id}")
async def get_contextual_advice(user_id: str, db: Session = Depends(get_db)):
    """
    Get contextual insights with advisor context update.
    """
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"Generating contextual insights for user {user_id}")
        
        # Update financial profile
        profile = update_financial_profile(db, user_id)
        if not profile:
            logger.error("Failed to create financial profile")
            raise HTTPException(status_code=500, detail="Failed to create financial profile")
            
        logger.info("Financial profile updated successfully")
        
        # Generate personalized advice
        advice = await generate_personalized_advice(db, user_id)
        logger.info("Personalized advice generated successfully")
        
        # Update advisor context
        update_advisor_context(db, user_id, ai_summary=advice)
        logger.info("Advisor context updated successfully")

        return {
            "profile": {
                "user_id": profile.user_id,
                "month": profile.month,
                "total_income": float(profile.total_income or 0),
                "total_expenses": float(profile.total_expenses or 0),
                "savings": float(profile.savings or 0),
                "top_category": profile.top_category or "None"
            },
            "contextual_advice": advice
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_contextual_advice endpoint: {str(e)}", exc_info=True)
        # Return a helpful response even if there's an error
        return {
            "profile": {
                "user_id": user_id,
                "month": datetime.utcnow().strftime("%Y-%m"),
                "total_income": 0.0,
                "total_expenses": 0.0,
                "savings": 0.0,
                "top_category": "None"
            },
            "contextual_advice": "I'm still learning about your financial patterns. As you add more transactions, I'll provide more personalized advice!"
        }

@router.post("/advisor/goals/{user_id}")
async def update_financial_goals(user_id: str, payload: Dict, db: Session = Depends(get_db)):
    """
    Save or update user financial goals.
    """
    try:
        goals = payload.get("goals")
        if not goals:
            raise HTTPException(status_code=400, detail="Missing 'goals' in request body")

        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Use AdvisorContext to store goals
        advisor_context = db.query(AdvisorContext).filter(AdvisorContext.user_id == user_id).first()
        if not advisor_context:
            advisor_context = AdvisorContext(
                user_id=user_id,
                alert_summary=None,
                ai_summary=None,
                last_profile_snapshot=str(goals),
            )
            db.add(advisor_context)
        else:
            advisor_context.last_profile_snapshot = str(goals)

        advisor_context.last_generated_at = datetime.utcnow()
        db.commit()

        return {"message": "Financial goals updated successfully", "goals": goals}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating financial goals: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update financial goals")

@router.get("/advisor/trends/{user_id}")
async def get_financial_trends(user_id: str, db: Session = Depends(get_db)):
    """
    Fetch financial trends for a given user.
    """
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profiles = (
            db.query(FinancialProfile)
            .filter(FinancialProfile.user_id == user_id)
            .order_by(FinancialProfile.month.asc())
            .all()
        )

        if not profiles:
            return {"user_id": user_id, "trends": [], "message": "No financial data found"}

        trends = []
        for profile in profiles:
            trends.append({
                "month": profile.month,
                "income": float(profile.total_income or 0),
                "expenses": float(profile.total_expenses or 0),
                "savings": float(profile.savings or 0),
                "top_category": profile.top_category or "None",
            })

        return {"user_id": user_id, "trends": trends}
        
    except Exception as e:
        logger.error(f"Error fetching financial trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch financial trends")