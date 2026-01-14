# # app/api/auth.py - NEW FILE
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.transaction import User, Transaction
from app.api.routes.user_routes import normalize_phone
from datetime import datetime
import httpx
from app.config import settings
import logging

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user info with M-Pesa transaction linking"""
    # Auto-link phone number if found in M-Pesa transactions
    if current_user.phone:
        # Reassign orphaned M-Pesa transactions to this user
        updated = db.query(Transaction).filter(
            Transaction.user_id.is_(None),
            Transaction.account_id == current_user.phone
        ).update({Transaction.user_id: current_user.id})
        
        if updated > 0:
            db.commit()
            logger.info(f"Linked {updated} orphaned transactions for user {current_user.id}")
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "phone": current_user.phone,
        "linked_mpesa": bool(current_user.phone),
        "created_at": current_user.created_at
    }

@router.post("/sync_on_login")
async def sync_on_login(
    data: dict = None,  # Make optional
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync user data on login - primarily links orphaned transactions.
    """
    try:
        # 1. Normalize user's phone for accurate matching
        phone = current_user.phone
        if phone:
            phone = normalize_phone(phone)
            current_user.phone = phone
            db.commit()

        # 2. CLAIM ORPHANED TRANSACTIONS
        linked_count = 0
        if phone:
            linked_count = db.query(Transaction).filter(
                Transaction.user_id.is_(None),
                (Transaction.phone_number == phone) | (Transaction.account_id == phone)
            ).update(
                {Transaction.user_id: current_user.id}, 
                synchronize_session=False
            )
            db.commit()
        
        # 3. Optional: Process incoming transactions from frontend
        incoming_txns = data.get("transactions", []) if data else []
        synced_count = 0
        
        if incoming_txns:
            valid_columns = Transaction.__table__.columns.keys()
            for tx_data in incoming_txns:
                tx_id = tx_data.get("id")
                existing = db.query(Transaction).filter(Transaction.id == tx_id).first()

                cleaned_tx_data = {
                    k: v for k, v in tx_data.items() 
                    if k in valid_columns
                }

                if existing:
                    if existing.user_id is None:
                        existing.user_id = current_user.id
                        synced_count += 1
                else:
                    new_txn = Transaction(**cleaned_tx_data)
                    new_txn.user_id = current_user.id
                    db.add(new_txn)
                    synced_count += 1
            
            db.commit()
        
        logger.info(f"🔄 Sync complete for {current_user.email}: {linked_count} claimed, {synced_count} synced.")

        return {
            "status": "success",
            "message": f"Sync complete: {linked_count} orphaned transactions claimed.",
            "user_id": str(current_user.id),
            "phone": phone,
            "linked_count": linked_count,
            "synced_count": synced_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error in sync_on_login: {e}")
        raise HTTPException(status_code=500, detail=str(e))