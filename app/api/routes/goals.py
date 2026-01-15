from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.core.goal_crud import (
    get_goals_by_user,
    get_goal_by_id,
    create_goal,
    update_goal,
    delete_goal,
    update_goal_progress,
    get_goals_summary,
    calculate_goal_progress,
)
from app.schemas.goal_schema import GoalCreate, GoalUpdate, GoalResponse, GoalProgress, GoalSummary

# Create router without trailing slash in prefix
router = APIRouter(prefix="/api/goals", tags=["goals"])

# ── Helper to handle both /goals and /goals/ ─────────────────────────────
def normalize_path(path: str) -> str:
    """Remove trailing slash if present"""
    return path.rstrip("/")


# GET /api/goals    and    GET /api/goals/
@router.get("/", response_model=List[GoalResponse])
@router.get("", response_model=List[GoalResponse])  # handles /api/goals (no slash)
def read_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all goals for the current user"""
    return get_goals_by_user(db, current_user.id)


# GET /api/goals/summary    and    /api/goals/summary/
@router.get("/summary", response_model=GoalSummary)
@router.get("/summary/", response_model=GoalSummary)
def read_goals_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get goals summary for the current user"""
    return get_goals_summary(db, current_user.id)


# GET /api/goals/{goal_id}    and    /api/goals/{goal_id}/
@router.get("/{goal_id}", response_model=GoalResponse)
@router.get("/{goal_id}/", response_model=GoalResponse)
def read_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific goal by ID"""
    goal = get_goal_by_id(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found"
        )
    return goal


# GET /api/goals/{goal_id}/progress    and    /api/goals/{goal_id}/progress/
@router.get("/{goal_id}/progress", response_model=GoalProgress)
@router.get("/{goal_id}/progress/", response_model=GoalProgress)
def read_goal_progress(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get progress for a specific goal"""
    progress = calculate_goal_progress(db, goal_id, current_user.id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found"
        )
    return progress


# POST /api/goals    and    POST /api/goals/
@router.post("/", response_model=GoalResponse)
@router.post("", response_model=GoalResponse)
def create_new_goal(
    goal: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new savings goal"""
    return create_goal(db, goal, current_user.id)


# PUT /api/goals/{goal_id}    and    PUT /api/goals/{goal_id}/
@router.put("/{goal_id}", response_model=GoalResponse)
@router.put("/{goal_id}/", response_model=GoalResponse)
def update_existing_goal(
    goal_id: UUID,
    goal_update: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing goal"""
    updated_goal = update_goal(db, goal_id, current_user.id, goal_update)
    if not updated_goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found"
        )
    return updated_goal


# PATCH /api/goals/{goal_id}/add-progress    and    /add-progress/
@router.patch("/{goal_id}/add-progress")
@router.patch("/{goal_id}/add-progress/")
def add_goal_progress(
    goal_id: UUID,
    amount: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add progress to a goal (manual contribution)"""
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )

    updated_goal = update_goal_progress(db, goal_id, current_user.id, amount)
    if not updated_goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found"
        )

    progress_pct = (
        (updated_goal.current_amount / updated_goal.target_amount * 100)
        if updated_goal.target_amount > 0
        else 0
    )

    return {
        "message": "Progress updated successfully",
        "current_amount": updated_goal.current_amount,
        "target_amount": updated_goal.target_amount,
        "progress_percentage": progress_pct,
    }


# DELETE /api/goals/{goal_id}    and    /api/goals/{goal_id}/
@router.delete("/{goal_id}")
@router.delete("/{goal_id}/")
def delete_existing_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a goal"""
    success = delete_goal(db, goal_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found"
        )

    return {"message": "Goal deleted successfully"}