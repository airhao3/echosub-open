"""Audit logging models for system activity tracking."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSON as JSONType  
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from .base import Base


class AuditAction(str, PyEnum):
    """Audit action types."""
    # User actions
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTER = "user.register" 
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    
    # Job actions
    JOB_CREATE = "job.create"
    JOB_UPDATE = "job.update"
    JOB_DELETE = "job.delete"
    JOB_START = "job.start"
    JOB_COMPLETE = "job.complete"
    JOB_FAIL = "job.fail"
    
    # Subscription actions
    SUBSCRIPTION_CREATE = "subscription.create"
    SUBSCRIPTION_UPDATE = "subscription.update"
    SUBSCRIPTION_CANCEL = "subscription.cancel"
    
    # Payment actions
    PAYMENT_CREATE = "payment.create"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAIL = "payment.fail"
    
    # Security actions
    API_KEY_CREATE = "api_key.create"
    API_KEY_DELETE = "api_key.delete"
    UNAUTHORIZED_ACCESS = "security.unauthorized_access"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"


class ResourceType(str, PyEnum):
    """Resource types for audit logging."""
    USER = "user"
    JOB = "job"
    SUBSCRIPTION = "subscription"  
    PAYMENT = "payment"
    API_KEY = "api_key"
    SYSTEM = "system"


class AuditLog(Base):
    """Audit log for tracking all system activities."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action details
    action = Column(String(100), nullable=False, index=True)  # What action was performed
    resource_type = Column(String(50), nullable=False)  # What type of resource was affected
    resource_id = Column(String(100), nullable=True)  # ID of the affected resource
    
    # Data changes (for update operations)
    old_values = Column(JSONType, nullable=True)  # Previous values (for updates)
    new_values = Column(JSONType, nullable=True)  # New values (for creates/updates)
    
    # Request details
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)  # Browser/client info
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id}, resource={self.resource_type}:{self.resource_id})>"