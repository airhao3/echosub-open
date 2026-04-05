import redis
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client = None

# Log the connection details that are being used
logger.info(f"Attempting to connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}, DB: {settings.REDIS_DB}")

try:
    # Create a Redis client instance with a connection pool
    pool = redis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True  # Automatically decode responses to strings (utf-8)
    )
    redis_client = redis.Redis(connection_pool=pool)
    
    # Test the connection
    redis_client.ping()
    logger.info("Successfully connected to Redis and received a PONG.")

except redis.exceptions.ConnectionError as e:
    logger.error(f"FATAL: Could not connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}. Progress tracking will NOT work. Error: {e}", exc_info=True)
    redis_client = None
except Exception as e:
    logger.error(f"FATAL: An unexpected error occurred during Redis initialization. Progress tracking will NOT work. Error: {e}", exc_info=True)
    redis_client = None

def get_redis_client():
    """
    Returns the shared Redis client instance.
    
    Returns:
        An initialized Redis client, or None if the connection failed.
    """
    if redis_client is None:
        logger.warning("Redis client is None. Returning None.")
    return redis_client