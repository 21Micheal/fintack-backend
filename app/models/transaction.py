# app/models/transaction.py
from sqlalchemy import (
    Column, String, Float, Date, Text, DateTime, func,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

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
    
    # Relationship
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, category={self.category})>"