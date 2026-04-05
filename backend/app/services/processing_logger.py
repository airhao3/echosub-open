"Processing logger for VideoLingo SaaS"

import logging
import math
import time
import json
from typing import Dict, Any, Optional, List
from enum import Enum

# Correctly import the progress_cache module at the top level
from app.services import progress_cache

class ProcessingStage(str, Enum):
    """Enum representing different stages of video processing."""
    # Core processing pipeline stages - in execution order
    INITIALIZED = "INITIALIZED"                    # 1. 初始化
    VIDEO_DOWNLOAD = "VIDEO_DOWNLOAD"              # 2. 视频下载/上传
    PREPROCESSING = "PREPROCESSING"                # 3. 视频预处理
    AUDIO_EXTRACTION = "AUDIO_EXTRACTION"         # 4. 音频提取
    TRANSCRIPTION = "TRANSCRIPTION"               # 5. 语音转录
    TEXT_SEGMENTATION = "TEXT_SEGMENTATION"       # 6. 文本分段
    TEXT_TAGGING = "TEXT_TAGGING"                 # 7. 文本标记
    TEXT_REFINEMENT = "TEXT_REFINEMENT"           # 8. 文本精炼
    CONTENT_UNDERSTANDING = "CONTENT_UNDERSTANDING" # 8.5 内容理解与修正
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"       # 9. 语义分析
    TERMINOLOGY_EXTRACTION = "TERMINOLOGY_EXTRACTION"  # 10. 术语提取
    TRANSLATION = "TRANSLATION"                   # 11. 翻译处理
    SUBTITLE_GENERATION = "SUBTITLE_GENERATION"   # 12. 字幕生成
    DUBBING = "DUBBING"                          # 13. 配音处理 (可选)
    VIDEO_PROCESSING = "VIDEO_PROCESSING"         # 14. 视频处理
    FILE_EXPORT = "FILE_EXPORT"                  # 15. 文件导出
    CLEANUP = "CLEANUP"                          # 16. 清理工作
    
    # Special terminal states
    COMPLETED = "COMPLETED"                      # 成功完成
    FAILED = "FAILED"                           # 处理失败
    
    @classmethod
    def get_processing_stages(cls) -> List[str]:
        """Get list of actual processing stages (excluding COMPLETED/FAILED)."""
        return [
            cls.INITIALIZED,
            cls.VIDEO_DOWNLOAD,
            cls.PREPROCESSING,
            cls.AUDIO_EXTRACTION,
            cls.TRANSCRIPTION,
            cls.TEXT_SEGMENTATION,
            cls.TEXT_TAGGING,
            cls.TEXT_REFINEMENT,
            cls.CONTENT_UNDERSTANDING,
            cls.SEMANTIC_ANALYSIS,
            cls.TERMINOLOGY_EXTRACTION,
            cls.TRANSLATION,
            cls.SUBTITLE_GENERATION,
            cls.DUBBING,
            cls.VIDEO_PROCESSING,
            cls.FILE_EXPORT,
            cls.CLEANUP
        ]
    
    @classmethod
    def get_stage_order(cls, stage: str) -> int:
        """Get the order/index of a stage in the processing pipeline."""
        stages = cls.get_processing_stages()
        try:
            return stages.index(stage) + 1  # 1-based indexing
        except ValueError:
            return 0  # Unknown stage
    
    @classmethod
    def is_optional_stage(cls, stage: str) -> bool:
        """Check if a stage is optional and can be skipped."""
        optional_stages = {cls.DUBBING, cls.VIDEO_PROCESSING}
        return stage in optional_stages
    
    @classmethod
    def get_icon(cls, stage: str) -> str:
        """Get an icon for a processing stage"""
        icons = {
            cls.INITIALIZED: "🚀",
            cls.VIDEO_DOWNLOAD: "📥",
            cls.PREPROCESSING: "🔧",
            cls.AUDIO_EXTRACTION: "🔊",
            cls.TRANSCRIPTION: "🔤",
            cls.TEXT_SEGMENTATION: "✂️",
            cls.TEXT_TAGGING: "🏷️",
            cls.TEXT_REFINEMENT: "✨",
            cls.CONTENT_UNDERSTANDING: "🔍",
            cls.SEMANTIC_ANALYSIS: "🧠",
            cls.TERMINOLOGY_EXTRACTION: "📖",
            cls.TRANSLATION: "🌐",
            cls.SUBTITLE_GENERATION: "💬",
            cls.DUBBING: "🎙️",
            cls.VIDEO_PROCESSING: "🎬",
            cls.FILE_EXPORT: "📁",
            cls.CLEANUP: "🧹",
            cls.COMPLETED: "✅",
            cls.FAILED: "❌"
        }
        return icons.get(stage, "⏳")

class ProcessingLogger:
    """Logger for tracking and reporting video processing progress."""
    
    def __init__(self, job_id: int, db_session=None):
        self.job_id = job_id
        self.db = db_session  # Database session for syncing to database
        self.logger = logging.getLogger("app.processing")
        self.stages: Dict[str, Dict[str, Any]] = {}
        self.current_stage: Optional[str] = None
        self.start_time = time.time()
        
        # Initialize tracking
        self.log_info(f"Initializing processing for Job {job_id}")
    
    @staticmethod
    def map_processing_stage_to_step_name(processing_stage: str) -> Optional[str]:
        """Map ProcessingStage to StatusUpdateService StepName for database sync"""
        # Import here to avoid circular imports
        try:
            from app.models import StepName
            
            # Map ProcessingStage to StepName (using available StepName values)
            stage_to_step_mapping = {
                ProcessingStage.INITIALIZED: StepName.UPLOAD,
                ProcessingStage.VIDEO_DOWNLOAD: StepName.UPLOAD,
                ProcessingStage.PREPROCESSING: StepName.UPLOAD,
                ProcessingStage.AUDIO_EXTRACTION: StepName.AUDIO_PROCESSING,
                ProcessingStage.TRANSCRIPTION: StepName.TRANSCRIBING,
                ProcessingStage.TEXT_SEGMENTATION: StepName.SEGMENTING,
                ProcessingStage.TEXT_TAGGING: StepName.SEGMENTING,
                ProcessingStage.TEXT_REFINEMENT: StepName.SEGMENTING,
                ProcessingStage.CONTENT_UNDERSTANDING: StepName.ANALYZING,
                ProcessingStage.SEMANTIC_ANALYSIS: StepName.ANALYZING,
                ProcessingStage.TERMINOLOGY_EXTRACTION: StepName.ANALYZING,
                ProcessingStage.TRANSLATION: StepName.TRANSLATING,
                ProcessingStage.SUBTITLE_GENERATION: StepName.ALIGNING_SUBTITLES,
                ProcessingStage.DUBBING: StepName.INTEGRATING,
                ProcessingStage.VIDEO_PROCESSING: StepName.VIDEO_COMPRESSING,
                ProcessingStage.FILE_EXPORT: StepName.INTEGRATING,
                ProcessingStage.CLEANUP: StepName.INTEGRATING,
            }
            
            return stage_to_step_mapping.get(processing_stage)
        except ImportError:
            return None
    
    def sync_to_database(self, stage: ProcessingStage, status: str, progress: float, detail: str = ""):
        """Sync ProcessingLogger progress to database via StatusUpdateService"""
        if not self.db:
            return  # No database session available
            
        try:
            # Import here to avoid circular imports
            from app.services.status_service import StatusUpdateService
            
            # Map ProcessingStage to StepName
            step_name = self.map_processing_stage_to_step_name(stage)
            if not step_name:
                self.log_warning(f"Could not map processing stage {stage} to database step")
                return
            
            # Update database
            success = StatusUpdateService.update_step_status(
                db=self.db,
                job_id=self.job_id,
                step_name=step_name,
                status=status,
                progress=progress,
                details=detail
            )
            
            if success:
                self.log_info(f"[SYNC] Synced {stage} → {step_name} to database")
            else:
                self.log_warning(f"[SYNC] Failed to sync {stage} to database")
                
        except Exception as e:
            self.log_warning(f"[SYNC] Error syncing to database: {str(e)}")
    
    def start_stage(self, stage: ProcessingStage, detail: str = "") -> None:
        """Start tracking a new processing stage."""
        stage_name = stage.value
        stage_icon = ProcessingStage.get_icon(stage_name)
        self.current_stage = stage_name
        
        # Create stage entry in tracking dictionary
        stage_start_time = time.time()
        self.stages[stage_name] = {
            "start_time": stage_start_time,
            "end_time": None,
            "duration": None,
            "status": "in_progress",
            "detail": detail,
            "progress_updates": []
        }
        
        # Calculate elapsed time since job start
        elapsed = stage_start_time - self.start_time
        
        # Calculate how many stages completed so far for overall progress
        completed_stages = len([s for s in self.stages.values() if s["status"] == "completed"])
        total_stages_seen = len(self.stages)
        
        # Create progress visualization
        if total_stages_seen > 0:
            progress_pct = (completed_stages / total_stages_seen) * 100
            progress_bar = "[" + "#" * int(progress_pct // 5) + "·" * (20 - int(progress_pct // 5)) + "]"
        else:
            progress_bar = "[··················]"
            
        # Format and log the stage start message with more details
        stage_start_msg = f"{stage_icon} STAGE {completed_stages+1} | {progress_bar} | Starting {stage_name}"
        detail_msg = f" - {detail}" if detail else ""
        log_message = f"[JOB {self.job_id}] {stage_start_msg}{detail_msg} ({elapsed:.2f}s elapsed)"
        self.log_info(log_message)
        
        # 更新进度缓存 - 阶段开始事件
        # 计算当前总体进度 - 使用动态阶段计数
        total_processing_stages = len(ProcessingStage.get_processing_stages())
        overall_progress = (completed_stages / total_processing_stages) * 100 if total_processing_stages > 0 else 0
        
        event_data = {
            "job_id": self.job_id,
            "event_type": "stage_start",
            "stage": stage_name,
            "stage_icon": stage_icon,
            "stage_number": completed_stages + 1,
            "progress": 0.0,  # 阶段刚开始，进度为0
            "overall_progress": overall_progress,
            "elapsed_time": 0.0,
            "total_elapsed": elapsed,
            "detail": detail,
            "formatted_message": log_message,
            "timestamp": stage_start_time,
            "stages_completed": completed_stages,
            "total_stages": total_processing_stages
        }
        
        try:
            # The incorrect local import was removed from here.
            # The call now uses the module imported at the top of the file.
            progress_cache.update_progress(self.job_id, event_data)
            self.log_info(f"[PROGRESS] Updated progress cache for stage start: {stage_name}")
        except Exception as e:
            self.log_warning(f"Failed to update progress cache for stage start: {str(e)}")
        
        # Log additional diagnostic information if available
        if detail:
            self.log_info(f"[JOB {self.job_id}] {stage_icon} {stage_name} details: {detail}")
            
        # If this is the first stage, log the overall job start
        if total_stages_seen == 1 and stage_name == ProcessingStage.INITIALIZED.value:
            self.log_info(f"📋 JOB {self.job_id} STARTED - {time.strftime('%Y-%m-%d %H:%M:%S')} - Processing pipeline initialized")
        
        # Sync to database
        self.sync_to_database(stage, "in_progress", 0.0, detail)
    
    def complete_stage(self, stage: ProcessingStage, detail: str = "", status: str = "completed") -> None:
        """Mark a processing stage as completed."""
        stage_name = stage.value
        stage_icon = ProcessingStage.get_icon(stage_name)
        
        if stage_name not in self.stages:
            self.log_warning(f"Completing stage {stage_name} that wasn't started")
            self.start_stage(stage)
            
        # Update stage tracking information
        end_time = time.time() # Calculate end_time early
        self.stages[stage_name]["end_time"] = end_time
        self.stages[stage_name]["status"] = status
        self.stages[stage_name]["detail"] = detail if detail else self.stages[stage_name]["detail"]
        
        # Calculate duration
        start_time = self.stages[stage_name]["start_time"]
        duration = end_time - start_time
        self.stages[stage_name]["duration"] = duration

        # Calculate total elapsed time early
        total_elapsed = end_time - self.start_time
        
        # Count progress updates for this stage
        progress_updates = len(self.stages[stage_name].get("progress_updates", []))
        
        # Create progress bar for completion
        progress_bar = "[" + "=" * 20 + "]" if status == "completed" else "[" + "X" * 20 + "]"
            
        # Format completion message
        completion_msg = f"{stage_icon} {status.upper()} | {stage_name}" # Default message
        if stage_name in [ProcessingStage.COMPLETED.value, ProcessingStage.FAILED.value]:
            # Special handling for final job completion/failure
            # This will be handled separately below
            pass
        else:
            # Normal stage completion
            completion_msg = f"{stage_icon} {status.upper()} | {stage_name} finished in {duration:.2f}s ({progress_updates} progress updates) | {progress_bar} 100.0% complete"
            
            # Add total time if we're tracking it
            # total_elapsed = end_time - self.start_time # Moved calculation up
            completion_msg += f" | Total time: {total_elapsed:.2f}s"
            
            self.log_info(f"[JOB {self.job_id}] {completion_msg}")
            
            # Log the stage result if there is detail
            if detail:
                self.log_info(f"[JOB {self.job_id}] {stage_name} result:\n    {detail}")            
        
        # 计算总体完成进度 - 使用动态阶段计数
        total_processing_stages = len(ProcessingStage.get_processing_stages())
        completed_stages = len([s for s in self.stages.values() if s["status"] == "completed"])
        overall_progress = (completed_stages / total_processing_stages) * 100 if total_processing_stages > 0 else 0
        
        # 创建阶段完成事件
        event_data = {
            "job_id": self.job_id,
            "event_type": "stage_complete",
            "stage": stage_name,
            "stage_icon": stage_icon,
            "status": status,
            "progress": 100.0,  # 阶段已完成，进度为100%
            "overall_progress": min(overall_progress, 99.9) if stage_name != ProcessingStage.COMPLETED.value else 100.0,
            "elapsed_time": duration,
            "total_elapsed": total_elapsed, # Now guaranteed to be defined
            "detail": detail,
            "formatted_message": completion_msg, # Use calculated completion_msg
            "timestamp": end_time,
            "stages_completed": completed_stages,
            "total_stages": len(ProcessingStage.get_processing_stages())
        }
        
        try:
            # The incorrect local import was removed from here.
            progress_cache.update_progress(self.job_id, event_data)
            self.log_info(f"[PROGRESS] Updated progress cache for stage completion: {stage_name}")
        except Exception as e:
            self.log_warning(f"Failed to update progress cache for stage completion: {str(e)}")
        
        # If this is the final COMPLETED stage, log a job completion summary
        if stage_name == ProcessingStage.COMPLETED.value:
            # Calculate total job time and completion stats
            # total_elapsed = end_time - self.start_time # Already calculated
            total_stages = len(self.stages)
            total_stages_completed = len([s for s in self.stages.values() if s["status"] == "completed"])
            
            # Calculate total time spent in each stage
            total_time = sum(s["duration"] or 0 for s in self.stages.values())
            
            # Build a summary of time spent in each stage
            stage_summary = ""
            for s_name, s_data in self.stages.items():
                if s_data["duration"] is not None:
                    icon = ProcessingStage.get_icon(s_name)
                    pct = (s_data["duration"] / total_time) * 100 if total_time > 0 else 0
                    stage_summary += f"    {icon} {s_name}: {s_data['duration']:.2f}s ({pct:.1f}%)\n"
            
            completion_message = f"\n🎉 JOB {self.job_id} COMPLETED SUCCESSFULLY - Total time: {total_time:.2f}s - Stages: {total_stages_completed}/{total_stages}\n{stage_summary}"
            self.log_info(completion_message)
            
            # 创建作业完成事件（100%完成）
            final_event = {
                "job_id": self.job_id,
                "event_type": "job_complete",
                "status": "completed",
                "overall_progress": 100.0,
                "total_elapsed": total_elapsed,
                "total_time": total_time,
                "stage_summary": stage_summary,
                "formatted_message": completion_message,
                "timestamp": end_time
            }
            
            try:
                # The incorrect local import was removed from here.
                progress_cache.update_progress(self.job_id, final_event)
                self.log_info(f"[PROGRESS] Updated progress cache for job completion: {self.job_id}")
            except Exception as e:
                self.log_warning(f"Failed to update progress cache for job completion: {str(e)}")

        # If this is the FAILED stage, log a job failure summary
        elif stage_name == ProcessingStage.FAILED.value:
            # Calculate total job time up to failure
            # total_elapsed = end_time - self.start_time # Already calculated
            total_stages = len(ProcessingStage.get_processing_stages()) # Expected stages
            stages_attempted = len(self.stages) -1 # Minus FAILED itself
            
            # Use the detail passed to complete_stage (which came from fail_stage) as the error message
            error_message = detail
            failure_summary = f"\n❌ JOB {self.job_id} FAILED - Total time: {total_elapsed:.2f}s - Stages attempted: {stages_attempted}/{total_stages} - Error: {error_message}"
            self.log_error(failure_summary) # Log as error
            
            # Create job failure event
            final_event = {
                "job_id": self.job_id,
                "event_type": "job_failed",
                "status": "failed",
                "overall_progress": overall_progress, # Progress up to failure
                "total_elapsed": total_elapsed,
                "error_message": error_message,
                "stage_failed": [s_name for s_name, s_data in self.stages.items() if s_data['status'] == 'failed'][0], # Get the name of the failed stage
                "formatted_message": failure_summary,
                "timestamp": end_time
            }
            
            try:
                # Send final failure event to cache
                progress_cache.update_progress(self.job_id, final_event)
                self.log_info(f"[PROGRESS] Updated progress cache for job failure: {self.job_id}")
            except Exception as e:
                self.log_warning(f"Failed to update progress cache for job failure: {str(e)}")
        
        # Sync completion to database (for all stages)
        final_progress = 100.0 if status == "completed" else 0.0
        self.sync_to_database(stage, status, final_progress, detail)
    
    def fail_stage(self, stage: ProcessingStage, error: str) -> None:
        """Mark a processing stage as failed."""
        # 记录错误日志
        self.log_error(f"[JOB {self.job_id}] Failed {stage.value} stage: {error}")
        
        # 计算持续时间，确保 total_elapsed 变量存在
        end_time = time.time()
        start_time = self.start_time
        total_elapsed = end_time - start_time
        
        # 标记阶段为失败
        self.complete_stage(stage, detail=error, status="failed")
    
    def log_progress(self, stage: ProcessingStage, progress: float, detail: str = "") -> None:
        """Log progress update within a stage."""
        stage_name = stage.value
        stage_icon = ProcessingStage.get_icon(stage_name)
        
        if stage_name not in self.stages:
            self.log_warning(f"Logging progress for stage {stage_name} that wasn't started")
            self.start_stage(stage)
        
        # Calculate timing information
        current_time = time.time()
        elapsed_in_stage = current_time - self.stages[stage_name]['start_time']
        
        # Initialize variables
        rate = 0
        eta = None
        
        # Only calculate rate if we've been running for more than 0.1 seconds to avoid division by zero
        if elapsed_in_stage > 0.1:
            rate = progress / elapsed_in_stage  # % per second
            if rate > 0:
                eta = max(0, (100 - progress) / rate)
        
        # Create the progress log message
        progress_msg = f"{stage_icon} {stage_name} | {progress:.1f}% | Time: {elapsed_in_stage:.2f}s"
        
        # Add ETA if available
        if eta is not None and not math.isinf(eta):
            progress_msg += f" | ETA: {eta:.1f}s"
        
        # Add detail if provided
        if detail:
            progress_msg += f"\n    └─ {detail}"
        
        # Log the full progress message
        self.log_info(f"[JOB {self.job_id}] {progress_msg}")
        
        # 更新进度缓存 - 前端实时显示用
        # 计算总体进度
        completed_stages = len([s for s in self.stages.values() if s["status"] == "completed"])
        total_stages_seen = len(self.stages)
        overall_progress = (completed_stages + (progress / 100)) / (total_stages_seen) * 100 if total_stages_seen > 0 else progress
        
        # Calculate total elapsed time across all stages
        total_elapsed = sum(
            stage_data.get('elapsed_time', 0) 
            for stage_data in self.stages.values()
            if 'elapsed_time' in stage_data
        )
        
        # Add current stage's elapsed time if not already included
        if stage_name in self.stages and 'elapsed_time' not in self.stages[stage_name]:
            total_elapsed += elapsed_in_stage
        
        # Create progress update event
        event_data = {
            "job_id": self.job_id,
            "stage": stage_name,
            "stage_icon": stage_icon,
            "progress": progress,
            "overall_progress": min(overall_progress, 99.9),  # Avoid showing 100% unless really completed
            "elapsed_time": elapsed_in_stage,
            "total_elapsed": total_elapsed,
            "eta": eta,
            "detail": detail,
            "formatted_message": progress_msg,
            "timestamp": current_time,
            "stages_completed": completed_stages,
            "total_stages": total_stages_seen
        }
        
        try:
            # The incorrect local import was removed from here.
            progress_cache.update_progress(self.job_id, event_data)
            self.log_info(f"[PROGRESS] Updated progress cache for job {self.job_id} at {progress:.1f}%")
        except Exception as e:
            self.log_warning(f"Failed to update progress cache: {str(e)}")
        
        # Sync progress to database
        self.sync_to_database(stage, "in_progress", progress, detail)

    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all processing stages."""
        total_time = sum(stage["duration"] or 0 for stage in self.stages.values())
        
        return {
            "job_id": self.job_id,
            "total_time": total_time,
            "stages": self.stages,
            "current_stage": self.current_stage
        }
    
    def log_info(self, message: str) -> None:
        """Log an info message."""
        # 添加时间戳，便于日志中显示明确的时间
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f"[{timestamp}] [JOB:{self.job_id}] {message}")
    
    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.logger.warning(f"[{timestamp}] [JOB:{self.job_id}] {message}")
    
    def log_error(self, message: str) -> None:
        """Log an error message."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.logger.error(f"[{timestamp}] [JOB:{self.job_id}] {message}")
