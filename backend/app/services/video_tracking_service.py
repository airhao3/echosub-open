import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.video_processing_record import VideoProcessingRecord
from app.models.job import Job

logger = logging.getLogger(__name__)

class VideoTrackingService:
    """Service for tracking video processing history using content hash"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_processing_record(self, content_hash: str, language: str, process_type: str) -> Optional[VideoProcessingRecord]:
        """
        Find existing processing record for a video by content hash, language, and process type
        
        Args:
            content_hash: The content hash of the video
            language: The language for which the video was processed
            process_type: The type of processing (subtitles, dubbing, etc.)
            
        Returns:
            The processing record if found, None otherwise
        """
        try:
            record = self.db.query(VideoProcessingRecord).filter(
                and_(
                    VideoProcessingRecord.content_hash == content_hash,
                    VideoProcessingRecord.language == language,
                    VideoProcessingRecord.process_type == process_type
                )
            ).first()
            
            return record
        except Exception as e:
            logger.error(f"Error finding processing record: {str(e)}")
            return None
    
    def check_processing_status(self, content_hash: str, language: str, process_type: str) -> Dict[str, Any]:
        """
        Check if a video has been processed before and return its status
        
        Args:
            content_hash: The content hash of the video
            language: The language to check
            process_type: The process type to check
            
        Returns:
            Dict with status information:
            {
                'exists': bool,
                'is_processing': bool,
                'process_count': int,
                'last_processed_at': datetime,
                'result_path': str or None
            }
        """
        record = self.find_processing_record(content_hash, language, process_type)
        
        if not record:
            return {
                'exists': False,
                'is_processing': False,
                'process_count': 0,
                'last_processed_at': None,
                'result_path': None
            }
            
        return {
            'exists': True,
            'is_processing': record.is_processing,
            'process_count': record.process_count,
            'last_processed_at': record.last_processed_at,
            'result_path': record.result_path
        }
    
    def register_processing_start(self, 
                                content_hash: str, 
                                language: str, 
                                process_type: str,
                                original_filename: str = None,
                                job_id: int = None) -> VideoProcessingRecord:
        """
        Register that processing has started for a video
        
        Args:
            content_hash: The content hash of the video
            language: The language being processed
            process_type: The type of processing
            original_filename: The original filename of the video
            job_id: The ID of the job processing the video
            
        Returns:
            The updated or created processing record
        """
        record = self.find_processing_record(content_hash, language, process_type)
        
        if record:
            # Update existing record
            logger.info(f"Video with hash {content_hash} has been processed {record.process_count} times before. Updating record.")
            record.update_processing(job_id)
        else:
            # Create new record
            logger.info(f"First time processing video with hash {content_hash}. Creating new record.")
            job_ids = [job_id] if job_id else []
            record = VideoProcessingRecord(
                content_hash=content_hash,
                language=language,
                process_type=process_type,
                original_filename=original_filename,
                job_ids=job_ids,
                is_processing=True
            )
            self.db.add(record)
            
        self.db.commit()
        return record
    
    def register_processing_complete(self, 
                                   content_hash: str, 
                                   language: str, 
                                   process_type: str,
                                   result_path: str = None) -> bool:
        """
        Register that processing has completed for a video
        
        Args:
            content_hash: The content hash of the video
            language: The language that was processed
            process_type: The type of processing
            result_path: The path to the processed result
            
        Returns:
            True if successful, False otherwise
        """
        try:
            record = self.find_processing_record(content_hash, language, process_type)
            
            if not record:
                logger.warning(f"No processing record found for {content_hash}, {language}, {process_type}")
                return False
                
            record.mark_completed(result_path)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error registering processing completion: {str(e)}")
            self.db.rollback()
            return False
            
    def get_processing_history(self, content_hash: str) -> List[VideoProcessingRecord]:
        """
        Get the processing history for a video by content hash
        
        Args:
            content_hash: The content hash of the video
            
        Returns:
            List of processing records for the video
        """
        try:
            records = self.db.query(VideoProcessingRecord).filter(
                VideoProcessingRecord.content_hash == content_hash
            ).all()
            
            return records
        except Exception as e:
            logger.error(f"Error getting processing history: {str(e)}")
            return []
