import logging
import mimetypes
import os
import tempfile
import datetime
import zipfile
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api import deps
from app.api.url_token_auth import get_user_from_url_token
from app.models.job import Job, JobStatus, JobResult, ResultType
from app.models.user import User
from app.services.job_service import JobService
from app.services.workflow_service import WorkflowService

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_up_temp_files(temp_files: List[str], temp_dir: str) -> None:
    """Clean up temporary files and directories."""
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError as e:
                logger.error(f"Error removing temporary file {temp_file}: {e}")
    if temp_dir and os.path.exists(temp_dir):
        try:
            os.rmdir(temp_dir)
        except OSError as e:
            logger.error(f"Error removing temporary directory {temp_dir}: {e}")

@router.api_route("/results/{job_id}/{result_type}", methods=["GET", "HEAD"])
async def download_result(
    request: Request,
    job_id: int,
    result_type: str,
    language: str = Query(None),
    streamable: bool = Query(False),
    token: str = Query(None),
    db: Session = Depends(deps.get_db),
):
    logger.info(f"--- Download request received for job_id={job_id}, result_type='{result_type}', language='{language}', streamable={streamable} ---")
    
    current_user = await get_user_from_url_token(request, db)
    if not current_user:
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                from app.core.security import verify_token
                payload = verify_token(token)
                user_id = int(payload.get("sub"))
                current_user = db.query(User).filter(User.id == user_id).first()
                if current_user:
                    logger.info(f"Authenticated with header token: User {current_user.id}")
        except Exception as e:
            logger.warning(f"Header token authentication failed: {str(e)}")
            current_user = None

    if not current_user:
        # Fallback to default user in open-source single-user mode
        current_user = deps.get_current_user(db)
        if current_user:
            logger.info(f"Using default user fallback: User {current_user.id}")
        else:
            logger.warning(f"Authentication failed for job {job_id}. Denying access.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        result_type_enum = next(t for t in ResultType if t.value == result_type or t.name.lower() == result_type.lower())
        logger.info(f"Successfully validated result_type '{result_type}' to {result_type_enum}")
    except StopIteration:
        valid_types = [t.value for t in ResultType]
        logger.error(f"Invalid result type: '{result_type}'. Valid types are: {valid_types}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid result type. Valid types: {valid_types}")

    data_dir = os.environ.get("VIDEOLINGO_DATA_DIR", "/tmp/videolingo_jobs")
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with ID {job_id} not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        logger.warning(f"Access denied: User {current_user.id} attempted to access job {job_id} owned by {job.owner_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    logger.info(f"Access granted for User {current_user.id} to Job {job_id}")

    result = None
    if result_type_enum == ResultType.SUBTITLED_VIDEO:
        logger.info(f"Searching for primary JobResult: job_id={job_id}, result_type={result_type_enum}, language={language}")
        result = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == result_type_enum,
            JobResult.language == language
        ).first()
        
        if not result:
            logger.warning(f"Primary JobResult not found. Trying to find any subtitled video for job {job_id}.")
            result = db.query(JobResult).filter(
                JobResult.job_id == job_id,
                JobResult.result_type == result_type_enum
            ).first()
            if not result:
                logger.warning("Fallback subtitled video not found either. Falling back to original video.")
                result = db.query(JobResult).filter(
                    JobResult.job_id == job_id,
                    JobResult.result_type == ResultType.ORIGINAL_VIDEO
                ).first()

    else:
        logger.info(f"Searching for JobResult: job_id={job_id}, result_type={result_type_enum}")
        result = db.query(JobResult).filter(
            JobResult.job_id == job_id, 
            JobResult.result_type == result_type_enum
        ).first()

    if not result:
        logger.warning(f"No result record found in DB for job {job_id} and type {result_type_enum} after all fallbacks.")
        logger.info(f"Attempting intelligent file system search for {result_type} job {job_id}")
        
        # Try intelligent file system search when database record is missing
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and result_type_enum in [ResultType.ORIGINAL_VIDEO, ResultType.SUBTITLED_VIDEO]:
            from app.core.config import get_settings
            settings = get_settings()
            storage_base = settings.STORAGE_BASE_DIR
            possible_paths = [
                os.path.join(storage_base, "users", str(job.owner_id), "jobs", str(job_id), "source"),
                os.path.join(storage_base, "jobs", str(job_id)),
            ]

            found_video = None
            for search_path in possible_paths:
                if os.path.isdir(search_path):
                    logger.info(f"Searching in directory: {search_path}")
                    for file in os.listdir(search_path):
                        file_lower = file.lower()
                        if file_lower.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                            if result_type_enum == ResultType.ORIGINAL_VIDEO and not file_lower.endswith('_subtitled.mp4'):
                                found_video = os.path.join(search_path, file)
                                logger.info(f"🎯 Found potential original video: {file}")
                                break
                            elif result_type_enum == ResultType.SUBTITLED_VIDEO and 'subtitled' in file_lower:
                                found_video = os.path.join(search_path, file)
                                logger.info(f"🎯 Found potential subtitled video: {file}")
                                break
                    if found_video:
                        break
            
            if found_video and os.path.exists(found_video):
                logger.info(f"✅ Smart search SUCCESS: Found {result_type} video at {found_video}")
                # Create a direct FileResponse for the found video
                file_name = os.path.basename(found_video)
                media_type, _ = mimetypes.guess_type(file_name)
                if not media_type:
                    media_type = 'application/octet-stream'
                
                return FileResponse(
                    path=found_video,
                    media_type=media_type,
                    filename=file_name,
                    headers={
                        "Content-Disposition": "inline" if streamable else "attachment",
                        "Accept-Ranges": "bytes",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges, Content-Disposition",
                        "Cache-Control": "no-cache"
                    }
                )
        
        # If smart search fails or not applicable
        logger.error(f"❌ No video file found for job {job_id} type {result_type_enum} anywhere")
        raise HTTPException(status_code=404, detail="Result file metadata not found in database.")
    
    # Use file_path instead of file_url
    file_path = getattr(result, 'file_path', None)
    if not file_path:
        logger.error(f"Result record for job {job_id} is missing file_path")
        raise HTTPException(status_code=500, detail="File path not found in result record.")
    
    # Make sure the path is absolute
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    
    logger.info(f"Looking for file at path: {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"File not found on disk at path: {file_path}")
        # Try to find the file in the job directory as a fallback
        job_dir = os.path.join(data_dir, f"job_{job_id}")
        fallback_path = os.path.join(job_dir, os.path.basename(file_path))
        if os.path.exists(fallback_path):
            logger.info(f"Found file at fallback location: {fallback_path}")
            file_path = fallback_path
        else:
            # Enhanced smart file search for missing video files
            logger.info(f"Trying intelligent file system search for {result_type} job {job_id}")
            
            # Get job info for smart searching
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and result_type_enum in [ResultType.ORIGINAL_VIDEO, ResultType.SUBTITLED_VIDEO]:
                from app.core.config import get_settings
                settings = get_settings()
                storage_base = settings.STORAGE_BASE_DIR
                possible_paths = [
                    os.path.join(storage_base, "users", str(job.owner_id), "jobs", str(job_id), "source"),
                    os.path.join(storage_base, "jobs", str(job_id)),
                ]
                
                found_video = None
                for search_path in possible_paths:
                    if os.path.isdir(search_path):
                        logger.info(f"Searching in directory: {search_path}")
                        for file in os.listdir(search_path):
                            file_lower = file.lower()
                            if file_lower.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                                if result_type_enum == ResultType.ORIGINAL_VIDEO and not file_lower.endswith('_subtitled.mp4'):
                                    found_video = os.path.join(search_path, file)
                                    break
                                elif result_type_enum == ResultType.SUBTITLED_VIDEO and 'subtitled' in file_lower:
                                    found_video = os.path.join(search_path, file)
                                    break
                        if found_video:
                            break
                
                if found_video and os.path.exists(found_video):
                    logger.info(f"✅ Smart search found video at: {found_video}")
                    file_path = found_video
                else:
                    logger.error(f"❌ Smart search failed to find {result_type} video for job {job_id}")
                    raise HTTPException(status_code=404, detail=f"Result file not found anywhere. Smart search completed.")
            else:
                logger.error(f"File not found at fallback location: {fallback_path}")
                raise HTTPException(status_code=404, detail=f"Result file not found on disk. Tried: {file_path} and {fallback_path}")

    logger.info(f"File found at {file_path}. Preparing response.")
    file_name = os.path.basename(file_path)
    media_type, _ = mimetypes.guess_type(file_name)
    media_type = media_type or "application/octet-stream"

    def file_iterator(file_path, chunk_size=8192):
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    if streamable and media_type.startswith("video/"):
        logger.info(f"Serving video file {file_name} with streaming support.")
        
        # Get file size for range requests
        file_size = os.path.getsize(file_path)
        
        # Handle range requests for streaming
        range_header = request.headers.get('Range')
        if range_header:
            logger.info(f"Range header received: {range_header}")
            
            # Parse range header
            start, end = 0, None
            range_ = range_header.replace('bytes=', '').split('-')
            if len(range_) == 2:
                start, end = range_
                start = int(start) if start else 0
                end = int(end) if (end and end.strip()) else file_size - 1
            
            # Ensure end is within file bounds
            end = min(end, file_size - 1) if end is not None else file_size - 1
            
            # Create a streaming response with range support
            chunk_size = 8192 * 4  # 32KB chunks
            
            def stream_file():
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = (end - start + 1) if end is not None else file_size - start
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            # Encode filename for Content-Disposition header
            try:
                # Try ASCII-only filename first
                file_name.encode('ascii')
                content_disposition = f'inline; filename="{file_name}"'
            except UnicodeEncodeError:
                # If filename contains non-ASCII, use RFC 5987 encoding
                import urllib.parse
                encoded_filename = urllib.parse.quote(file_name, encoding='utf-8')
                # Use a safe ASCII fallback for the regular filename parameter
                safe_filename = ''.join(c if c.isascii() and c.isprintable() else '_' for c in file_name)
                content_disposition = f'inline; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
                
            headers = {
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Content-Length': str((end - start + 1)),
                'Content-Type': media_type,
                'Content-Disposition': content_disposition,
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Expose-Headers': 'Content-Range, Content-Length, Accept-Ranges, Content-Disposition',
            }
            
            return StreamingResponse(
                content=stream_file(),
                status_code=206,
                headers=headers,
                media_type=media_type
            )
        else:
            # No range header, return full file
            # Encode filename for Content-Disposition header
            try:
                # Try ASCII-only filename first
                file_name.encode('ascii')
                content_disposition = f'inline; filename="{file_name}"'
            except UnicodeEncodeError:
                # If filename contains non-ASCII, use RFC 5987 encoding
                import urllib.parse
                encoded_filename = urllib.parse.quote(file_name, encoding='utf-8')
                # Use a safe ASCII fallback for the regular filename parameter
                safe_filename = ''.join(c if c.isascii() and c.isprintable() else '_' for c in file_name)
                content_disposition = f'inline; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
                
            headers = {
                'Accept-Ranges': 'bytes',
                'Content-Length': str(file_size),
                'Content-Type': media_type,
                'Content-Disposition': content_disposition,
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Expose-Headers': 'Content-Range, Content-Length, Accept-Ranges, Content-Disposition',
            }
            
            def file_iterator():
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192 * 4):  # 32KB chunks
                        yield chunk
            
            return StreamingResponse(
                content=file_iterator(),
                status_code=200,
                headers=headers,
                media_type=media_type
            )
    else:
        logger.info(f"Serving file {file_name} as a direct download.")
        # Prepare Content-Disposition for FileResponse
        import urllib.parse
        if file_name.isascii():
            content_disposition = f'attachment; filename="{file_name}"'
        else:
            encoded_filename = urllib.parse.quote(file_name, encoding='utf-8')
            safe_filename = ''.join(c if c.isascii() and c.isprintable() else '_' for c in file_name)
            content_disposition = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type=media_type,
            headers={
                'Content-Disposition': content_disposition,
                'Access-Control-Allow-Origin': '*',  # For testing - restrict in production
                'Access-Control-Expose-Headers': 'Content-Disposition',
            }
        )

@router.post("/reprocess_result")
async def reprocess_result(
    request: Request,
    db: Session = Depends(deps.get_db),
):
    data = await request.json()
    job_id = data.get("job_id")
    target_language = data.get("target_language")
    
    if not job_id or not target_language:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id and target_language are required"
        )
    
    current_user = await get_user_from_url_token(request, db)
    if not current_user:
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                from app.core.security import verify_token
                payload = verify_token(token)
                user_id = int(payload.get("sub"))
                current_user = db.query(User).filter(User.id == user_id).first()
        except Exception:
            current_user = None

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    data_dir = os.environ.get("VIDEOLINGO_DATA_DIR", "/tmp/videolingo_jobs")
    job_service = JobService(db, data_dir)
    job = job_service.get_job_by_id(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
    
    workflow_service = WorkflowService(db, data_dir)
    try:
        reprocessing_job = workflow_service.reprocess_translation_for_job(job_id, target_language)
        return {"message": "Reprocessing started successfully", "job_id": reprocessing_job.id}
    except Exception as e:
        logger.error(f"Failed to start reprocessing for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start reprocessing"
        )

@router.get("/zip/{job_id}", response_class=FileResponse)
@router.get("/job/{job_id}/all", response_class=FileResponse)
async def download_all_results(
    *,
    job_id: int,
    video_id: Optional[str] = None,
    simplified: bool = False,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Download results for a specific video in a job as a zip file
    """
    data_dir = os.environ.get("VIDEOLINGO_DATA_DIR", "/tmp/videolingo_jobs")
    job_service = JobService(db, data_dir)
    job = job_service.get_job_by_id(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
    
    results = db.query(JobResult).filter(JobResult.job_id == job_id).all()
    
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No results found for job {job_id}"
        )
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    video_name = os.path.splitext(job.video_filename)[0] if job and job.video_filename else None
    
    temp_dir = tempfile.mkdtemp(prefix=f"job_{job_id}_")
    
    files_to_zip = []
    for result in results:
        file_path = result.file_path
        if not os.path.isabs(file_path):
            file_path = os.path.join(data_dir, file_path)
            
        if os.path.exists(file_path):
            files_to_zip.append(file_path)
        else:
            logger.warning(f"File not found, skipping: {file_path}")

    if not files_to_zip:
        clean_up_temp_files([], temp_dir)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result files found on disk to zip."
        )

    zip_filename_base = video_name or f"job_{job_id}"
    zip_path = os.path.join(temp_dir, f"{zip_filename_base}_{timestamp}.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files_to_zip:
            arcname = os.path.basename(file)
            zipf.write(file, arcname)
            
    response = FileResponse(
        path=zip_path,
        filename=os.path.basename(zip_path),
        media_type='application/zip',
    )
    
    response.background = BackgroundTask(clean_up_temp_files, [zip_path], temp_dir)
    
    return response
    # Use a temp directory within our configured base directory
    from app.core.config import get_settings
    settings = get_settings()
    temp_base = os.path.join(settings.STORAGE_BASE_DIR, "tmp")
    os.makedirs(temp_base, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix=f"videolingo_download_{job_id}_", dir=temp_base)
    logger.info(f"Created temporary directory for download: {temp_dir}")
    logger.info(f"Created temporary directory: {temp_dir}")
    
    # Set up the zip file path
    if video_name:
        zip_filename = f"{video_name}_output.zip"
    else:
        zip_filename = f"{job_id}_output.zip"
    
    zip_path = os.path.join(temp_dir, zip_filename)
    logger.info(f"Creating zip file at: {zip_path}")
    
    # List to keep track of temporary files for cleanup
    temp_files = [zip_path]
    
    # Get the job directory to scan for files
    job_dir = job_service.get_job_directory(job_id)
    logger.info(f"Using job directory: {job_dir}")
    
    # Get the job record to find the original filename (for ZIP naming)
    job = db.query(Job).filter(Job.id == job_id).first()
    video_name_for_zip = None
    
    if job and job.video_filename:
        # Use original filename for the ZIP name
        video_name_for_zip = os.path.splitext(job.video_filename)[0]
        logger.info(f"Using original filename for ZIP: {video_name_for_zip}")
        
    # Use the new directory structure directly - no complex filtering needed
    # We know exactly where the files are stored for this job
    
    # Collection of directories to process
    dirs_to_process = []
    
    # Get all video directories matching the job prefix pattern
    prefix = f"job{job_id}_"
    video_subdirs = [os.path.join(job_dir, d) for d in os.listdir(job_dir)
                   if os.path.isdir(os.path.join(job_dir, d)) and d.startswith(prefix)]
    
    if not video_subdirs:
        logger.warning(f"No video subdirectories found with prefix '{prefix}' in {job_dir}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No video directories found"
        )
    
    logger.info(f"Found {len(video_subdirs)} video directories with prefix '{prefix}'")
    
    # When video_id is provided, ONLY include that specific video directory
    if video_id:
        logger.info(f"Looking for specific video ID: {video_id}")
        exact_match_dirs = [d for d in video_subdirs if video_id in os.path.basename(d)]
        
        # Try match
        if exact_match_dirs:
            # We found a match - ONLY include this directory
            matched_dir = exact_match_dirs[0]  # Take the first match if multiple
            dirs_to_process = [matched_dir]  # ONLY this directory, nothing else
            logger.info(f"Found match for video ID {video_id}: {matched_dir}")
            
            # Also update ZIP filename to include this video ID
            if video_name_for_zip:
                video_name_for_zip = f"{video_name_for_zip}_{video_id}"
                logger.info(f"Updated ZIP filename to include video ID: {video_name_for_zip}")
        else:
            # Try partial match if no exact match found
            partial_match_dirs = [d for d in video_subdirs if video_id in os.path.basename(d)]
            
            if partial_match_dirs:
                matched_dir = partial_match_dirs[0]  # Take the first match if multiple
                dirs_to_process = [matched_dir]  # ONLY this directory, nothing else
                logger.info(f"Found partial match for video ID {video_id}: {matched_dir}")
                
                # Also update ZIP filename to include this video ID
                if video_name_for_zip:
                    video_name_for_zip = f"{video_name_for_zip}_{video_id}"
                    logger.info(f"Updated ZIP filename to include video ID: {video_name_for_zip}")
            else:
                # No match found for this video_id
                logger.warning(f"No matching directory found for video ID: {video_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No directory found matching video ID {video_id}"
                )
    else:
        # No specific video_id provided, include all video directories
        # but NOT the job directory or output directory
        dirs_to_process = video_subdirs
        logger.info(f"Including all {len(video_subdirs)} video subdirectories")
        
        # Optionally include the job directory for summary file
        # Add this only when downloading ALL videos, as it's not specific to any one video
        dirs_to_process.append(job_dir)
            
    logger.info(f"Will process {len(dirs_to_process)} directories: {dirs_to_process}")
    
    # Create a ZIP file that preserves the exact original directory structure
    import zipfile
    import io
    import re
    from pathlib import Path
    
    try:
        # Update the zip filename if we found a video name
        if video_name_for_zip:
            # Sanitize filename to remove problematic characters
            safe_name = re.sub(r'[^\w\-_\. ]', '_', video_name_for_zip)
            zip_filename = f"{safe_name}_output.zip"
        # If no specific directory was selected yet, include all video subdirectories
        if not dirs_to_process:
            dirs_to_process = video_subdirs
            logger.info(f"Including all video directories: {len(dirs_to_process)}")
        
        # Create the zip file with selected directories
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Counter for files added
            file_count = 0
            
            # Process each directory separately to organize the files nicely
            for dir_path in dirs_to_process:
                # Get directory name for organizing files in ZIP
                dir_name = os.path.basename(dir_path)
                logger.info(f"Processing directory: {dir_path} ({dir_name})")
                
                # Walk through all files in this directory
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        # Get relative path from job directory for ZIP structure
                        # This maintains the original directory structure
                        try:
                            # Use relative path to job dir to preserve structure
                            rel_path = os.path.relpath(file_path, job_dir)
                            zip_path_name = rel_path
                        except ValueError:
                            # Fallback if paths are on different drives
                            zip_path_name = os.path.basename(file_path)
                        
                        # Get file size for logging and large file handling
                        file_size = os.path.getsize(file_path)
                        
                        logger.info(f"Adding to ZIP: {file_path} -> {zip_path_name} ({file_size/1024:.1f} KB)")
                        
                        # Handle large files (>100MB) with streaming to reduce memory usage
                        if file_size > 100 * 1024 * 1024:  # 100MB threshold
                            try:
                                with open(file_path, 'rb') as f_in:
                                    with zipf.open(zip_path_name, 'w') as f_out:
                                        chunk_size = 4 * 1024 * 1024  # 4MB chunks
                                        bytes_written = 0
                                        while True:
                                            chunk = f_in.read(chunk_size)
                                            if not chunk:
                                                break
                                            f_out.write(chunk)
                                            bytes_written += len(chunk)
                                        
                                        if bytes_written > 0:
                                            logger.info(f"Successfully added large file {file} ({bytes_written/1024/1024:.1f} MB)")
                            except Exception as e:
                                logger.error(f"Error adding large file {file}: {str(e)}")
                        else:
                            # Use standard method for regular files
                            zipf.write(file_path, zip_path_name)
                        
                        file_count += 1
                        
            logger.info(f"Added {file_count} files to ZIP with preserved directory structure")
        
        # Verify the zip file was created successfully
        if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
            logger.info(f"Successfully created zip file at {zip_path}")
            
            # Use the video name for the download file
            if video_name_for_zip:
                download_filename = f"{video_name_for_zip}_output.zip"
            else:
                # Fallback if no video name was found
                download_filename = f"{job_id}_output.zip"
            
            return FileResponse(
                path=zip_path,
                filename=download_filename,
                media_type="application/zip",
                # Important: Set these headers to prevent caching issues
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        else:
            # Clean up if zip was created but is empty or invalid
            logger.error(f"Zip file creation failed or resulted in empty file: {zip_path}")
            clean_up_temp_files(temp_files, temp_dir)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create zip file for job {job_id} results"
            )
            
    except Exception as e:
        # Log the error and clean up temporary files
        logger.error(f"Error creating zip file: {str(e)}")
        clean_up_temp_files(temp_files, temp_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating zip file: {str(e)}"
        )


@router.get("/current/{job_id}", response_class=FileResponse)
async def download_current_videos(
    *,
    job_id: int,
    video_id: Optional[str] = None,  # Optional specific video ID to download
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Download current processed videos for a job using WorkflowService
    This endpoint directly accesses the video paths created by the workflow process
    """
    import tempfile
    import datetime
    
    # Get job and validate ownership
    data_dir = os.environ.get("VIDEOLINGO_DATA_DIR", "/tmp/videolingo_jobs")
    job_service = JobService(db, data_dir)
    workflow_service = WorkflowService(db, data_dir)
    job = job_service.get_job_by_id(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
    
    # Get all processed video paths for this job using the new directory structure
    # Video directories now follow the pattern: job{job_id}_{video_name}_{hash}
    job_dir = job_service.get_job_directory(job_id)
    prefix = f"job{job_id}_"
    video_dirs = [os.path.join(job_dir, d) for d in os.listdir(job_dir)
                 if os.path.isdir(os.path.join(job_dir, d)) and d.startswith(prefix)]
    
    if not video_dirs:
        logger.warning(f"No video directories found with prefix '{prefix}' in {job_dir}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No processed videos found for job {job_id}"
        )
    
    logger.info(f"Found {len(video_dirs)} video directories with prefix '{prefix}'")
    
    # Filter for specific video if video_id is provided
    if video_id:
        logger.info(f"Looking for specific video ID: {video_id}")
        # Try match based on video_id being contained in the directory name
        match_dirs = [d for d in video_dirs if video_id in os.path.basename(d)]
        
        if match_dirs:
            video_dirs = match_dirs
            logger.info(f"Found match for video ID '{video_id}': {len(match_dirs)} directories")
        else:
            # No match found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No directory found matching video ID {video_id}"
            )
    
    # Get the job directory
    job_dir = job_service.get_job_directory(job_id)
    
    # Create a temporary directory for the zip file
    # Use a temp directory within our configured base directory
    from app.core.config import get_settings
    settings = get_settings()
    temp_base = os.path.join(settings.STORAGE_BASE_DIR, "tmp")
    os.makedirs(temp_base, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix=f"videolingo_current_download_{job_id}_", dir=temp_base)
    logger.info(f"Created temporary directory for current download: {temp_dir}")
    logger.info(f"Created temporary directory: {temp_dir}")
    
    # Get video filename for ZIP naming
    video_name = None
    if job and job.video_filename:
        video_name = os.path.splitext(job.video_filename)[0]
        logger.info(f"Using video name for download: {video_name}")
    
    # Set up the zip file path
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    if video_name:
        zip_filename = f"{video_name}_current_{timestamp}.zip"
    else:
        zip_filename = f"{job_id}_current_{timestamp}.zip"
    
    zip_path = os.path.join(temp_dir, zip_filename)
    logger.info(f"Creating zip file at: {zip_path}")
    
    # List to keep track of temporary files for cleanup
    temp_files = [zip_path]
    
    # Create ZIP file with the processed videos
    import zipfile
    import io
    import re
    from pathlib import Path
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Track number of files added
            file_count = 0
            
            # Process each video directory
            for video_dir in video_dirs:
    # If output directory exists, include it too
                if not os.path.exists(video_dir) or not os.path.isdir(video_dir):
                    logger.warning(f"Video directory not found or not a directory: {video_dir}")
                    continue
                    
                logger.info(f"Processing video directory: {video_dir}")
                
                # Get video name for organizing files in ZIP
                video_dir_name = os.path.basename(video_dir)
                
                # Walk through all files in this directory
                for root, _, files in os.walk(video_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        # Get relative path from job directory for ZIP structure
                        # This maintains the original directory structure
                        try:
                            # Use relative path to job dir to preserve structure
                            rel_path = os.path.relpath(file_path, job_dir)
                            zip_path_name = rel_path
                        except ValueError:
                            # Fallback if paths are on different drives
                            zip_path_name = os.path.join(video_dir_name, os.path.relpath(file_path, video_dir))
                        
                        # Get file size for logging and large file handling
                        file_size = os.path.getsize(file_path)
                        
                        logger.info(f"Adding to ZIP: {file_path} -> {zip_path_name} ({file_size/1024:.1f} KB)")
                        
                        # Handle large files (>100MB) with streaming to reduce memory usage
                        if file_size > 100 * 1024 * 1024:  # 100MB threshold
                            try:
                                with open(file_path, 'rb') as f_in:
                                    with zipf.open(zip_path_name, 'w') as f_out:
                                        chunk_size = 4 * 1024 * 1024  # 4MB chunks
                                        bytes_written = 0
                                        while True:
                                            chunk = f_in.read(chunk_size)
                                            if not chunk:
                                                break
                                            f_out.write(chunk)
                                            bytes_written += len(chunk)
                                        
                                        if bytes_written > 0:
                                            logger.info(f"Successfully added large file {file} ({bytes_written/1024/1024:.1f} MB)")
                            except Exception as e:
                                logger.error(f"Error adding large file {file}: {str(e)}")
                        else:
                            # Use standard method for regular files
                            zipf.write(file_path, zip_path_name)
                        
                        file_count += 1
            
            logger.info(f"Added {file_count} files to ZIP")
            
            # Also add the job processing summary if it exists
            job_summary_path = os.path.join(job_dir, "processing_summary.txt")
            if os.path.exists(job_summary_path):
                # Add at root level for easy access
                zipf.write(job_summary_path, os.path.basename(job_summary_path))
                logger.info("Added job processing summary to ZIP root")
                file_count += 1
        
        # Verify the zip file was created successfully
        if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
            logger.info(f"Successfully created zip file at {zip_path}")
            
            # Use the video name for the download file
            if video_name:
                download_filename = f"{video_name}_current_{timestamp}.zip"
            else:
                # Fallback if no video name was found
                download_filename = f"{job_id}_current_{timestamp}.zip"
            
            return FileResponse(
                path=zip_path,
                filename=download_filename,
                media_type="application/zip",
                # Important: Set these headers to prevent caching issues
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        else:
            # Clean up if zip was created but is empty or invalid
            logger.error(f"Zip file creation failed or resulted in empty file: {zip_path}")
            clean_up_temp_files(temp_files, temp_dir)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create zip file for job {job_id} results"
            )
            
    except Exception as e:
        # Log the error and clean up temporary files
        logger.error(f"Error creating zip file: {str(e)}")
        clean_up_temp_files(temp_files, temp_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating zip file: {str(e)}"
        )
