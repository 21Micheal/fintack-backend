# app/schemas/alert.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator

# Allowed severity levels (using Literal for strict validation)
SeverityLevel = Literal["info", "warning", "critical", "goal"]

# Base schema with common fields
class AlertBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=120, description="Short title of the alert")
    message: str = Field(..., min_length=10, max_length=500, description="Main alert message")
    severity: SeverityLevel = Field(..., description="Alert severity level")
    category: Optional[str] = Field(None, max_length=50, description="Optional category like 'spending', 'savings', 'budget'")
    ai_insight: Optional[str] = Field(None, max_length=1000, description="Optional AI-generated deeper insight/explanation")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Schema for creating a new alert (what the client sends)
class AlertCreate(AlertBase):
    user_id: str = Field(..., description="UUID of the user this alert belongs to")
    
    # You can add defaults or extra validation if needed
    @validator("title")
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


# Schema for response / reading alerts (includes DB-generated fields)
class AlertOut(AlertBase):
    id: int = Field(..., description="Internal database ID")
    user_id: str = Field(..., description="User UUID")
    is_read: bool = Field(default=False, description="Whether the user has read this alert")
    created_at: datetime = Field(..., description="When the alert was created")
    updated_at: Optional[datetime] = Field(None, description="Last update time (if applicable)")

    class Config:
        orm_mode = True           # Allows conversion from SQLAlchemy models
        from_attributes = True    # Pydantic v2+ style (recommended)


# Optional: Schema for bulk update / partial update
class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
    title: Optional[str] = Field(None, min_length=3, max_length=120)
    message: Optional[str] = Field(None, min_length=10, max_length=500)
    severity: Optional[SeverityLevel] = None
    ai_insight: Optional[str] = None

    class Config:
        extra = "forbid"  # Prevent unknown fields