import logging
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# Initial superuser data
SUPERUSER_EMAIL = "admin@videolingo.example.com"
SUPERUSER_USERNAME = "admin"
SUPERUSER_PASSWORD = "admin123"  # Please change to a strong password in production
SUPERUSER_FULLNAME = "System Administrator"

def create_initial_superuser(db: Session) -> None:
    """
    Create initial superuser (if not exists)
    """
    # Check if superuser already exists
    user = db.query(User).filter(
        (User.email == SUPERUSER_EMAIL) |
        (User.username == SUPERUSER_USERNAME)
    ).first()
    
    if user:
        logger.info(f"Superuser already exists: {user.username}")
        return
    
    # Create new superuser
    logger.info(f"Creating initial superuser: {SUPERUSER_USERNAME}")
    
    user = User(
        email=SUPERUSER_EMAIL,
        username=SUPERUSER_USERNAME,
        hashed_password=get_password_hash(SUPERUSER_PASSWORD),
        full_name=SUPERUSER_FULLNAME,
        is_active=True,
        is_superuser=True,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Superuser created successfully: {user.id}")


def init_db(db: Session) -> None:
    """
    Initialize database data
    """
    # Create superuser
    create_initial_superuser(db)
