from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, func, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import datetime, timezone

class AICache(Base):
    __tablename__ = "ai_cache"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    alert_hash = Column(String(128), index=True)
    alert_title = Column(String(255))
    alert_message = Column(Text)
    applied = Column(Boolean, default=False)
    transaction_summary = Column(JSONB)
    ai_response = Column(Text, nullable=False)
    response_type = Column(String(50), default="insight")  # insight, advice, summary
    model_used = Column(String(50), default="gpt-3.5-turbo")
    tokens_used = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now())
    refresh_needed = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="ai_caches")
    
    def __repr__(self):
        return f"<AICache(user_id={self.user_id}, alert_title={self.alert_title}, applied={self.applied})>"
    
    @property
    def is_expired(self):
        """Check if cache entry is expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at