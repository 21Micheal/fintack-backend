from pydantic import BaseModel, validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID

class GoalBase(BaseModel):
    name: str
    target_amount: float
    deadline: Optional[date] = None
    category: str = "savings"
    color: str = "#10b981"
    icon: str = "target"
    is_active: bool = True

    @validator('target_amount')
    def target_amount_positive(cls, v):
        if v <= 0:
            raise ValueError('Target amount must be positive')
        return v

    @validator('name')
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Goal name cannot be empty')
        return v.strip()

class GoalCreate(GoalBase):
    pass

class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    deadline: Optional[date] = None
    category: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None

class GoalResponse(GoalBase):
    id: UUID
    user_id: UUID
    current_amount: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GoalProgress(BaseModel):
    goal_id: UUID
    progress_percentage: float
    amount_remaining: float
    days_remaining: Optional[int] = None
    is_completed: bool

class GoalSummary(BaseModel):
    total_goals: int
    active_goals: int
    completed_goals: int
    total_target: float
    total_saved: float
    overall_progress: float