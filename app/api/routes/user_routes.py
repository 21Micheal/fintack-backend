# user_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.models import User, Transaction
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["User"])

# ✅ Request schemas for validation
class PhoneLinkRequest(BaseModel):
    phone_number: str

class PhoneUpdateRequest(BaseModel):
    phone_number: Optional[str] = None  # Allows None for unlinking

# ✅ Improved phone normalization
def normalize_phone(phone: str) -> Optional[str]:
    """
    Normalize phone number to 254XXXXXXXXX format
    Returns None if phone is None or empty
    """
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits = "".join(filter(str.isdigit, phone))
    
    if not digits:
        return None
    
    # Handle different formats
    if digits.startswith("254"):
        return digits  # Already in correct format
    elif digits.startswith("0"):
        return "254" + digits[1:]  # 0712... -> 254712...
    elif digits.startswith("7") or digits.startswith("1"):
        return "254" + digits  # 712... -> 254712...
    
    return digits  # Return as-is if unknown format


@router.post("/phone-by-email")
async def get_phone_by_email(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if a phone number is linked to the user's email
    """
    email = data.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "linked": bool(user.phone),
        "phone_number": user.phone,
        "email": user.email
    }


@router.post("/link-phone")
async def link_phone_to_user(
    request: PhoneLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Link a phone number to the current user's account.
    Also handles updating an existing phone number.
    Claims orphaned transactions for this phone.
    """
    try:
        phone = request.phone_number
        
        if not phone:
            raise HTTPException(status_code=400, detail="Phone number is required")
        
        # Normalize the phone number
        normalized_phone = normalize_phone(phone)
        
        if not normalized_phone:
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        
        # Validate format (should be 254XXXXXXXXX - 12 digits)
        if not (normalized_phone.startswith("254") and len(normalized_phone) == 12):
            raise HTTPException(
                status_code=400, 
                detail="Phone must be 12 digits starting with 254 (e.g., 254712345678)"
            )
        
        logger.info(f"🔗 Linking phone {normalized_phone} to user {current_user.email}")
        
        # Check if phone is already linked to ANOTHER user
        existing_user = db.query(User).filter(
            User.phone == normalized_phone,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            logger.warning(f"⚠️ Phone {normalized_phone} already linked to {existing_user.email}")
            raise HTTPException(
                status_code=409, 
                detail="This phone number is already linked to another account."
            )
        
        # Update current user's phone (or confirm if already linked)
        old_phone = current_user.phone
        current_user.phone = normalized_phone
        
        # Claim orphaned transactions for this phone number
        claimed_count = db.query(Transaction).filter(
            Transaction.account_id == normalized_phone,
            Transaction.user_id.is_(None)
        ).update({"user_id": current_user.id}, synchronize_session=False)
        
        db.commit()
        db.refresh(current_user)
        
        action = "updated" if old_phone else "linked"
        logger.info(f"✅ Phone {action}: {normalized_phone}, claimed {claimed_count} transactions")
        
        return {
            "message": f"Phone {action} successfully. {claimed_count} transaction(s) claimed.",
            "phone": normalized_phone,
            "claimed_transactions": claimed_count,
            "action": action
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Phone link error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link phone: {str(e)}")


@router.put("/update-phone")
async def update_phone(
    request: PhoneUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user's phone number OR unlink if None/null is provided.
    """
    try:
        phone = request.phone_number
        
        # CASE 1: UNLINKING (Phone is None or empty string)
        if phone is None or phone == "":
            logger.info(f"🔓 Unlinking phone for user {current_user.email}")
            current_user.phone = None
            db.commit()
            db.refresh(current_user)
            return {
                "message": "Phone number unlinked successfully",
                "phone": None
            }
        
        # CASE 2: UPDATING (Phone is provided)
        normalized_phone = normalize_phone(phone)
        
        if not normalized_phone:
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        
        # Validate format
        if not (normalized_phone.startswith("254") and len(normalized_phone) == 12):
            raise HTTPException(
                status_code=400,
                detail="Phone must be 12 digits starting with 254"
            )
        
        # Check if taken by another user
        existing_user = db.query(User).filter(
            User.phone == normalized_phone,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Phone number already linked to another account."
            )
        
        logger.info(f"📱 Updating phone for {current_user.email} to {normalized_phone}")
        current_user.phone = normalized_phone
        db.commit()
        db.refresh(current_user)
        
        return {
            "message": "Phone updated successfully",
            "phone": normalized_phone
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Phone update error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update phone: {str(e)}")


@router.delete("/unlink-phone")
async def unlink_phone(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dedicated endpoint for unlinking phone (cleaner than PUT with null)
    """
    try:
        if not current_user.phone:
            raise HTTPException(status_code=400, detail="No phone number is currently linked")
        
        logger.info(f"🔓 Unlinking phone {current_user.phone} from {current_user.email}")
        current_user.phone = None
        db.commit()
        db.refresh(current_user)
        
        return {
            "message": "Phone number unlinked successfully",
            "phone": None
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Phone unlink error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink phone: {str(e)}")