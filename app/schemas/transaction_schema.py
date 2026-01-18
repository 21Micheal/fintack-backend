from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Union, Literal
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
    type: Literal["income", "expense"]  # This was missing!
    
    transaction_type: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    account_id: Optional[str] = None
    phone_number: Optional[str] = None
    reference: Optional[str] = None  # Add this too for M-Pesa
    raw_content: Optional[str] = None  # And this for debugging
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True # ✅ Correct for V2
    }
