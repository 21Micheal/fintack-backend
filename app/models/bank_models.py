from sqlalchemy import (
    Column,
    String,
    Float,
    Date,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class BankItem(Base):
    __tablename__ = "bank_items"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    access_token = Column(String, nullable=False, unique=True)
    institution_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    accounts = relationship("BankAccount", back_populates="bank_item", cascade="all, delete-orphan")
    transactions = relationship("BankTransaction", back_populates="bank_item", cascade="all, delete-orphan")


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(String, primary_key=True, index=True)
    bank_item_id = Column(String, ForeignKey("bank_items.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    subtype = Column(String, nullable=True)
    mask = Column(String, nullable=True)
    current_balance = Column(Float, nullable=True)
    available_balance = Column(Float, nullable=True)
    iso_currency_code = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    bank_item = relationship("BankItem", back_populates="accounts")
    transactions = relationship("BankTransaction", back_populates="account", cascade="all, delete-orphan")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(String, primary_key=True, index=True)
    bank_item_id = Column(String, ForeignKey("bank_items.id", ondelete="CASCADE"))
    account_id = Column(String, ForeignKey("bank_accounts.id", ondelete="CASCADE"))
    name = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    category = Column(String, nullable=True)
    pending = Column(String, nullable=True)
    iso_currency_code = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    bank_item = relationship("BankItem", back_populates="transactions")
    account = relationship("BankAccount", back_populates="transactions")
