from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class AdvisorContext(Base):
    __tablename__ = "advisor_context"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    alert_summary = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    last_profile_snapshot = Column(Text, nullable=True)
    financial_goals = Column(Text, nullable=True)
    risk_tolerance = Column(String(50), default="medium")
    investment_horizon = Column(String(50), default="medium")
    preferred_categories = Column(Text, nullable=True)  # JSON string
    spending_patterns = Column(Text, nullable=True)  # JSON string
    last_generated_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="advisor_context")
    
    def __repr__(self):
        return f"<AdvisorContext(user_id={self.user_id}, last_generated={self.last_generated_at})>"