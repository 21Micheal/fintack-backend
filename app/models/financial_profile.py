# app/models/financial_profile.py
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    month = Column(String(10), index=True)
    total_income = Column(Float, default=0)
    total_expenses = Column(Float, default=0)
    savings = Column(Float, default=0)
    top_category = Column(String(50))
    top_category_amount = Column(Float, default=0)
    avg_daily_spending = Column(Float, default=0)
    biggest_expense = Column(Float, default=0)
    biggest_expense_category = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Define relationship as string
    user = relationship("User", back_populates="financial_profiles", lazy="select")
    
    def __repr__(self):
        return f"<FinancialProfile(user_id={self.user_id}, month={self.month}, savings={self.savings})>"