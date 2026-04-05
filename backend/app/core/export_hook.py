
import os
import logging
import shutil
from pathlib import Path

from app.utils.file_path_manager import get_file_path_manager, FileType

logger = logging.getLogger(__name__)

def ensure_all_results_included(job_id, job_dir):
    """
    Ensures all important results are included in the final output.
    Uses FilePathManager to locate and copy files to the output directory.
    This function is called at the end of job processing.
    """
    try:
        # Initialize FilePathManager with the same base directory
        base_dir = os.path.dirname(os.path.dirname(job_dir))  # Go up 2 levels from job_dir
        file_manager = get_file_path_manager(base_dir)
        
        # Check if output directory exists
        output_dir = os.path.join(job_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Try to load file registry for this job
        registry_loaded = False
        try:
            registry_path = file_manager.get_registry_path(job_id)
            if os.path.exists(registry_path):
                file_manager.load_registry(job_id)
                registry_loaded = True
                logger.info(f"Loaded file registry from {registry_path}")
        except Exception as e:
            logger.warning(f"Could not load registry, will use fallback methods: {str(e)}")
        
        # 1. Copy subtitle files to output
        for lang in file_manager.get_available_languages(job_id, FileType.SUBTITLE_FILE):
            try:
                subtitle_path = file_manager.get_file_path(job_id, FileType.SUBTITLE_FILE, lang)
                if subtitle_path and os.path.exists(subtitle_path):
                    dest = os.path.join(output_dir, os.path.basename(subtitle_path))
                    if not os.path.exists(dest):
                        shutil.copy(subtitle_path, dest)
                        logger.info(f"Copied subtitle file for {lang} to output directory")
            except Exception as e:
                logger.warning(f"Error copying subtitle file for language {lang}: {str(e)}")
        
        # Fallback: search for subtitle files if registry is not available
        if not registry_loaded:
            subtitle_dir = os.path.join(job_dir, "subtitles")
            if os.path.exists(subtitle_dir):
                for srt_file in Path(subtitle_dir).glob("*.srt"):
                    dest = os.path.join(output_dir, srt_file.name)
                    if not os.path.exists(dest):
                        shutil.copy(str(srt_file), dest)
                        logger.info(f"Copied {srt_file.name} to output directory (fallback method)")
        
        # 2. Copy subtitled videos to output
        for lang in file_manager.get_available_languages(job_id, FileType.SUBTITLED_VIDEO):
            try:
                video_path = file_manager.get_file_path(job_id, FileType.SUBTITLED_VIDEO, lang)
                if video_path and os.path.exists(video_path):
                    dest = os.path.join(output_dir, f"video_with_subtitles_{lang}.mp4")
                    if not os.path.exists(dest):
                        shutil.copy(video_path, dest)
                        logger.info(f"Copied subtitled video for {lang} to output directory")
            except Exception as e:
                logger.warning(f"Error copying subtitled video for language {lang}: {str(e)}")
        
        # Fallback: check for traditional subtitled video path
        if not registry_loaded:
            subtitled_video = os.path.join(job_dir, "output_sub.mp4")
            if os.path.exists(subtitled_video):
                dest = os.path.join(output_dir, "video_with_subtitles.mp4")
                if not os.path.exists(dest):
                    shutil.copy(subtitled_video, dest)
                    logger.info(f"Copied subtitled video to {dest} (fallback method)")
        
        # 3. Copy translation files to output
        for lang in file_manager.get_available_languages(job_id, FileType.TRANSLATION):
            try:
                translation_path = file_manager.get_file_path(job_id, FileType.TRANSLATION, lang)
                if translation_path and os.path.exists(translation_path):
                    dest = os.path.join(output_dir, os.path.basename(translation_path))
                    if not os.path.exists(dest):
                        shutil.copy(translation_path, dest)
                        logger.info(f"Copied translation file for {lang} to output directory")
            except Exception as e:
                logger.warning(f"Error copying translation file for language {lang}: {str(e)}")
                
        # Fallback: search for translation files
        if not registry_loaded:
            log_dir = os.path.join(job_dir, "log")
            if os.path.exists(log_dir):
                for trans_file in Path(log_dir).glob("*translated*.xlsx"):
                    dest = os.path.join(output_dir, trans_file.name)
                    if not os.path.exists(dest):
                        shutil.copy(str(trans_file), dest)
                        logger.info(f"Copied {trans_file.name} to output directory (fallback method)")
        
        # 4. Copy transcript files
        for lang in file_manager.get_available_languages(job_id, FileType.TRANSCRIPT):
            try:
                transcript_path = file_manager.get_file_path(job_id, FileType.TRANSCRIPT, lang)
                if transcript_path and os.path.exists(transcript_path):
                    dest = os.path.join(output_dir, os.path.basename(transcript_path))
                    if not os.path.exists(dest):
                        shutil.copy(transcript_path, dest)
                        logger.info(f"Copied transcript file for {lang} to output directory")
            except Exception as e:
                logger.warning(f"Error copying transcript file for language {lang}: {str(e)}")
                
        logger.info(f"Ensured all results are included for job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Error ensuring results are included: {str(e)}")
        return False
