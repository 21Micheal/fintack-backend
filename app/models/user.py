# app/models/user.py
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=True)
    phone = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Define relationships as strings to avoid circular imports
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan", lazy="select")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan", lazy="select")
    financial_profiles = relationship("FinancialProfile", back_populates="user", cascade="all, delete-orphan", lazy="select")
    advisor_context = relationship("AdvisorContext", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="select")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan", lazy="select")
    ai_caches = relationship("AICache", back_populates="user", cascade="all, delete-orphan", lazy="select")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"