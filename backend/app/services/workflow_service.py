import os
import datetime
import logging
import traceback
from typing import Dict, Any, List
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.utils.file_path_manager import FileType, get_file_path_manager
from app.models.job_context import JobContext
from app.services.status_service import StatusUpdateService
from app.models.job import Job, JobStatus, JobResult
from app.models.user import User
from app.models.base import Base
from app.services.job_service import JobService
# Import services for processor initialization
from app.services.semantic_service import SemanticService

# Import new modular processor services
from app.services.audio_processor_service import AudioProcessorService
from app.services.video_processor_service import VideoProcessorService
from app.services.transcription_processor_service import TranscriptionProcessorService
from app.services.translation_processor_service import TranslationProcessorService
from app.services.subtitle_processor_service import SubtitleProcessorService
from app.models.translation_job import StepName, StepStatus

logger = logging.getLogger(__name__)

class WorkflowService:
    """
    Service for coordinating the entire video processing workflow
    This acts as a facade over the individual services
    """
    
    # Removed _update_workflow_status - using StatusUpdateService directly instead

    def __init__(self, db: Session):
        # Import ResultType with RT alias at instance level
        from app.models.job_result import ResultType
        
        self.RT = ResultType
        
        self.db = db
        # Get data directory from settings
        from app.core.config import get_settings
        settings = get_settings()
        data_dir = settings.STORAGE_BASE_DIR
        
        # Initialize SQLAlchemy engine
        if hasattr(settings, 'SQLALCHEMY_DATABASE_URI'):
            self.engine = create_engine(
                settings.SQLALCHEMY_DATABASE_URI,
                poolclass=QueuePool,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Ensure all tables are created
            Base.metadata.create_all(bind=self.engine)
        else:
            logger.warning("SQLALCHEMY_DATABASE_URI not found in settings. Database operations may fail.")
            self.engine = None
            self.SessionLocal = None
        
        logger.info(f"Using storage base directory from settings: {data_dir}")
        self.job_service = JobService(db, data_dir)
        self.semantic_service = SemanticService()
        
        # Initialize FilePathManager for centralized file path handling
        self.file_manager = get_file_path_manager()

        # Initialize processor services (already imported at module level)
        self.audio_processor = AudioProcessorService(db)
        self.video_processor = VideoProcessorService(db, self.job_service)
        self.transcription_processor = TranscriptionProcessorService(db)
        self.translation_processor = TranslationProcessorService(db, self.job_service, self.semantic_service)
        self.subtitle_processor = SubtitleProcessorService(db, self.job_service)
        
        logger.info(f"WorkflowService initialized with data directory: {data_dir}")
        
        # Track reference to StatusUpdateService class and db for status updates
        self.status_service = StatusUpdateService
        self.db = db
    
    # The _realign_and_update_chunks method has been removed as it's been replaced by the new subtitle alignment functionality
    
    def process_job(self, job_id: int, force_reprocess: bool = False) -> Job:
        """
        Process a job from start to finish - Pure orchestration workflow
        
        Args:
            job_id: ID of the job to process
            force_reprocess: If True, forces reprocessing even if the job has been processed before
        """
        # Initialize processing logger for workflow tracking
        proc_logger = ProcessingLogger(job_id, db_session=self.db)
        proc_logger.start_stage(ProcessingStage.INITIALIZED, f"Starting video processing workflow for Job #{job_id}")
        
        try:
            # 0. Load user preferences from DB and apply to environment
            self._apply_user_preferences(job_id)

            # 1. Initialize job and context
            job, context = self._initialize_job_processing(job_id, force_reprocess, proc_logger)
            StatusUpdateService.update_workflow_step(self.db, job_id, StepName.UPLOAD, status="completed", progress=100, details="Job Initialized")

            # 2. Video preparation & Audio processing
            #    Check if this is an audio-only upload (audio extracted on the client)
            is_audio_only = (
                job.result_metadata
                and isinstance(job.result_metadata, dict)
                and job.result_metadata.get('upload_mode') == 'audio_only'
            )

            if is_audio_only:
                # Audio-only mode: skip video prep and audio extraction
                whisper_audio = job.result_metadata.get('audio_file_path', '')
                if not whisper_audio or not os.path.exists(whisper_audio):
                    raise FileNotFoundError(f"Audio file not found: {whisper_audio}")
                proc_logger.log_info(f"Audio-only mode: skipping video/audio processing. Using: {whisper_audio}")
                StatusUpdateService.update_step_status(
                    self.db, job_id, StepName.AUDIO_PROCESSING,
                    StepStatus.COMPLETED, 100.0, "Audio uploaded directly (client-side extraction)"
                )
            else:
                # Standard mode: process video → extract audio
                video_path = self.video_processor.prepare_video_input(job, context, proc_logger)
                whisper_audio = self.audio_processor.perform_audio_processing(job, context, video_path, proc_logger)
            # Audio processing step progress is managed internally

            # 3. Transcription processing (includes content understanding & correction)
            #    This now handles: transcription → global scan → scene correction → segmentation → export
            #    Summary, terminology, and global analysis are all produced inside this step.
            transcription_path = self.transcription_processor.process_transcription(
                job, context, whisper_audio, proc_logger
            )
            StatusUpdateService.update_workflow_step(self.db, job_id, StepName.ANALYZING, status="completed", progress=100, details="Content analysis and correction complete")

            # 4. Prepare translation input from processed transcription
            translation_input_path = self.translation_processor.prepare_translation_input(
                job, context, transcription_path, proc_logger
            )

            translation_files = self.translation_processor.perform_translation(
                job, context, translation_input_path, proc_logger
            )

            subtitle_files = self.subtitle_processor.generate_subtitles_for_all_languages(
                job, context, translation_files, proc_logger
            )

            if job.generate_dubbing:
                self._process_dubbing(job, context, proc_logger)

            target_video_path = self.video_processor.create_final_output_video(job, context, subtitle_files, proc_logger)

            # 9. AI QA — verify final subtitles against source
            self._qa_check_subtitles(job, context, proc_logger)

            # 10. File export and cleanup
            self._finalize_job_processing(job_id, context, proc_logger)
            
            # The workflow is now complete. The final status will be set automatically
            # by the update_workflow_step logic when all steps are marked as completed.
            proc_logger.complete_stage(ProcessingStage.COMPLETED, "All processing stages completed successfully")
            proc_logger.log_info(f"🎉 Job {job_id} completed successfully!")
            return job
            
        except Exception as e:
            # Delegate error handling to helper method
            self._handle_job_failure(job_id, str(e), proc_logger)
            raise
        finally:
            # Ensure cleanup happens even if an error occurs
            self._cleanup_intermediate_files(job_id, context, proc_logger)

    def _apply_user_preferences(self, job_id: int):
        """Load user preferences from DB and inject into environment for this job."""
        try:
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            user = self.db.query(User).filter(User.id == job.owner_id).first()
            if not user or not user.processing_preferences:
                return

            prefs = user.processing_preferences
            env_map = {
                'llm_base_url': 'OPENAI_BASE_URL',
                'llm_api_key': 'OPENAI_API_KEY',
                'llm_model': 'TRANSLATION_MODEL',
                'llm_temperature': 'TRANSLATION_TEMPERATURE',
                'llm_max_tokens': 'TRANSLATION_MAX_TOKENS',
                'whisper_api_url': 'WHISPER_API_URL',
                'whisper_model': 'WHISPER_MODEL',
            }

            applied = []
            for pref_key, env_key in env_map.items():
                val = prefs.get(pref_key)
                if val and str(val).strip():
                    os.environ[env_key] = str(val)
                    display = str(val)[:20] + '...' if len(str(val)) > 20 else str(val)
                    applied.append(f"{env_key}={display}")

            if applied:
                logger.info(f"[JOB:{job_id}] Applied user preferences: {', '.join(applied)}")
        except Exception as e:
            logger.warning(f"[JOB:{job_id}] Failed to load user preferences: {e}")

    def _initialize_job_processing(self, job_id: int, force_reprocess: bool, proc_logger: ProcessingLogger):
        """Initialize job and create context - delegate complex logic to processor services"""
        # Get job and validate
        job = self.job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=0)
        
        if not job.owner_id:
            raise ValueError(f"Job {job_id} is missing an owner. Cannot process.")
        
        # Create JobContext
        target_langs = []
        if job.target_languages:
            if isinstance(job.target_languages, str):
                target_langs = [lang.strip() for lang in job.target_languages.split(',')]
            else:
                target_langs = [lang.strip() for lang in job.target_languages]
        
        context = JobContext(
            user_id=job.owner_id,
            job_id=job_id,
            source_language=job.source_language,
            target_languages=target_langs
        )
        
        # Handle reprocessing if needed
        if force_reprocess:
            self._handle_reprocessing(job, context, proc_logger)
        
        proc_logger.complete_stage(ProcessingStage.INITIALIZED, "Job initialization completed")
        return job, context

    def _handle_reprocessing(self, job: Job, context: JobContext, proc_logger: ProcessingLogger):
        """Handle reprocessing logic - delegate to appropriate services"""
        proc_logger.log_info("Force reprocessing enabled - cleaning up previous job data")
        
        # Delegate cleanup to job service
        self.job_service.cleanup_job_for_reprocessing(job.id)
        
        # Update job metadata
        job.result_metadata = job.result_metadata or {}
        job.result_metadata['reprocessing'] = {
            'reprocessed_at': datetime.datetime.utcnow().isoformat()
        }
        self.db.commit()

    def _process_dubbing(self, job: Job, context: JobContext, proc_logger: ProcessingLogger):
        """Process dubbing if enabled - placeholder for future implementation"""
        proc_logger.start_stage(ProcessingStage.DUBBING, "Processing dubbing")
        proc_logger.log_info(f"🚧 Dubbing functionality is currently being implemented for job {job.id}")
        proc_logger.complete_stage(ProcessingStage.DUBBING, "Dubbing feature is coming soon")

    def _qa_check_subtitles(self, job: Job, context: JobContext, proc_logger: ProcessingLogger):
        """
        AI QA pass on final subtitles: check completeness, accuracy, and consistency.
        Reads aligned_chunks.json (source + translation), sends batches to LLM for review,
        fixes any issues found, and rewrites subtitle files.
        """
        import json as _json

        proc_logger.log_info("Starting AI QA check on final subtitles...")

        try:
            aligned_path = self.file_manager.get_file_path(context=context, file_type=FileType.ALIGNED_CHUNKS_JSON)
            if not self.file_manager.exists(aligned_path):
                proc_logger.log_warning("No aligned_chunks.json found, skipping QA")
                return

            data = self.file_manager.read_json(aligned_path)
            segments = data.get('segments', [])
            if not segments:
                return

            target_langs = [k.replace('text_', '') for k in segments[0].keys() if k.startswith('text_') and k != 'text']
            if not target_langs:
                proc_logger.log_warning("No translations found in aligned chunks, skipping QA")
                return

            # Global context for QA
            global_analysis_path = self.file_manager.get_file_path(context=context, file_type=FileType.GLOBAL_ANALYSIS_JSON)
            global_context = ""
            if self.file_manager.exists(global_analysis_path):
                ga = self.file_manager.read_json(global_analysis_path)
                overview = ga.get('global_analysis', {}).get('content_overview', '')
                domain = ga.get('global_analysis', {}).get('domain', '')
                if overview:
                    global_context = f"Content: {overview}\nDomain: {domain}"

            any_fixes = False

            for lang in target_langs:
                text_key = f'text_{lang}'
                proc_logger.log_info(f"QA checking language: {lang}")

                # Sliding window with overlap for context continuity
                # Window: 12 lines to review, 3 lines overlap on each side for context
                REVIEW_SIZE = 12
                OVERLAP = 3
                STEP = REVIEW_SIZE
                total = len(segments)
                batch_num = 0

                for window_start in range(0, total, STEP):
                    batch_num += 1
                    # Context window: overlap before + review lines + overlap after
                    ctx_start = max(0, window_start - OVERLAP)
                    review_end = min(window_start + REVIEW_SIZE, total)
                    ctx_end = min(review_end + OVERLAP, total)

                    # Build context lines (before)
                    before_ctx = ""
                    if ctx_start < window_start:
                        before_lines = []
                        for i in range(ctx_start, window_start):
                            src = segments[i].get('text', '').strip()
                            tgt = segments[i].get(text_key, '').strip()
                            before_lines.append(f"  [{i+1}] {src} → {tgt}")
                        before_ctx = "PREVIOUS CONTEXT (for reference only, do NOT fix these):\n" + '\n'.join(before_lines)

                    # Build review lines
                    review_lines = []
                    for i in range(window_start, review_end):
                        idx = i + 1
                        src = segments[i].get('text', '').strip()
                        tgt = segments[i].get(text_key, '').strip()
                        review_lines.append(f"[{idx}] EN: {src}")
                        review_lines.append(f"[{idx}] {lang.upper()}: {tgt}")
                    qa_text = '\n'.join(review_lines)

                    # Build context lines (after)
                    after_ctx = ""
                    if review_end < ctx_end:
                        after_lines = []
                        for i in range(review_end, ctx_end):
                            src = segments[i].get('text', '').strip()
                            tgt = segments[i].get(text_key, '').strip()
                            after_lines.append(f"  [{i+1}] {src} → {tgt}")
                        after_ctx = "NEXT CONTEXT (for reference only, do NOT fix these):\n" + '\n'.join(after_lines)

                    prompt = f"""You are a professional subtitle QA reviewer.

{f"CONTEXT: {global_context}" if global_context else ""}

{before_ctx}

SUBTITLES TO REVIEW (fix only these):
{qa_text}

{after_ctx}

CHECK EACH LINE:
1. COMPLETENESS: Does the translation cover ALL meaning from the source? Any omissions?
2. ACCURACY: Is the meaning correct? No hallucination or wrong interpretation?
3. TONE: Does it match the speaker's emotion? (casual/angry/funny/sarcastic)
4. COHERENCE: Does the line flow naturally with the lines before and after it?
5. CONTEXT FIT: Given the scene/topic, is the word choice appropriate?

RULES:
- Fix ONE line at a time — do NOT merge or split
- The fix must match the SAME source line
- Do NOT add filler words not in the source
- Keep punctuation count similar to original
- Consider the before/after context for coherence
- Only fix REAL problems

Return ONLY a JSON array of fixes. Empty [] if all acceptable.
[{{"id": 1, "issue": "brief description", "fixed": "corrected translation"}}]
JSON:"""

                    try:
                        resp = self.semantic_service.provider.translate(
                            prompt, 'en', lang,
                            metadata={"type": "content_scan", "max_tokens": 4000}
                        )
                        raw = str(resp.get("translated_text", "[]")).strip()
                        fixes = self.semantic_service._clean_and_parse_json(raw, str(job.id), context="qa_check")

                        if fixes and isinstance(fixes, list) and len(fixes) > 0:
                            proc_logger.log_info(f"QA batch {batch_num}: found {len(fixes)} issues")
                            for fix in fixes:
                                fix_id = fix.get('id')
                                fixed_text = fix.get('fixed', '')
                                issue = fix.get('issue', '')
                                if fix_id and fixed_text and isinstance(fix_id, int):
                                    seg_idx = fix_id - 1
                                    # Only fix lines within the review window
                                    if window_start <= seg_idx < review_end:
                                        old_text = segments[seg_idx].get(text_key, '')
                                        segments[seg_idx][text_key] = fixed_text
                                        proc_logger.log_info(f"  fix [{fix_id}] ({issue}): \"{old_text[:30]}\" → \"{fixed_text[:30]}\"")
                                        any_fixes = True
                        else:
                            proc_logger.log_info(f"QA batch {batch_num}: all OK")

                    except Exception as e:
                        proc_logger.log_warning(f"QA batch {batch_num} error: {e}")
                        continue

            if any_fixes:
                # Save updated aligned chunks
                data['segments'] = segments
                self.file_manager.write_json(aligned_path, data)
                proc_logger.log_info(f"QA applied {sum(1 for _ in [1])} fixes. Rewriting subtitle files...")

                # Rewrite SRT/VTT/JSON files directly from fixed aligned chunks
                import re as _qa_re
                for lang in target_langs:
                    text_key = f'text_{lang}'
                    srt_lines = []
                    json_subs = []
                    sub_num = 0

                    for seg in segments:
                        text = str(seg.get(text_key, '')).strip()
                        if not text:
                            continue
                        start = float(seg.get('start', 0))
                        end = float(seg.get('end', 0))

                        # Split by punctuation (same logic as subtitle_processor)
                        parts = _qa_re.split(r'(?<=[。！？，、；.!?,;:])\s*', text)
                        parts = [p.strip() for p in parts if p.strip()]
                        if len(parts) <= 1:
                            parts = [(start, end, text)]
                        else:
                            # Use source word timestamps when available
                            src_text = str(seg.get('text', '')).strip()
                            seg_words = seg.get('words', [])
                            src_parts = _qa_re.split(r'(?<=[.!?,;:])\s*', src_text)
                            src_parts = [p.strip() for p in src_parts if p.strip()]
                            if len(src_parts) == len(parts) and seg_words:
                                result = []
                                widx = 0
                                for si, (sp, tp) in enumerate(zip(src_parts, parts)):
                                    wc = len(sp.split())
                                    ws = seg_words[widx].get('start', start) if widx < len(seg_words) else start
                                    widx += wc
                                    we = seg_words[widx-1].get('end', end) if widx-1 < len(seg_words) else end
                                    if si == len(parts)-1: we = end
                                    result.append((ws, we, tp))
                                parts = result
                            else:
                                dur = (end - start) / len(parts)
                                parts = [(start + i*dur, start + (i+1)*dur if i < len(parts)-1 else end, p) for i, p in enumerate(parts)]

                        for s, e, t in parts:
                            t = t.rstrip('.,;:!?…。，；：！？、')
                            if not t: continue
                            sub_num += 1
                            # SRT
                            def fmt(sec):
                                h=int(sec//3600); m=int((sec%3600)//60); s_=int(sec%60); ms=int((sec%1)*1000)
                                return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"
                            srt_lines.extend([str(sub_num), f"{fmt(s)} --> {fmt(e)}", t, ""])
                            json_subs.append({"id": str(sub_num), "text": t, "startTime": s, "endTime": e})

                    # Write files
                    job_dir = self.file_manager._get_job_dir(context.user_id, context.job_id)
                    srt_path = os.path.join(job_dir, "subtitles", f"{lang}.srt")
                    vtt_path = os.path.join(job_dir, "subtitles_vtt", f"{lang}.vtt")
                    json_path = os.path.join(job_dir, "subtitles_json", f"subtitle_{lang}.json")

                    os.makedirs(os.path.dirname(srt_path), exist_ok=True)
                    os.makedirs(os.path.dirname(vtt_path), exist_ok=True)
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)

                    with open(srt_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(srt_lines))
                    with open(vtt_path, 'w', encoding='utf-8') as f:
                        vtt = "WEBVTT\n\n" + '\n'.join(srt_lines).replace(',', '.')
                        f.write(vtt)
                    import json as _json_mod
                    with open(json_path, 'w', encoding='utf-8') as f:
                        _json_mod.dump(json_subs, f, ensure_ascii=False, indent=2)

                    proc_logger.log_info(f"QA: rewrote {sub_num} subtitles for {lang}")
            else:
                proc_logger.log_info("QA check passed — no issues found")

        except Exception as e:
            proc_logger.log_warning(f"QA check failed (non-critical): {e}")

    def _finalize_job_processing(self, job_id: int, context: JobContext, proc_logger: ProcessingLogger):
        """Finalize job processing - file export and cleanup"""
        proc_logger.start_stage(ProcessingStage.FILE_EXPORT, "Organizing and exporting result files")
        
        # Get result files
        result_files = self.job_service.get_job_results(job_id)
        proc_logger.log_info(f"Generated {len(result_files)} output files")
        
        # Sync all result files to remote storage (R2/S3)
        from app.core.config import get_settings
        settings = get_settings()
        
        if settings.STORAGE_BACKEND.lower() == 's3':
            sync_success_count = 0
            sync_failed_count = 0
            
            proc_logger.log_info("Starting sync of result files to remote storage...")
            
            for result_file in result_files:
                try:
                    # Sync each result file to remote storage
                    if self.file_manager.sync_to_remote(result_file.file_path):
                        sync_success_count += 1
                        proc_logger.log_info(f"Successfully synced to R2: {result_file.file_path}")
                    else:
                        sync_failed_count += 1
                        proc_logger.log_warning(f"Failed to sync to R2: {result_file.file_path}")
                except Exception as e:
                    sync_failed_count += 1
                    proc_logger.log_error(f"Error syncing {result_file.file_path} to R2: {str(e)}")
            
            proc_logger.log_info(f"Sync completed: {sync_success_count} successful, {sync_failed_count} failed")
            
            # Also sync the source video if it exists
            try:
                job = self.job_service.get_job_by_id(job_id)
                if job and hasattr(job, 'source_video_url') and job.source_video_url:
                    if self.file_manager.sync_to_remote(job.source_video_url):
                        proc_logger.log_info(f"Successfully synced source video to R2: {job.source_video_url}")
                    else:
                        proc_logger.log_warning(f"Failed to sync source video to R2: {job.source_video_url}")
            except Exception as e:
                proc_logger.log_error(f"Error syncing source video to R2: {str(e)}")
        
        proc_logger.complete_stage(ProcessingStage.FILE_EXPORT, f"Generated {len(result_files)} output files and synced to remote storage")
        
        # Final cleanup
        proc_logger.start_stage(ProcessingStage.CLEANUP, "Performing final cleanup")
        proc_logger.complete_stage(ProcessingStage.CLEANUP, "Cleanup completed successfully")

    def _cleanup_intermediate_files(self, job_id: int, context: JobContext, proc_logger: ProcessingLogger):
        """Clean up intermediate files after job processing"""
        try:
            proc_logger.log_info(f"Starting cleanup of intermediate files for job {job_id}")
            
            # Get job directory
            job_dir = self.file_manager.get_directory_path(context, FileType.JOB_DIRECTORY)
            
            # List of intermediate file patterns to clean up
            intermediate_patterns = [
                "working_video/*",  # Temporary video processing files
                "temp/*",           # General temporary files
                "*.tmp",            # Temporary files with .tmp extension
            ]
            
            cleanup_count = 0
            for pattern in intermediate_patterns:
                try:
                    import glob
                    pattern_path = os.path.join(job_dir, pattern)
                    matching_files = glob.glob(pattern_path, recursive=True)
                    
                    for file_path in matching_files:
                        if os.path.exists(file_path):
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                cleanup_count += 1
                            elif os.path.isdir(file_path) and not os.listdir(file_path):
                                # Remove empty directories
                                os.rmdir(file_path)
                                cleanup_count += 1
                                
                except Exception as pattern_error:
                    proc_logger.log_warning(f"Error cleaning pattern {pattern}: {str(pattern_error)}")
            
            proc_logger.log_info(f"Cleanup completed: removed {cleanup_count} intermediate files")
            
        except Exception as e:
            proc_logger.log_warning(f"Error during cleanup: {str(e)}")
            # Don't raise exception - cleanup failure shouldn't fail the job

    def _handle_job_failure(self, job_id: int, error_message: str, proc_logger: ProcessingLogger):
        """Handle job failure - centralized error handling"""
        proc_logger.log_error(f"Error processing job {job_id}: {error_message}")
        
        # Update job status to failed
        try:
            StatusUpdateService.update_job_status(
                db=self.db,
                job_id=job_id,
                status=JobStatus.FAILED,
                progress=0.0,
                status_message=error_message
            )
            proc_logger.fail_stage(ProcessingStage.FAILED, error_message)
        except Exception as status_error:
            proc_logger.log_error(f"Additional error updating job status: {str(status_error)}")
        
        proc_logger.log_error(f"Stack trace: {traceback.format_exc()}")
