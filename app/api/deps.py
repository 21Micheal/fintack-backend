# app/api/deps.py - UPDATED
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timezone
from uuid import UUID as PyUUID
import logging
import requests
from typing import Optional

from app.db.session import get_db
from app.models import User
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# app/api/deps.py - Fix HTTP validation
def verify_supabase_token_via_http(token: str) -> Optional[dict]:
    """Verify token by calling Supabase API"""
    try:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            logger.warning("Supabase URL or ANON_KEY not configured, skipping HTTP validation")
            return None
            
        response = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY
            },
            timeout=10
        )
        
        logger.debug(f"HTTP validation response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"HTTP validation successful for user: {data.get('email')}")
            return data
        elif response.status_code == 401:
            # Try with service_role key if available
            if hasattr(settings, 'SUPABASE_SERVICE_ROLE_KEY') and settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.info("Trying with service_role key...")
                response = requests.get(
                    f"{settings.SUPABASE_URL}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()
            
            logger.warning(f"HTTP validation failed with 401: {response.text}")
            return None
        else:
            logger.warning(f"HTTP validation failed: {response.status_code} - {response.text}")
            
    except requests.exceptions.Timeout:
        logger.warning("HTTP token verification timed out")
    except Exception as e:
        logger.warning(f"HTTP token verification failed: {str(e)}")
        
    return None

def verify_supabase_token_locally(token: str) -> Optional[dict]:
    """Verify token locally using JWT secret"""
    try:
        if not settings.SUPABASE_JWT_SECRET:
            logger.warning("SUPABASE_JWT_SECRET not configured, skipping local validation")
            return None
            
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
        
        logger.info(f"Local JWT validation successful for user: {payload.get('email')}")
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
    except JWTError as e:
        logger.warning(f"Local JWT verification failed: {str(e)}")
    except Exception as e:
        logger.warning(f"Unexpected error in local validation: {str(e)}")
        
    return None

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current user - tries HTTP validation first, falls back to local JWT
    """
    # Debug logging
    auth_header = request.headers.get("authorization")
    logger.info(f"Auth attempt - Header present: {bool(auth_header)}, Credentials: {bool(credentials)}")
    
    if not credentials:
        logger.warning("No authorization credentials provided")
        raise HTTPException(
            status_code=401, 
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    
    if not token or token == "null" or token == "undefined":
        logger.warning(f"Invalid token format: {token}")
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    logger.debug(f"Token received (first 20 chars): {token[:20]}...")
    
    user_data = None
    
    # Try HTTP validation first
    user_data = verify_supabase_token_via_http(token)
    
    # Fall back to local JWT validation
    if not user_data:
        user_data = verify_supabase_token_locally(token)
    
    if not user_data:
        logger.error("All token validation methods failed")
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract user info
    sub = user_data.get("sub") or user_data.get("id")
    email = user_data.get("email")
    phone = user_data.get("phone") or user_data.get("phone_number")
    
    # Check for metadata
    if "user_metadata" in user_data:
        metadata = user_data.get("user_metadata", {})
        phone = phone or metadata.get("phone_number") or metadata.get("phone")
        name = metadata.get("name") or metadata.get("full_name")
    
    if not sub:
        logger.error("No user ID found in token")
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = PyUUID(sub)
    except ValueError:
        logger.error(f"Invalid UUID format: {sub}")
        raise HTTPException(status_code=401, detail="Invalid user ID format")

    # Find or create user in database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.info(f"Creating new user: {email} ({user_id})")
        user = User(
            id=user_id, 
            email=email, 
            phone=phone,
            name=name or email.split('@')[0]  # Default name from email
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user: {user.email}")

    logger.info(f"User authenticated: {user.email} ({user.id})")
    return user