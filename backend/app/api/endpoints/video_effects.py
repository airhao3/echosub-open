import os
import subprocess
import tempfile
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.job import Job
from app.models.job_result import JobResult, ResultType
from app.core.config import get_settings
from app.utils.file_utils import ensure_directory_exists
from app.core.tasks import celery_app

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Pydantic models for request/response
class VideoEffect(BaseModel):
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    hue: float = 0.0
    blur: float = 0.0
    opacity: float = 1.0
    rotation: float = 0.0
    scale: float = 1.0
    cropTop: float = 0.0
    cropBottom: float = 0.0
    cropLeft: float = 0.0
    cropRight: float = 0.0
    flipHorizontal: bool = False
    flipVertical: bool = False
    noise: float = 0.0
    sharpen: float = 0.0
    vignette: float = 0.0
    colorTint: str = "#ffffff"
    grayscale: bool = False
    sepia: bool = False
    invert: bool = False

class ExportRequest(BaseModel):
    jobId: int
    effects: VideoEffect
    exportConfig: Dict[str, Any]

class ExportResponse(BaseModel):
    success: bool
    message: str
    taskId: Optional[str] = None
    estimatedTime: Optional[int] = None

class FFmpegCommand(BaseModel):
    command: str
    filters: List[str]
    estimated_processing_time: Optional[int] = None

class VideoEffectProcessor:
    """Class to handle video effect processing with FFmpeg"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        
    def generate_ffmpeg_filters(self, effects: VideoEffect) -> List[str]:
        """Generate FFmpeg filter chain from effects"""
        filters = []
        
        # Color adjustments
        if (effects.brightness != 1.0 or effects.contrast != 1.0 or 
            effects.saturation != 1.0 or effects.hue != 0.0):
            eq_params = []
            if effects.brightness != 1.0:
                eq_params.append(f"brightness={effects.brightness - 1.0:.2f}")
            if effects.contrast != 1.0:
                eq_params.append(f"contrast={effects.contrast:.2f}")
            if effects.saturation != 1.0:
                eq_params.append(f"saturation={effects.saturation:.2f}")
            if effects.hue != 0.0:
                eq_params.append(f"hue={effects.hue:.0f}*PI/180")
            
            filters.append(f"eq={':'.join(eq_params)}")
        
        # Blur effect
        if effects.blur > 0:
            blur_value = int(effects.blur * 2)  # Convert to FFmpeg blur units
            filters.append(f"boxblur={blur_value}:{blur_value}")
        
        # Geometric transformations
        transform_filters = []
        
        # Rotation
        if effects.rotation != 0:
            angle_rad = effects.rotation * 3.14159 / 180
            filters.append(f"rotate={angle_rad:.4f}")
        
        # Scale
        if effects.scale != 1.0:
            filters.append(f"scale=iw*{effects.scale:.2f}:ih*{effects.scale:.2f}")
        
        # Flip operations
        if effects.flipHorizontal:
            filters.append("hflip")
        if effects.flipVertical:
            filters.append("vflip")
        
        # Cropping
        if (effects.cropTop > 0 or effects.cropBottom > 0 or 
            effects.cropLeft > 0 or effects.cropRight > 0):
            # Calculate crop parameters
            crop_w = f"iw-{effects.cropLeft + effects.cropRight}*iw/100"
            crop_h = f"ih-{effects.cropTop + effects.cropBottom}*ih/100"
            crop_x = f"{effects.cropLeft}*iw/100"
            crop_y = f"{effects.cropTop}*ih/100"
            filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
        
        # Color effects
        if effects.grayscale:
            filters.append("colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3")
        
        if effects.sepia:
            filters.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
        
        if effects.invert:
            filters.append("negate")
        
        # Opacity/Alpha
        if effects.opacity < 1.0:
            filters.append(f"colorchannelmixer=aa={effects.opacity:.2f}")
        
        # Noise (using noise filter)
        if effects.noise > 0:
            noise_strength = int(effects.noise * 10)
            filters.append(f"noise=alls={noise_strength}:allf=t")
        
        # Sharpen
        if effects.sharpen > 0:
            sharpen_value = effects.sharpen / 10.0  # Normalize
            filters.append(f"unsharp=5:5:{sharpen_value:.2f}:5:5:{sharpen_value:.2f}")
        
        # Vignette effect
        if effects.vignette > 0:
            vignette_strength = effects.vignette / 100.0
            filters.append(f"vignette=PI/4:{vignette_strength:.2f}")
        
        return filters
    
    def build_ffmpeg_command(self, input_path: str, output_path: str, 
                           effects: VideoEffect, export_config: Dict[str, Any]) -> str:
        """Build complete FFmpeg command"""
        filters = self.generate_ffmpeg_filters(effects)
        
        cmd = ["ffmpeg", "-y", "-i", input_path]
        
        # Add video filters
        if filters:
            filter_complex = ",".join(filters)
            cmd.extend(["-vf", filter_complex])
        
        # Video codec and quality settings
        format_type = export_config.get("format", "mp4")
        quality = export_config.get("quality", "high")
        resolution = export_config.get("resolution", "original")
        
        if format_type == "mp4":
            cmd.extend(["-c:v", "libx264"])
            if quality == "high":
                cmd.extend(["-crf", "18"])
            elif quality == "medium":
                cmd.extend(["-crf", "23"])
            elif quality == "low":
                cmd.extend(["-crf", "28"])
        elif format_type == "webm":
            cmd.extend(["-c:v", "libvpx-vp9"])
            if quality == "high":
                cmd.extend(["-crf", "30", "-b:v", "2000k"])
            elif quality == "medium":
                cmd.extend(["-crf", "32", "-b:v", "1000k"])
            elif quality == "low":
                cmd.extend(["-crf", "35", "-b:v", "500k"])
        
        # Resolution scaling
        if resolution != "original":
            if resolution == "1080p":
                cmd.extend(["-vf", "scale=1920:1080" + ("," + ",".join(filters) if filters else "")])
            elif resolution == "720p":
                cmd.extend(["-vf", "scale=1280:720" + ("," + ",".join(filters) if filters else "")])
            elif resolution == "480p":
                cmd.extend(["-vf", "scale=854:480" + ("," + ",".join(filters) if filters else "")])
        
        # Audio handling
        if export_config.get("includeAudio", True):
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])
        
        # Output format
        cmd.extend(["-f", format_type])
        cmd.append(output_path)
        
        return " ".join(cmd)
    
    def estimate_processing_time(self, input_path: str, effects: VideoEffect) -> int:
        """Estimate processing time in seconds based on video duration and effects complexity"""
        try:
            # Get video duration using ffprobe
            probe_cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", 
                "-show_format", "-show_streams", input_path
            ]
            
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return 60  # Default estimate
            
            info = json.loads(result.stdout)
            duration = float(info["format"]["duration"])
            
            # Calculate complexity factor based on active effects
            complexity = 1.0
            if effects.blur > 0:
                complexity += 0.5
            if effects.rotation != 0:
                complexity += 0.3
            if effects.scale != 1.0:
                complexity += 0.2
            if effects.flipHorizontal or effects.flipVertical:
                complexity += 0.1
            if effects.noise > 0:
                complexity += 0.4
            if effects.sharpen > 0:
                complexity += 0.3
            
            # Estimate: roughly 1 second processing per 10 seconds of video * complexity
            estimated_seconds = int(duration * complexity * 0.1)
            return max(estimated_seconds, 5)  # Minimum 5 seconds
            
        except Exception as e:
            logger.error(f"Error estimating processing time: {e}")
            return 60  # Default fallback

# Initialize processor
processor = VideoEffectProcessor()

@router.post("/preview-command", response_model=FFmpegCommand)
async def preview_ffmpeg_command(
    effects: VideoEffect,
    export_config: Dict[str, Any] = None,
    current_user: User = Depends(deps.get_current_user)
):
    """Generate FFmpeg command preview without processing"""
    try:
        if export_config is None:
            export_config = {"format": "mp4", "quality": "high", "resolution": "original", "includeAudio": True}
        
        filters = processor.generate_ffmpeg_filters(effects)
        sample_input = "/path/to/input.mp4"
        sample_output = f"/path/to/output.{export_config.get('format', 'mp4')}"
        
        command = processor.build_ffmpeg_command(
            sample_input, sample_output, effects, export_config
        )
        
        return FFmpegCommand(
            command=command,
            filters=filters,
            estimated_processing_time=30  # Sample estimate
        )
        
    except Exception as e:
        logger.error(f"Error generating FFmpeg command preview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating command preview: {str(e)}"
        )

@router.post("/export", response_model=ExportResponse)
async def export_video_with_effects(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start video export process with effects"""
    try:
        # Validate job ownership
        job = db.query(Job).filter(Job.id == request.jobId).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Find source video
        if not job.source_video_url or not os.path.exists(job.source_video_url):
            raise HTTPException(status_code=404, detail="Source video not found")
        
        # Estimate processing time
        estimated_time = processor.estimate_processing_time(
            job.source_video_url, request.effects
        )
        
        # Create output directory
        output_dir = os.path.join(settings.DATA_PATH, f"jobs/{job.id}/effects")
        ensure_directory_exists(output_dir)
        
        # Generate output filename
        format_ext = request.exportConfig.get("format", "mp4")
        output_filename = f"video_with_effects_{job.id}.{format_ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        # Create Celery task for background processing
        task = process_video_effects_task.delay(
            job_id=request.jobId,
            input_path=job.source_video_url,
            output_path=output_path,
            effects_dict=request.effects.dict(),
            export_config=request.exportConfig,
            user_id=current_user.id
        )
        
        return ExportResponse(
            success=True,
            message="Video export started successfully",
            taskId=task.id,
            estimatedTime=estimated_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting video export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting export: {str(e)}"
        )

@router.get("/export-status/{task_id}")
async def get_export_status(
    task_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """Get export task status"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        if task_result.state == "PENDING":
            response = {
                "state": task_result.state,
                "status": "Task is waiting to be processed"
            }
        elif task_result.state == "PROGRESS":
            response = {
                "state": task_result.state,
                "progress": task_result.info.get("progress", 0),
                "status": task_result.info.get("status", "")
            }
        elif task_result.state == "SUCCESS":
            response = {
                "state": task_result.state,
                "progress": 100,
                "status": "Export completed successfully",
                "result": task_result.info
            }
        else:  # FAILURE
            response = {
                "state": task_result.state,
                "status": str(task_result.info)
            }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error getting export status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}"
        )

@router.get("/download-result/{job_id}")
async def download_processed_video(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Download the processed video with effects"""
    try:
        # Validate job ownership
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Find the processed video file
        effects_dir = os.path.join(settings.DATA_PATH, f"jobs/{job_id}/effects")
        
        if not os.path.exists(effects_dir):
            raise HTTPException(status_code=404, detail="No processed videos found")
        
        # Find the most recent processed video
        video_files = []
        for ext in ['mp4', 'webm', 'mov', 'avi']:
            pattern = os.path.join(effects_dir, f"video_with_effects_{job_id}.{ext}")
            if os.path.exists(pattern):
                video_files.append(pattern)
        
        if not video_files:
            raise HTTPException(status_code=404, detail="Processed video not found")
        
        # Return the most recent file
        video_path = max(video_files, key=os.path.getctime)
        
        return FileResponse(
            path=video_path,
            media_type="video/mp4",
            filename=os.path.basename(video_path),
            headers={"Content-Disposition": f"attachment; filename={os.path.basename(video_path)}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading processed video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading video: {str(e)}"
        )

# Celery task for background video processing
@celery_app.task(bind=True)
def process_video_effects_task(self, job_id: int, input_path: str, output_path: str, 
                              effects_dict: Dict[str, Any], export_config: Dict[str, Any], 
                              user_id: int):
    """Background task to process video with effects"""
    try:
        # Update task state
        self.update_state(
            state="PROGRESS",
            meta={"progress": 10, "status": "Initializing video processing..."}
        )
        
        # Convert effects dict back to VideoEffect
        effects = VideoEffect(**effects_dict)
        
        # Build FFmpeg command
        command = processor.build_ffmpeg_command(input_path, output_path, effects, export_config)
        
        self.update_state(
            state="PROGRESS",
            meta={"progress": 20, "status": "Starting FFmpeg processing..."}
        )
        
        # Execute FFmpeg command
        process = subprocess.Popen(
            command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Monitor progress (simplified - in real implementation, parse FFmpeg output)
        progress_steps = [30, 40, 50, 60, 70, 80, 90]
        for progress in progress_steps:
            if process.poll() is None:  # Process still running
                self.update_state(
                    state="PROGRESS",
                    meta={"progress": progress, "status": f"Processing video... {progress}%"}
                )
                # Sleep briefly to simulate progress
                import time
                time.sleep(2)
        
        # Wait for completion
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg failed: {stderr}")
            raise Exception(f"Video processing failed: {stderr}")
        
        # Verify output file was created
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Output video file was not created or is empty")
        
        # Save result to database
        from app.api.deps import get_db
        db = next(get_db())
        
        try:
            job_result = JobResult(
                job_id=job_id,
                result_type=ResultType.PROCESSED_VIDEO,
                file_path=output_path,
                metadata_={"effects": effects_dict, "export_config": export_config}
            )
            db.add(job_result)
            db.commit()
        except Exception as db_error:
            logger.error(f"Error saving result to database: {db_error}")
            # Continue anyway, file is created successfully
        finally:
            db.close()
        
        return {
            "progress": 100,
            "status": "Video processing completed successfully",
            "output_path": output_path,
            "file_size": os.path.getsize(output_path)
        }
        
    except Exception as e:
        logger.error(f"Video processing task failed: {e}")
        self.update_state(
            state="FAILURE",
            meta={"status": str(e)}
        )
        raise