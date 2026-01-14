from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from app.models.transaction import Goal
from app.schemas.goal_schema import GoalCreate, GoalUpdate
from typing import List, Optional, Union
from datetime import date

def get_goals_by_user(db: Session, user_id: Union[UUID, str]) -> List[Goal]:
    """Get all goals for a user"""
    # Convert to string if it's UUID to ensure consistent comparison
    user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
    return db.query(Goal).filter(Goal.user_id == user_id_str).order_by(Goal.created_at.desc()).all()

def get_goal_by_id(db: Session, goal_id: Union[UUID, str], user_id: Union[UUID, str]) -> Optional[Goal]:
    """Get a specific goal by ID for a user"""
    # Convert to strings for consistent comparison
    goal_id_str = str(goal_id) if isinstance(goal_id, UUID) else goal_id
    user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
    
    return db.query(Goal).filter(
        and_(Goal.id == goal_id_str, Goal.user_id == user_id_str)
    ).first()

def create_goal(db: Session, goal: GoalCreate, user_id: Union[UUID, str]) -> Goal:
    """Create a new goal"""
    user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
    
    db_goal = Goal(
        user_id=user_id_str,
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=0.0,
        deadline=goal.deadline,
        category=goal.category,
        color=goal.color,
        icon=goal.icon,
        is_active=goal.is_active
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

def update_goal(db: Session, goal_id: Union[UUID, str], user_id: Union[UUID, str], goal_update: GoalUpdate) -> Optional[Goal]:
    """Update an existing goal"""
    db_goal = get_goal_by_id(db, goal_id, user_id)
    if not db_goal:
        return None
    
    update_data = goal_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_goal, field, value)
    
    db.commit()
    db.refresh(db_goal)
    return db_goal

def delete_goal(db: Session, goal_id: Union[UUID, str], user_id: Union[UUID, str]) -> bool:
    """Delete a goal"""
    db_goal = get_goal_by_id(db, goal_id, user_id)
    if not db_goal:
        return False
    
    db.delete(db_goal)
    db.commit()
    return True

def update_goal_progress(db: Session, goal_id: Union[UUID, str], user_id: Union[UUID, str], amount: float) -> Optional[Goal]:
    """Add progress to a goal"""
    db_goal = get_goal_by_id(db, goal_id, user_id)
    if not db_goal:
        return None
    
    # Ensure we don't exceed target amount
    new_amount = min(db_goal.current_amount + amount, db_goal.target_amount)
    db_goal.current_amount = new_amount
    
    # Auto-complete if target reached
    if new_amount >= db_goal.target_amount:
        db_goal.is_active = False
    
    db.commit()
    db.refresh(db_goal)
    return db_goal

def get_goals_summary(db: Session, user_id: Union[UUID, str]):
    """Get summary of all goals for a user"""
    user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
    goals = db.query(Goal).filter(Goal.user_id == user_id_str).all()
    
    if not goals:
        return {
            "total_goals": 0,
            "completed_goals": 0,
            "active_goals": 0,
            "total_target": 0,
            "total_saved": 0,
            "overall_progress": 0
        }
    
    # Calculate summary
    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.current_amount >= g.target_amount)
    total_target = sum(g.target_amount for g in goals)
    total_current = sum(g.current_amount for g in goals)
    
    return {
        "total_goals": total_goals,
        "completed_goals": completed_goals,
        "active_goals": total_goals - completed_goals,
        "total_target": total_target,
        "total_saved": total_current,
        "overall_progress": (total_current / total_target * 100) if total_target > 0 else 0
    }

def calculate_goal_progress(db: Session, goal_id: Union[UUID, str], user_id: Union[UUID, str]):
    """Calculate detailed progress for a specific goal"""
    goal = get_goal_by_id(db, goal_id, user_id)
    if not goal:
        return None
    
    progress_percentage = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
    amount_remaining = goal.target_amount - goal.current_amount
    is_completed = goal.current_amount >= goal.target_amount
    
    days_remaining = None
    if goal.deadline:
        today = date.today()
        days_remaining = (goal.deadline - today).days
        days_remaining = max(0, days_remaining)  # Don't show negative days
    
    # Calculate daily savings needed if deadline exists
    daily_savings_needed = None
    if goal.deadline and days_remaining and days_remaining > 0:
        daily_savings_needed = amount_remaining / days_remaining
    
    return {
        "goal_id": str(goal.id),
        "goal_name": goal.name,
        "current_amount": goal.current_amount,
        "target_amount": goal.target_amount,
        "progress_percentage": round(progress_percentage, 2),
        "amount_remaining": round(amount_remaining, 2),
        "days_remaining": days_remaining,
        "daily_savings_needed": round(daily_savings_needed, 2) if daily_savings_needed else None,
        "is_completed": is_completed,
        "category": goal.category,
        "deadline": goal.deadline.isoformat() if goal.deadline else None
    }