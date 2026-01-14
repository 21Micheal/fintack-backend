from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Literal
from sqlalchemy.orm import Session
import httpx
from app.config import settings
from app.db.session import get_db
from app.models.transaction import Transaction, User
from app.schemas.transaction_schema import TransactionResponse
from datetime import datetime
import logging
import json
from app.api.deps import get_current_user 
from app.models.transaction import User
from app.core.supabase_client import get_supabase_admin
import re


# Configure logging properly
logger = logging.getLogger(__name__)

# Create a router with prefix and tags
router = APIRouter(tags=["Transactions"])

def classify_transaction(transaction: dict) -> str:
    """
    Comprehensive transaction classification.
    """
    # Check existing type
    if transaction.get('type') in ['income', 'expense']:
        return transaction['type']
    
    # Check category first (most reliable for your data)
    category = (transaction.get('category') or '').lower()
    
    # Definitely expense categories
    expense_categories = [
        'shopping', 'food', 'transport', 'entertainment',
        'bills', 'utilities', 'rent', 'groceries',
        'dining', 'travel', 'subscriptions', 'shopping',
        'retail', 'supermarket', 'mall'
    ]
    
    for expense_cat in expense_categories:
        if expense_cat in category:
            return 'expense'
    
    # Income categories
    income_categories = [
        'salary', 'freelance', 'business', 'investment',
        'refund', 'bonus', 'gift', 'dividend', 'payment'
    ]
    
    for income_cat in income_categories:
        if income_cat in category:
            return 'income'
    
    # Check description
    description = (transaction.get('description') or '').lower()
    if any(word in description for word in ['received', 'from', 'credited', 'deposit']):
        return 'income'
    
    if any(word in description for word in ['sent to', 'paid to', 'withdraw', 'purchase', 'shopping']):
        return 'expense'
    
    # Default: category-based heuristic
    # Shopping-like categories are expenses
    if 'shop' in category or 'store' in category or 'market' in category:
        return 'expense'
    
    # Most transactions are expenses
    return 'expense'

def determine_mpesa_transaction_type(transaction_type: str, amount: float) -> str:
    """
    Determine if M-Pesa transaction is income or expense based on transaction type.
    """
    transaction_type_lower = transaction_type.lower()
    
    # Income transactions
    if any(word in transaction_type_lower for word in [
        "deposit", "receive", "credit", "from", 
        "payment received", "money received"
    ]):
        return "income"
    
    # Expense transactions  
    if any(word in transaction_type_lower for word in [
        "withdrawal", "send", "payment", "pay bill", 
        "buy goods", "airtime", "transfer", "sent to",
        "paid to", "purchase"
    ]):
        return "expense"
    
    # Default based on common patterns
    # Pay Bill transactions are usually expenses
    if "pay bill" in transaction_type_lower:
        return "expense"
    
    # Receiving money is usually income
    if "received" in transaction_type_lower:
        return "income"
    
    # If we can't determine, use a safer default
    # Most M-Pesa transactions are expenses (payments)
    return "expense"

@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    """
    Receive and store M-Pesa payment data, linking it to the correct user if possible.
    """
    try:
        data = await request.json()
        logger.info("💰 M-Pesa Callback: %s", json.dumps(data, default=str))

        trans_id = data.get("TransID")
        amount = float(data.get("TransAmount", 0))
        trans_time = data.get("TransTime", datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        phone_number = data.get("MSISDN", "").strip()
        name = data.get("FirstName", "M-Pesa User")
        transaction_type = data.get("TransactionType", "Pay Bill")  # Changed variable name to avoid conflict

        # Parse timestamp safely
        try:
            timestamp = datetime.strptime(trans_time, "%Y%m%d%H%M%S")
        except Exception:
            timestamp = datetime.utcnow()

        # Avoid duplicates
        existing = db.query(Transaction).filter(Transaction.description.like(f"%{trans_id}%")).first()
        if existing:
            logger.info("⚠️ Duplicate M-Pesa transaction ignored: %s", trans_id)
            return {"ResultCode": 0, "ResultDesc": "Duplicate ignored"}

        # Try to link with a user by phone
        user = db.query(User).filter(User.phone == phone_number).first()
        user_id = user.id if user else None

        # ✅ FIXED: Determine transaction type properly
        transaction_category = determine_mpesa_transaction_type(transaction_type, amount)
        
        # Create transaction
        new_txn = Transaction(
            name=name,
            amount=amount,
            date=timestamp.date(),
            category="M-Pesa",
            account_id=phone_number,
            transaction_type=transaction_type,  # Original M-Pesa transaction type
            type=transaction_category,  # ✅ Now properly classified as income/expense
            source="mpesa",
            description=f"M-Pesa {transaction_type} (ID: {trans_id})",
            user_id=user_id
        )

        db.add(new_txn)
        db.commit()
        db.refresh(new_txn)

        logger.info("✅ Saved M-Pesa transaction for %s (User: %s, Type: %s)", 
                   phone_number, user.email if user else "None", transaction_category)

        return {"ResultCode": 0, "ResultDesc": "Transaction received successfully"}

    except Exception as e:
        logger.error("❌ M-Pesa callback error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mpesa/transactions", response_model=list[TransactionResponse])
async def get_mpesa_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch all transactions for the current user with proper classification.
    """
    try:
        transactions = db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.source.in_(["mpesa", "sms"])
        ).order_by(Transaction.date.desc()).all()
        
        # ✅ Ensure all transactions are properly classified
        for txn in transactions:
            if not txn.type or txn.type not in ["income", "expense"]:
                correct_type = classify_transaction(txn)
                if txn.type != correct_type:
                    txn.type = correct_type
                    logger.debug(f"Reclassified transaction {txn.id} as {correct_type}")
        
        # Commit any reclassifications
        db.commit()
        
        logger.info("📱 Fetched %d transactions for user %s", len(transactions), current_user.id)
        
        # Log classification summary
        income_count = sum(1 for t in transactions if t.type == "income")
        expense_count = sum(1 for t in transactions if t.type == "expense")
        logger.info("📊 Classification: %d income, %d expense", income_count, expense_count)
        
        return transactions
        
    except Exception as e:
        logger.error("🔥 Error fetching transactions: %s", str(e))
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching transactions: {str(e)}"
        )

def parse_mpesa_message(sms: str) -> dict:
    """
    Robustly parses M-Pesa SMS formats, handling multi-part fragments 
    and various transaction types.
    """
    # Clean up whitespace and newlines
    sms = " ".join(sms.split()).strip()
    
    # 1. Extract Transaction Reference (10 alphanumeric chars)
    # Using search instead of match because it might not be at index 0
    reference_match = re.search(r"\b([A-Z0-9]{10})\b", sms)
    reference = reference_match.group(1) if reference_match else None

    # 2. Extract Amount (Handles 'Ksh1.00', 'Ksh 1,200.00', etc.)
    amount_match = re.search(r"Ksh\s?([\d,]+\.\d{2})", sms, re.IGNORECASE)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else 0.0

    # 3. Extract Balance
    balance_match = re.search(r"balance\s+is\s+Ksh\s?([\d,]+\.\d{2})", sms, re.IGNORECASE)
    balance = float(balance_match.group(1).replace(",", "")) if balance_match else 0.0

    # 4. Extract Date/Time
    # Pattern: 10/1/26 at 8:18 PM
    timestamp = datetime.utcnow() # Default
    date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})\s+at\s+(\d{1,2}:\d{2}\s?[APMapm]{2})", sms)
    if date_match:
        try:
            date_str = date_match.group(1)
            time_str = date_match.group(2).replace(" ", "").upper()
            # Handle 2-digit vs 4-digit years
            year_fmt = "%y" if len(date_str.split('/')[-1]) == 2 else "%Y"
            timestamp = datetime.strptime(f"{date_str} {time_str}", f"%d/%m/{year_fmt} %I:%M%p")
        except Exception as e:
            logger.warning(f"Failed to parse M-Pesa date: {e}")

    # 5. Classification & Merchant Extraction
    txn_type = "expense"  # Default
    merchant = "M-Pesa Transaction"

    # Identify Type
    is_received = re.search(r"received|credited", sms, re.IGNORECASE)
    is_sent = re.search(r"sent to", sms, re.IGNORECASE)
    is_paid = re.search(r"paid to|buy goods", sms, re.IGNORECASE)
    is_withdraw = re.search(r"withdraw", sms, re.IGNORECASE)
    is_fuliza = re.search(r"Fuliza", sms, re.IGNORECASE)

    if is_received:
        txn_type = "income"
        # Extract name after 'from' and before 'on' or '07...'
        m = re.search(r"from\s+(.+?)\s+(?:on|(?:\d{10}))", sms, re.IGNORECASE)
        merchant = m.group(1).strip() if m else "Sender"
        
    elif is_sent:
        txn_type = "expense"
        # Extract name after 'sent to' and before 'on' or '07...'
        m = re.search(r"sent to\s+(.+?)\s+(?:on|(?:\d{10}))", sms, re.IGNORECASE)
        merchant = m.group(1).strip() if m else "Recipient"
        
    elif is_paid:
        txn_type = "expense"
        # Extract name after 'paid to' or 'at'
        m = re.search(r"(?:paid to|at)\s+(.+?)\s+on", sms, re.IGNORECASE)
        merchant = m.group(1).strip() if m else "Merchant"
        
    elif is_withdraw:
        txn_type = "expense"
        m = re.search(r"at\s+(.+?)\s+on", sms, re.IGNORECASE)
        merchant = f"Withdrawal: {m.group(1).strip()}" if m else "Agent Withdrawal"

    elif is_fuliza:
        txn_type = "expense"
        merchant = "Fuliza M-Pesa"

    return {
        "reference": reference,
        "amount": amount,
        "merchant": merchant,
        "timestamp": timestamp,
        "balance": balance,
        "type": txn_type,
        "raw_text": sms
    }

# Request schema for the mobile app
class MpesaTransactionRequest(BaseModel):
    tx_code: str
    type: Literal["income", "expense"]
    amount: float
    counterparty: Optional[str] = None
    phone: Optional[str] = None
    balance: Optional[float] = None
    cost: Optional[float] = None
    occurred_at: datetime
    raw_text: Optional[str] = None


@router.post("/mpesa/transactions")
async def create_mpesa_transaction(
    payload: MpesaTransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 🔒 Idempotency (HARD GUARANTEE)
        existing = db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.reference == payload.tx_code
        ).first()

        if existing:
            logger.info(f"⏭️ Duplicate ignored: {payload.tx_code}")
            raise HTTPException(status_code=409, detail="Transaction already exists")

        txn = Transaction(
            user_id=current_user.id,
            name=payload.counterparty or "M-Pesa",
            amount=payload.amount,
            date=payload.occurred_at,
            category="M-Pesa",
            reference=payload.tx_code,
            type=payload.type,
            source="sms",
            description=f"M-Pesa {payload.type}",
            raw_content=payload.raw_text
        )

        db.add(txn)
        db.commit()
        db.refresh(txn)

        logger.info(f"✅ M-Pesa transaction saved: {payload.tx_code}")

        return {"status": "success", "id": txn.id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Transaction Save Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")




@router.post("/auth/sync_from_supabase")
async def sync_from_supabase(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync user data (like phone number) from Supabase metadata into local DB.
    """
    supabase = get_supabase_admin()
    try:
        user = supabase.auth.admin.get_user_by_id(current_user.id)
        metadata = user.user.get("user_metadata", {})
        phone = metadata.get("phone_number")

        if phone and not current_user.phone:
            current_user.phone = phone
            db.commit()
            db.refresh(current_user)
            logger.info("🔁 Synced phone %s from Supabase for %s", phone, current_user.email)
            return {"message": "Synced from Supabase", "phone": phone}

        return {"message": "No sync needed or already up to date."}

    except Exception as e:
        logger.error("❌ Failed to sync from Supabase: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/link_phone")
async def link_phone(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    phone = data.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")
    
    # 1. Ensure phone number is unique to prevent account hijacking
    existing = db.query(User).filter(User.phone == phone).first()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="Phone number already linked to another account")
    
    # 2. Update local user record
    current_user.phone = phone
    db.add(current_user)
    
    # 3. Update Supabase metadata (Optional but recommended for Auth consistency)
    try:
        supabase_admin = get_supabase_admin()
        supabase_admin.auth.admin.update_user_by_id(
            current_user.id,
            {"user_metadata": {"phone_number": phone}}
        )
    except Exception as e:
        logger.warning(f"⚠️ Supabase sync failed: {str(e)}")

    # 4. INTERNAL SYNC: Reassign all orphaned transactions
    # This combines your previous steps 2 and 3 into one efficient update
    updated_count = db.query(Transaction).filter(
        Transaction.account_id == phone,
        Transaction.user_id.is_(None)
    ).update({"user_id": current_user.id}, synchronize_session=False)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database update failed")

    return {
        "status": "success",
        "message": "Phone linked successfully",
        "phone": phone,
        "linked_transactions_count": updated_count
    }


# Add this temporary endpoint to fix your existing data
@router.post("/fix-transaction-classification")
async def fix_all_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    One-time fix for misclassified transactions.
    """
    try:
        transactions = db.query(Transaction).filter(
            Transaction.user_id == current_user.id
        ).all()
        
        fixed = []
        for txn in transactions:
            original_type = txn.type
            
            # Classify based on category
            category = (txn.category or '').lower()
            if 'shopping' in category:
                correct_type = 'expense'
            elif any(word in category for word in ['food', 'transport', 'bills', 'rent']):
                correct_type = 'expense'
            elif any(word in category for word in ['salary', 'payment', 'business']):
                correct_type = 'income'
            else:
                # Keep original if we can't determine
                continue
            
            if original_type != correct_type:
                txn.type = correct_type
                fixed.append({
                    'id': txn.id,
                    'category': txn.category,
                    'original': original_type,
                    'corrected': correct_type
                })
        
        if fixed:
            db.commit()
            logger.info(f"Fixed {len(fixed)} transactions")
        
        return {
            'fixed_count': len(fixed),
            'fixed_transactions': fixed,
            'message': f'Fixed {len(fixed)} transaction classifications'
        }
        
    except Exception as e:
        logger.error(f"Error fixing transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# --- OLD PLAID TRANSACTION ROUTES (COMMENTED OUT) ---

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from app.services.plaid_service import get_plaid_client
# from app.services.bank_service import create_transactions
# from app.db.session import get_db
# from app.models.bank_models import BankItem, BankTransaction
# from app.schemas.transaction_schema import TransactionResponse
# from plaid.model.transactions_sync_request import TransactionsSyncRequest

# router = APIRouter(prefix="/transactions", tags=["Transactions"])

# @router.post("/sync")
# def sync_transactions(user_id: str, db: Session = Depends(get_db)):
#     """
#     Fetches latest transactions from Plaid and stores them in the DB.
#     """
#     plaid_client = get_plaid_client()

#     # Retrieve user's bank item (access_token)
#     bank_item = db.query(BankItem).filter(BankItem.user_id == user_id).first()
#     if not bank_item:
#         raise HTTPException(status_code=404, detail="No linked bank account found")

#     request = TransactionsSyncRequest(access_token=bank_item.access_token)

#     try:
#         response = plaid_client.transactions_sync(request)
#         added_transactions = response["added"]

#         if added_transactions:
#             create_transactions(db, bank_item.id, added_transactions)

#         return {"status": "success", "fetched": len(added_transactions)}

#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))


# @router.get("/", response_model=list[TransactionResponse])
# def get_transactions(user_id: str, db: Session = Depends(get_db)):
#     """
#     Returns transactions stored in the DB for a given user.
#     """
#     transactions = (
#         db.query(BankTransaction)
#         .join(BankItem)
#         .filter(BankItem.user_id == user_id)
#         .order_by(BankTransaction.date.desc())
#         .all()
#     )

#     if not transactions:
#         return []

#     return [
#         TransactionResponse(
#             id=t.id,
#             name=t.name,
#             amount=t.amount,
#             date=t.date,
#             category=t.category,
#             account_id=t.account_id,
#         )
#         for t in transactions
#     ]
