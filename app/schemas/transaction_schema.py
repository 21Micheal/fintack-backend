from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Union
from uuid import UUID



# --- Request schemas ---
class TransactionCreate(BaseModel):
    name: str
    amount: float
    date: date
    category: Optional[str] = None
    account_id: Optional[str] = None
    bank_item_id: Optional[int] = None


# --- Response schemas ---
class TransactionResponse(BaseModel):
    id: Union[int, str, UUID]
    name: Optional[str]
    amount: float
    date: date
    category: Optional[str]
    account_id: Optional[str]
    transaction_type: Optional[str]
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
