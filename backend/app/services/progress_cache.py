import json
import logging
from typing import Dict, Any, List
import time

from app.core.redis_service import get_redis_client

logger = logging.getLogger(__name__)

PROGRESS_KEY_PREFIX = "job:progress:"
PROGRESS_KEY_EXPIRE = 86400

def update_progress(job_id: int, progress_data: Dict[str, Any]) -> None:
    """
    Update job progress information in Redis by accumulating events.
    """
    logger.debug(f"[Job {job_id}] update_progress function CALLED.") # LOG: Announce function call
    redis = get_redis_client()
    
    if not redis:
        # LOG: Make the warning clearer
        logger.warning(f"[Job {job_id}] Redis client is NOT AVAILABLE. Cannot update progress cache.")
        return

    try:
        key = f"{PROGRESS_KEY_PREFIX}{job_id}"
        
        # Get existing progress data
        existing_data = redis.get(key)
        if existing_data:
            try:
                accumulated_data = json.loads(existing_data)
                # Ensure events list exists
                if 'events' not in accumulated_data:
                    accumulated_data['events'] = []
            except (json.JSONDecodeError, TypeError):
                # If existing data is corrupted, start fresh
                accumulated_data = {"events": [], "last_updated": time.time()}
        else:
            accumulated_data = {"events": [], "last_updated": time.time()}
        
        # Add the new event to the events list
        accumulated_data['events'].append(progress_data)
        
        # Update summary information from the latest event
        accumulated_data.update({
            'job_id': job_id,
            'last_updated': time.time(),
            'current_stage': progress_data.get('stage'),
            'current_event_type': progress_data.get('event_type'),
            'overall_progress': progress_data.get('overall_progress', 0),
            'status': progress_data.get('status', 'processing')
        })
        
        # Keep only the last 100 events to prevent memory issues
        if len(accumulated_data['events']) > 100:
            accumulated_data['events'] = accumulated_data['events'][-100:]
        
        value = json.dumps(accumulated_data)
        redis.set(key, value, ex=PROGRESS_KEY_EXPIRE)
        logger.debug(f"[Job {job_id}] Successfully updated progress in Redis with key '{key}'. Events: {len(accumulated_data['events'])}")

    except Exception as e:
        logger.error(f"[Job {job_id}] Failed to update progress in Redis: {e}", exc_info=True)

def get_progress(job_id: int) -> Dict[str, Any]:
    """
    Get the latest progress information for a job from Redis.
    """
    logger.debug(f"[Job {job_id}] get_progress function CALLED.")
    redis = get_redis_client()
    if not redis:
        logger.warning(f"[Job {job_id}] Redis client is NOT AVAILABLE. Cannot get progress.")
        return {"status": "not_found", "message": "Redis not connected"}

    try:
        key = f"{PROGRESS_KEY_PREFIX}{job_id}"
        result = redis.get(key)

        if result:
            progress_data = json.loads(result)
            return {
                "status": "found",
                "data": progress_data
            }
        else:
            return {"status": "not_found"}
            
    except Exception as e:
        logger.error(f"[Job {job_id}] Failed to get progress from Redis: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def clear_job(job_id: int) -> None:
    """
    Clear a job's progress data from Redis upon completion or failure.
    """
    logger.debug(f"[Job {job_id}] clear_job function CALLED.")
    redis = get_redis_client()
    if not redis:
        logger.warning(f"[Job {job_id}] Redis client is NOT AVAILABLE. Cannot clear job cache.")
        return

    try:
        key = f"{PROGRESS_KEY_PREFIX}{job_id}"
        redis.delete(key)
        logger.info(f"[Job {job_id}] Cleared progress cache from Redis.")
    except Exception as e:
        logger.error(f"[Job {job_id}] Failed to clear job from Redis: {e}", exc_info=True)
