import os
import json
from pathlib import Path
import logging
from app.utils.file_path_manager import get_file_path_manager, FileType
from app.models.job_context import JobContext

logger = logging.getLogger(__name__)

# Temporary storage for subtitle languages until proper database migration
class SubtitlePreferencesService:
    """
    Temporary service to handle subtitle language preferences without requiring database migrations.
    This allows us to implement the feature while avoiding database errors.
    """
    
    def __init__(self, data_dir=None):
        self.file_manager = get_file_path_manager()
        # For backward compatibility with old calls, still accept data_dir parameter
    
    def get_preferences_file(self, job_id: int, user_id: int = 1) -> str:
        """Get the path to the preferences file for a specific job"""
        context = JobContext(user_id=user_id, job_id=job_id, content_hash=None)
        return self.file_manager.get_file_path(
            context, FileType.PREFERENCES_FILE, filename=f"job_{job_id}_languages.json"
        )
    
    def save_subtitle_languages(self, job_id: int, languages: list, user_id: int = 1) -> bool:
        """Save subtitle language preferences for a job"""
        try:
            preferences_file = self.get_preferences_file(job_id, user_id)
            data = {
                'job_id': job_id,
                'subtitle_languages': languages
            }
            self.file_manager.write_json(preferences_file, data)
            logger.info(f"Saved subtitle languages for job {job_id}: {languages}")
            return True
        except Exception as e:
            logger.error(f"Error saving subtitle languages for job {job_id}: {str(e)}")
            return False
    
    def get_subtitle_languages(self, job_id: int, user_id: int = 1) -> list:
        """Get subtitle language preferences for a job"""
        try:
            preferences_file = self.get_preferences_file(job_id, user_id)
            if not os.path.exists(preferences_file):
                return []
            
            with open(preferences_file, 'r') as f:
                data = json.load(f)
                return data.get('subtitle_languages', [])
        except Exception as e:
            logger.error(f"Error loading subtitle languages for job {job_id}: {str(e)}")
            return []
    
    def delete_subtitle_languages(self, job_id: int) -> bool:
        """Delete subtitle language preferences for a job"""
        try:
            preferences_file = self.get_preferences_file(job_id)
            if os.path.exists(preferences_file):
                os.remove(preferences_file)
                logger.info(f"Deleted subtitle languages for job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting subtitle languages for job {job_id}: {str(e)}")
            return False
