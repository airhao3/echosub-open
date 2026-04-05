from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional, Dict, Any

class OAuthProvider(str, Enum):
    GITHUB = "github"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    MICROSOFT = "microsoft"
    APPLE = "apple"

class OAuthAccountBase(BaseModel):
    """Base OAuth account schema."""
    provider: OAuthProvider
    provider_user_id: str
    account_email: str
    account_name: Optional[str] = None
    account_avatar: Optional[HttpUrl] = None
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scopes: Optional[str] = None

class OAuthAccountCreate(OAuthAccountBase):
    """Schema for creating a new OAuth account."""
    pass

class OAuthAccountUpdate(BaseModel):
    """Schema for updating an existing OAuth account."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scopes: Optional[str] = None
    account_name: Optional[str] = None
    account_avatar: Optional[HttpUrl] = None

class OAuthAccountInDB(OAuthAccountBase):
    """OAuth account schema as stored in the database."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class OAuthAccount(OAuthAccountBase):
    """OAuth account schema for API responses."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    password: Optional[str] = None
    current_password: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDBBase(UserBase):
    id: int
    is_superuser: bool = False

    class Config:
        orm_mode = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    """User model with sensitive data for internal use."""
    hashed_password: str

    class Config:
        orm_mode = True

class UserResponse(UserInDBBase):
    """User model for API responses."""

    class Config:
        orm_mode = True
