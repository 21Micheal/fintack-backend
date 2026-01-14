from sqlalchemy import (
    Column, String, Float, Date, Text, DateTime, func,
    Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.db.session import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=True)
    phone = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="user")
    advisor_context = relationship("AdvisorContext", back_populates="user", uselist=False)
    profiles = relationship("FinancialProfile", back_populates="user")

    __table_args__ = (
        UniqueConstraint("email", "phone", name="uix_user_email_phone"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    account_id = Column(String(100), nullable=True)
    account_name = Column(String(255), nullable=True)
    institution_name = Column(String(255), nullable=True)
    account_type = Column(String(50), nullable=True)
    balance = Column(Float, nullable=True)
    transaction_type = Column(String(100), nullable=True)
    reference = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    mpesa_receipt = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    source = Column(String, nullable=True, default="manual")
    type = Column(String, nullable=False, default="expense")
    currency = Column(String, default="KES")
    raw_content = Column(Text, nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="transactions")



class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(120), nullable=False)
    message = Column(Text, nullable=False)
    # Changed from 'level' to 'severity' to match your Schema
    severity = Column(String(50), default="info")  # "info", "warning", "critical", "goal"
    category = Column(String(50), nullable=True)   # "spending", "savings", "budget"
    ai_insight = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Alert(title='{self.title}', severity='{self.severity}')>"


class AICache(Base):
    __tablename__ = "ai_cache"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), index=True)
    alert_hash = Column(String(128), index=True)
    alert_title = Column(String(255))
    alert_message = Column(Text)
    applied = Column(Boolean, default=False)
    transaction_summary = Column(JSONB)
    ai_response = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now())
    refresh_needed = Column(Boolean, default=False)


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    month = Column(String(10), index=True)  # e.g. "2025-10"
    total_income = Column(Float, default=0)
    total_expenses = Column(Float, default=0)
    savings = Column(Float, default=0)
    top_category = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="profiles")


class AdvisorContext(Base):
    __tablename__ = "advisor_context"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    alert_summary = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    last_profile_snapshot = Column(Text, nullable=True)
    last_generated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="advisor_context")

    def is_stale(self, days: int = 7):
        """Check if cached AI summary is older than X days."""
        if not self.last_generated_at:
            return True
        return (datetime.utcnow() - self.last_generated_at).days > days


class Goal(Base):
    __tablename__ = "savings_goals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Links to auth.users id
    name = Column(String(100), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(Date, nullable=True)
    category = Column(String(50), default="savings")
    color = Column(String(7), default="#10b981")
    icon = Column(String(50), default="target")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())