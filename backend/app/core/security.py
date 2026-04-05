from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import get_settings

settings = get_settings()

# Configure password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to verify against
        
    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Error verifying password: {str(e)}")
        return False

def get_password_hash(password: str) -> str:
    """
    Generate a password hash
    
    Args:
        password: The plain text password
        
    Returns:
        str: The hashed password
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        print(f"Error hashing password: {str(e)}")
        raise

def create_access_token(
    subject: Union[str, int], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token
    
    Args:
        subject: The subject of the token (usually user id)
        expires_delta: Optional timedelta for token expiration
        
    Returns:
        str: Encoded JWT token
    """
    try:
        # Set expiration time
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            
        # Ensure subject is a string
        subject_str = str(subject).strip()
        if not subject_str:
            raise ValueError("Subject cannot be empty")
            
        # Create token payload
        to_encode = {
            "exp": int(expire.timestamp()),  # Convert to POSIX timestamp
            "sub": subject_str,
            "iat": int(datetime.utcnow().timestamp())  # Issued at
        }
        
        # Encode the token
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
        
    except Exception as e:
        print(f"Error creating access token: {str(e)}")
        raise

def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token
    
    Args:
        token: The JWT token to verify
        
    Returns:
        dict: The decoded token payload if valid
        
    Raises:
        JWTError: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        print(f"Token validation error: {str(e)}")
        raise

def get_token_payload(token: str) -> Optional[dict]:
    """
    Safely get the payload from a token
    
    Args:
        token: The JWT token
        
    Returns:
        Optional[dict]: The token payload if valid, None otherwise
    """
    try:
        return verify_token(token)
    except JWTError:
        return None

def get_token_subject(token: str) -> Optional[str]:
    """
    Get the subject (user id) from a token
    
    Args:
        token: The JWT token
        
    Returns:
        Optional[str]: The subject (user id) if valid, None otherwise
    """
    payload = get_token_payload(token)
    if payload and 'sub' in payload:
        return str(payload['sub'])
    return None
