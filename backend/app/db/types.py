import json
import logging
from typing import Any, Optional, Union, Dict, Type, TypeVar

from sqlalchemy.types import TypeDecorator, TEXT, TypeEngine

logger = logging.getLogger(__name__)
T = TypeVar('T', bound=Type['TypeEngine'])

class FlexibleJSON(TypeDecorator):
    """
    A flexible JSON type that can handle strings, dictionaries, and None values.
    Automatically converts between JSON strings and Python dictionaries.
    """
    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        # For SQLite, use TEXT type
        if dialect.name == 'sqlite':
            return dialect.type_descriptor(TEXT())
        # For PostgreSQL, use JSON type if available
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value: Optional[Union[Dict, str, bytes, bool, int, float]], dialect) -> Optional[str]:
        """
        Process the value before storing it in the database.
        Converts Python objects to JSON strings.
        """
        if value is None:
            return None
            
        # Handle bytes by decoding to string
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode bytes to string: {value!r}")
                return None
                
        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            if not value:  # Empty string
                return None
                
            # Check for preset styles
            lower_val = value.lower()
            if lower_val in ['default', 'outline', 'box']:
                return json.dumps({"preset": lower_val})
                
            # Try to parse as JSON if it looks like JSON
            if value[0] in '{[' and value[-1] in '}]':
                try:
                    parsed = json.loads(value)
                    return json.dumps(parsed)  # Re-serialize to ensure valid JSON
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Invalid JSON in process_bind_param: {value!r}, error: {e}")
                    return json.dumps({"value": value})
            return json.dumps({"value": value})
            
        # Handle other JSON-serializable types
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize value to JSON: {value!r}, error: {e}")
            return None

    def process_result_value(self, value: Any, dialect) -> Optional[Union[Dict, str, int, float, bool]]:
        """
        Process the value after loading it from the database.
        Converts JSON strings to Python objects.
        """
        if value is None:
            return None
            
        # Handle bytes by decoding to string
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode bytes to string: {value!r}")
                return None
                
        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            if not value:  # Empty string
                return None
                
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse JSON from database: {value!r}, error: {e}")
                return {"value": value}
                
        # For non-string values, return as is
        return value
