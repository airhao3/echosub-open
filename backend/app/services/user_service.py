import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)

class UserService:
    """
    Service for user management operations
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID
        """
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email
        """
        return self.db.query(User).filter(User.email == email).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username
        """
        return self.db.query(User).filter(User.username == username).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all users with pagination
        """
        return self.db.query(User).offset(skip).limit(limit).all()
    
    def create(self, user_data: Dict[str, Any]) -> User:
        """
        Create a new user
        """
        # Check if email or username already exists
        if self.get_by_email(user_data.get("email")):
            raise ValueError(f"Email {user_data.get('email')} already registered")
        
        if self.get_by_username(user_data.get("username")):
            raise ValueError(f"Username {user_data.get('username')} already registered")
        
        # Create password hash
        password = user_data.pop("password", None)
        if not password:
            raise ValueError("Password is required")
        
        # Create user object
        user = User(
            **user_data,
            hashed_password=get_password_hash(password),
            is_superuser=user_data.get("is_superuser", False)
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"Created new user: {user.username} (ID: {user.id})")
        return user
    
    def update(self, user_id: int, user_data: Dict[str, Any]) -> Optional[User]:
        """
        Update user information
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        # Handle email change
        if "email" in user_data and user_data["email"] != user.email:
            if self.get_by_email(user_data["email"]):
                raise ValueError(f"Email {user_data['email']} already registered")
        
        # Handle username change
        if "username" in user_data and user_data["username"] != user.username:
            if self.get_by_username(user_data["username"]):
                raise ValueError(f"Username {user_data['username']} already registered")
        
        # Handle password change
        if "password" in user_data:
            user.hashed_password = get_password_hash(user_data.pop("password"))
        
        # Update other fields
        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"Updated user: {user.username} (ID: {user.id})")
        return user
    
    def delete(self, user_id: int) -> bool:
        """
        Delete a user
        """
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        self.db.delete(user)
        self.db.commit()
        
        logger.info(f"Deleted user: {user.username} (ID: {user.id})")
        return True
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user by username and password
        """
        user = self.get_by_username(username)
        if not user:
            # Try to authenticate by email
            user = self.get_by_email(username)
        
        if not user or not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    def is_active(self, user: User) -> bool:
        """
        Check if user is active
        """
        return user.is_active
