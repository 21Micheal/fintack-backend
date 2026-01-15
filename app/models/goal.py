# app/models/goal.py
from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import date

class Goal(Base):
    __tablename__ = "savings_goals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(Date, nullable=True)
    category = Column(String(50), default="savings")
    priority = Column(String(20), default="medium")
    color = Column(String(7), default="#10b981")
    icon = Column(String(50), default="target")
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    monthly_target = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Define relationship as string
    user = relationship("User", back_populates="goals", lazy="select")
    
    def __repr__(self):
        return f"<Goal(name={self.name}, target={self.target_amount}, current={self.current_amount})>"
    
    @property
    def progress_percentage(self):
        if self.target_amount <= 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)