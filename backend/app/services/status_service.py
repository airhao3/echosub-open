from typing import Optional, List, Dict, Any, Union
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.services import progress_cache

# Import models from models.py
from app import models as app_models
from app.models import JobStatus, StepName

logger = logging.getLogger(__name__)

class StatusUpdateService:
    """
    Centralized service for updating job and step statuses throughout the workflow.
    Provides atomic updates to both job and step status tables.
    """
    
    @staticmethod
    def normalize_status(status: str) -> str:
        """
        Normalize status to consistent lowercase format.
        
        Args:
            status: Status in any format
            
        Returns:
            Normalized status in lowercase
        """
        if not isinstance(status, str):
            return str(status).lower()
        return status.lower().replace('_', '_').strip()
    
    @staticmethod
    def update_job_status(
        db: Session, 
        job_id: int, 
        status: JobStatus, 
        progress: float = None, 
        status_message: str = None
    ) -> bool:
        """
        Update the status of a translation job.
        
        Args:
            db: Database session
            job_id: ID of the job to update
            status: New job status
            progress: Overall job progress (0-100)
            status_message: Optional status message
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            logger.info(f"[Job {job_id}] Updating status to {status} (progress: {progress}%)")
            if status_message:
                logger.debug(f"[Job {job_id}] Status message: {status_message}")
                
            # First try to get the job from the Job table (new unified model)
            job = db.query(app_models.Job).filter(app_models.Job.id == job_id).first()
            if not job:
                # Fallback to TranslationJob for backward compatibility
                job = db.query(app_models.TranslationJob).filter(app_models.TranslationJob.id == job_id).first()
                if not job:
                    logger.error(f"[Job {job_id}] Job not found in either Job or TranslationJob tables")
                    return False
                logger.debug(f"[Job {job_id}] Using TranslationJob model for backward compatibility")
                
            # Log status transition if it's changing
            if status is not None and job.status != status:
                logger.info(f"[Job {job_id}] Status changing from {job.status} to {status}")
                job.status = status
            
            if progress is not None:
                logger.debug(f"[Job {job_id}] Progress updating from {job.progress}% to {progress}%")
                job.progress = progress
                
            if status_message is not None:
                logger.debug(f"[Job {job_id}] Status message updating to: {status_message}")
                job.status_message = status_message
                
            db.commit()
            logger.info(f"[Job {job_id}] Successfully updated status to {status}")
            return True
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"[Job {job_id}] Failed to update job status: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def update_step_status(
        db: Session, 
        job_id: int, 
        step_name: StepName, 
        status: str = None, 
        progress: float = None, 
        details: str = None
    ) -> bool:
        """
        Update the status of a specific job step.
        
        Args:
            db: Database session
            job_id: ID of the job
            step_name: The step to update
            status: New step status (pending, in_progress, completed, failed)
            progress: Step progress (0-100)
            details: Optional details about the step status
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Check if step exists
            step = db.query(app_models.JobStep).filter(
                app_models.JobStep.job_id == job_id,
                app_models.JobStep.step_name == step_name
            ).first()
            
            if not step:
                # Create new step if it doesn't exist
                step = app_models.JobStep(
                    job_id=job_id,
                    step_name=step_name,
                    status="pending",
                    progress=0.0
                )
                db.add(step)
            
            # Update fields if provided
            if status is not None:
                step.status = status
                
            if progress is not None:
                step.progress = progress
                
            if details is not None:
                step.details = details
                
            db.commit()
            logger.info(f"Updated job {job_id} step {step_name} status to {status} with progress {progress}%")
            return True
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to update step status: {str(e)}")
            return False
    
    # Define step weights for progress calculation
    # More time-consuming steps should have higher weights
    STEP_WEIGHTS = {
        StepName.UPLOAD: 1.0,
        StepName.AUDIO_PROCESSING: 1.5,
        StepName.TRANSCRIBING: 2.5,
        StepName.SEGMENTING: 1.0,
        StepName.ANALYZING: 2.0,
        StepName.TRANSLATING: 3.0,
        StepName.INTEGRATING: 2.0,
        StepName.ALIGNING_TIMESTAMPS: 1.5,
        StepName.ALIGNING_SUBTITLES: 2.0,
        StepName.VIDEO_COMPRESSING: 2.5
    }
    
    @classmethod
    def _get_step_weight(cls, step_name: StepName) -> float:
        """Get the weight of a step for progress calculation"""
        return cls.STEP_WEIGHTS.get(step_name, 1.0)
    
    @classmethod
    def update_workflow_step(
        cls,
        db: Session,
        job_id: int,
        step_name: StepName,
        status: str,
        progress: float,
        details: str = None,
        update_job_progress: bool = True
    ) -> bool:
        """
        Update both a step status and the overall job status in a single transaction.
        Uses weighted progress calculation based on step complexity.
        
        Args:
            db: Database session
            job_id: ID of the job
            step_name: The step to update
            status: New step status (pending, in_progress, completed, failed)
            progress: Step progress (0-100)
            details: Optional details about the step
            update_job_progress: Whether to also update the job's overall progress
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            logger.info(f"[Job {job_id}] Updating workflow step {step_name} to {status} (progress: {progress}%)")
            if details:
                logger.debug(f"[Job {job_id}] Step details: {details}")
            
            # First update the step status
            step_updated = cls.update_step_status(
                db=db,
                job_id=job_id,
                step_name=step_name,
                status=status,
                progress=progress,
                details=details
            )
            
            if not step_updated:
                logger.error(f"[Job {job_id}] Failed to update step {step_name}")
                return False
                
            if update_job_progress:
                    # Get all steps for this job
                all_steps = db.query(app_models.JobStep).filter(
                    app_models.JobStep.job_id == job_id
                ).all()
                
                if not all_steps:
                    logger.warning(f"[Job {job_id}] No steps found for job")
                    return False
                    
                    # Log current state of all steps
                    step_states = [(s.step_name, s.status, s.progress) for s in all_steps]
                    logger.debug(f"[Job {job_id}] Current step states: {step_states}")
                    
                    # Calculate weighted progress across all steps
                    total_weight = 0.0
                    weighted_progress = 0.0
                    has_failed_steps = False
                    all_completed = True
                    
                    for step in all_steps:
                        weight = cls._get_step_weight(step.step_name)
                        total_weight += weight
                        weighted_progress += (step.progress * weight)
                        
                        if step.status == "failed":
                            has_failed_steps = True
                        elif step.status != "completed":
                            all_completed = False
                    
                    overall_progress = round(weighted_progress / total_weight, 2) if total_weight > 0 else 0
                    logger.debug(f"[Job {job_id}] Calculated weighted progress: {overall_progress}%")
                    
                    # Determine overall job status based on step statuses
                    job_status = None
                    if all_completed:
                        job_status = JobStatus.COMPLETED
                        overall_progress = 100.0  # Ensure 100% when all steps are complete
                        logger.info(f"[Job {job_id}] All steps completed, marking job as COMPLETED")
                    elif has_failed_steps:
                        failed_steps = [s.step_name for s in all_steps if s.status == "failed"]
                        job_status = JobStatus.FAILED
                        logger.warning(f"[Job {job_id}] Failed steps detected: {failed_steps}, marking job as FAILED")
                    else:
                        job_status = JobStatus.PROCESSING
                        logger.debug(f"[Job {job_id}] Job still in progress")
                
                    # Update the job status
                    status_message = details or f"Step {step_name} is {status}"
                    logger.info(f"[Job {job_id}] Updating job status to {job_status} with progress {overall_progress}%")
                    
                    job_updated = StatusUpdateService.update_job_status(
                        db=db,
                        job_id=job_id,
                        status=job_status,
                        progress=overall_progress,
                        status_message=status_message
                    )
                    
                    if not job_updated:
                        logger.error(f"[Job {job_id}] Failed to update job status")
                        return False
                    
                    # Update progress cache for real-time updates
                    try:
                        cache_data = {
                            "status": job_status.value if job_status else "processing",
                            "progress": overall_progress,
                            "status_message": status_message,
                            "stage": step_name,
                            "steps": [{"name": s.step_name, "status": s.status, "progress": s.progress} for s in all_steps]
                        }
                        logger.debug(f"[Job {job_id}] Updating progress cache with: {cache_data}")
                        progress_cache.update_progress(job_id, cache_data)
                    except Exception as e:
                        logger.error(f"[Job {job_id}] Failed to update progress cache: {str(e)}", exc_info=True)
                        # Don't fail the whole operation if cache update fails
                        pass
            
            return True
        except Exception as e:
            logger.error(f"Error updating workflow step: {str(e)}")
            return False
    
    @staticmethod
    def get_job_status(db: Session, job_id: int) -> Dict[str, Any]:
        """
        Get the full status of a job, including all steps.
        
        Args:
            db: Database session
            job_id: ID of the job
            
        Returns:
            Dict containing job status and list of steps with their statuses
        """
        try:
            # First try to get the job from the Job table
            job = db.query(app_models.Job).filter(app_models.Job.id == job_id).first()
            if not job:
                # Fallback to TranslationJob for backward compatibility
                job = db.query(app_models.TranslationJob).filter(app_models.TranslationJob.id == job_id).first()
                if not job:
                    return {"error": f"Job with ID {job_id} not found"}
            
            # Get steps from JobStep table
            steps = db.query(app_models.JobStep).filter(
                app_models.JobStep.job_id == job_id
            ).all()
            
            step_statuses = []
            for step in steps:
                step_statuses.append({
                    "step_name": step.step_name,
                    "status": step.status,
                    "progress": step.progress,
                    "details": step.details
                })
                
            return {
                "job_id": job.id,
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                "progress": job.progress,
                "status_message": getattr(job, 'status_message', job.error_message if hasattr(job, 'error_message') else None),
                "steps": step_statuses
            }
        except SQLAlchemyError as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return {"error": f"Database error: {str(e)}"}
