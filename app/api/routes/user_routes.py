# user_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import User, Transaction
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/user", tags=["User"])

# Add this utility at the top of your file
def normalize_phone(phone: str) -> str:
    if not phone: return None
    digits = "".join(filter(str.isdigit, phone))
    if digits.startswith("0"):
        return "254" + digits[1:]
    elif digits.startswith("7"): # Handles cases like 712...
        return "254" + digits
    return digits

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
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    phone = data.get("phone_number")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    normalized_phone = normalize_phone(phone)

    # CHECK 1: Ensure phone isn't taken by SOMEONE ELSE
    existing_user = db.query(User).filter(User.phone == normalized_phone).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=409, detail="This phone number is already linked to another account.")

    # 2. Update current user's phone
    current_user.phone = normalized_phone
    
    # 3. Claim orphaned transactions (Crucial logic)
    claimed_count = db.query(Transaction).filter(
        Transaction.phone_number == normalized_phone,
        Transaction.user_id.is_(None)
    ).update({"user_id": current_user.id}, synchronize_session=False)
    
    try:
        db.commit()
        db.refresh(current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to link phone number")
    
    return {
        "message": f"Phone linked and {claimed_count} transactions claimed.",
        "phone": normalized_phone,
        "claimed_transactions": claimed_count
    }

@router.put("/update-phone")
async def update_phone(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user's phone number OR Unlink if null
    """
    # We use .get() without a default to detect if key exists but is None
    phone = data.get("phone_number")
    
    # CASE 1: UNLINKING (Phone is explicitly None)
    if phone is None:
        current_user.phone = None
        db.commit()
        db.refresh(current_user)
        return {"message": "Phone number unlinked successfully", "phone": None}

    # CASE 2: UPDATING (Phone is provided)
    # Check if taken by another user
    existing_user = db.query(User).filter(User.phone == phone).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=409, detail="Phone number already linked to another account.")
    
    current_user.phone = phone
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Phone updated successfully",
        "phone": phone
    }