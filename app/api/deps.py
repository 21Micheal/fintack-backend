# app/api/deps.py - UPDATED VERSION
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timezone
from uuid import UUID as PyUUID
import logging
import requests
from typing import Optional

from app.db.session import get_db
from app.models.transaction import User
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

def verify_supabase_token_via_http(token: str) -> Optional[dict]:
    """Verify token by calling Supabase API"""
    try:
        response = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"HTTP token verification failed: {e}")
    return None

def verify_supabase_token_locally(token: str) -> Optional[dict]:
    """Verify token locally using JWT secret"""
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,
            },
        )
        return payload
    except JWTError as e:
        logger.warning(f"Local JWT verification failed: {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current user - tries HTTP validation first, falls back to local JWT
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = credentials.credentials
    user_data = None
    
    # Try HTTP validation first (more reliable)
    user_data = verify_supabase_token_via_http(token)
    
    # Fall back to local JWT validation
    if not user_data:
        user_data = verify_supabase_token_locally(token)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Extract user info
    sub = user_data.get("sub") or user_data.get("id")
    email = user_data.get("email")
    phone = user_data.get("phone") or user_data.get("phone_number")
    
    # Check for metadata in HTTP response
    if "user_metadata" in user_data:
        metadata = user_data.get("user_metadata", {})
        phone = phone or metadata.get("phone_number") or metadata.get("phone")

    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = PyUUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID format")

    # Find or create user in database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id, email=email, phone=phone)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user: {email}")

    return user