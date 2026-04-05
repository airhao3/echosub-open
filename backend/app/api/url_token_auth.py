"""
URL Token Authentication Module

This module provides functions for validating tokens passed as URL parameters,
which is necessary for resources like videos that can't set authorization headers.
"""

import logging
from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

async def get_user_from_url_token(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Extract token from URL parameters and validate it.
    Returns the User if valid, or None if no token is provided or token is invalid.
    """
    token = request.query_params.get("token")
    
    if not token:
        logger.debug("No token in URL parameters")
        return None
    
    try:
        # Decode the token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Extract user ID
        user_id = int(payload.get("sub"))
        if not user_id:
            logger.warning("Token has no sub claim")
            return None
            
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User with ID {user_id} not found")
            return None
            
        if not user.is_active:
            logger.warning(f"User {user_id} is inactive")
            return None
            
        return user
        
    except JWTError as e:
        logger.warning(f"Invalid token in URL params: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing URL token: {e}")
        return None

async def get_auth_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get authenticated user from URL token parameter.
    This is for endpoints that require authentication but can't use headers.
    Raises HTTPException if authentication fails.
    """
    user = await get_user_from_url_token(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated via URL token parameter"
        )
        
    return user
