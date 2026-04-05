"""
Videolingo SaaS Backend Application

This package contains the main application code for the Videolingo SaaS backend.
"""

__version__ = '0.1.0'

# Import and expose CRUD operations
from . import crud

# Make these available at the package level
__all__ = [
    'crud',
]
