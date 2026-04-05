import os
import json
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models.job import Job, JobResult
from app.models.job_context import JobContext
from app.models.job import ResultType as RT # Alias for convenience
from app.models.translation_job import StepName, StepStatus
from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.services.status_service import StatusUpdateService
from app.utils.file_path_manager import FileType, get_file_path_manager

logger = logging.getLogger(__name__)


class SubtitleProcessorService:
    """
    Service for handling subtitle generation and processing operations in the workflow.
    
    This service is responsible for:
    - Generating subtitles with timeline alignment
    - Processing subtitle files for multiple languages
    - Creating SRT and VTT subtitle formats
    - Managing subtitle file paths and results
    - Handling subtitle alignment and repair
    """
    
    def __init__(self, db: Session, job_service):
        self.db = db
        self.job_service = job_service
        self.file_manager = get_file_path_manager()
    
    def _get_file_size_safe(self, file_path: str) -> int:
        """Safely get file size using file manager with fallback."""
        try:
            return self.file_manager.get_file_size(file_path)
        except Exception as e:
            logger.warning(f"Could not get file size for {file_path}: {e}")
            return 0

    def generate_subtitles_for_all_languages(self, job: Job, context: JobContext, 
                                           translation_files: Dict[str, str], 
                                           proc_logger: ProcessingLogger) -> Dict[str, Dict[str, str]]:
        """
        Generate subtitles with timeline alignment for all languages.
        
        Args:
            job: The job being processed
            context: Job context with user and job information
            translation_files: Dictionary mapping language codes to translation file paths
            proc_logger: Processing logger for tracking progress
            
        Returns:
            Dict[str, Dict[str, str]]: Dictionary mapping language codes to subtitle file paths
                                     (each language has 'srt' and 'vtt' keys)
        """
        proc_logger.start_stage(ProcessingStage.SUBTITLE_GENERATION, "Generating subtitles with timeline alignment")
        
        # Update progress - Starting subtitle generation
        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.ALIGNING_SUBTITLES, 
            StepStatus.IN_PROGRESS, 5.0, "Starting subtitle generation"
        )

        # --- PHASE 1: Establish the 'Source of Truth' ---
        proc_logger.log_info("Attempting to load alignment base file 'aligned_chunks.json'.")

        base_segments = []  # List[Dict] with keys: start, end, text, text_{lang}...
        try:
            aligned_chunks_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.ALIGNED_CHUNKS_JSON
            )

            if not self.file_manager.exists(aligned_chunks_path):
                # Fallback: try legacy xlsx
                xlsx_path = self.file_manager.get_file_path(
                    context=context, file_type=FileType.ALIGNED_CHUNKS_XLSX)
                if self.file_manager.exists(xlsx_path):
                    proc_logger.log_info("JSON not found, falling back to legacy aligned_chunks.xlsx")
                    local_path = self.file_manager.get_local_path(xlsx_path)
                    df = pd.read_excel(local_path)
                    base_segments = df.to_dict('records')
                else:
                    raise FileNotFoundError(f"Alignment file not found (tried JSON and xlsx)")
            else:
                data = self.file_manager.read_json(aligned_chunks_path)
                base_segments = data.get('segments', [])

            if not base_segments:
                raise ValueError("Alignment file contains no segments")

            proc_logger.log_info(f"Successfully loaded alignment base with {len(base_segments)} segments.")

            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.ALIGNING_SUBTITLES,
                StepStatus.IN_PROGRESS, 15.0, f"Loaded {len(base_segments)} aligned segments"
            )

            # Validate required keys
            required_keys = ['start', 'end', 'text']
            first_seg = base_segments[0]
            missing_keys = [k for k in required_keys if k not in first_seg]
            if missing_keys:
                raise ValueError(f"Alignment segments missing required keys: {missing_keys}")

            proc_logger.log_info("Alignment base validated successfully. Contains required keys: start, end, text.")

        except (FileNotFoundError, ValueError) as e:
            error_msg = f"Critical error: Could not load or validate the alignment file. Reason: {e}"
            proc_logger.log_error(error_msg)
            proc_logger.fail_stage(ProcessingStage.SUBTITLE_GENERATION, error_msg)
            raise RuntimeError(error_msg) from e

        # --- End of PHASE 1 ---

        # --- PHASE 2 & 3: Generate subtitles per language ---
        proc_logger.log_info("Starting subtitle generation for all languages.")

        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.ALIGNING_SUBTITLES,
            StepStatus.IN_PROGRESS, 25.0, "Generating subtitles for all languages"
        )

        target_langs = job.target_languages if isinstance(job.target_languages, list) else [lang.strip() for lang in job.target_languages.split(',') if lang.strip()] if job.target_languages else []
        all_languages = ['src'] + target_langs

        subtitle_files = {}
        has_subtitle_errors = False
        total_languages = len(all_languages)

        for lang_index, lang in enumerate(all_languages):
            proc_logger.log_info(f"Processing language: {lang}")

            current_progress = 30.0 + (lang_index / total_languages) * 50.0
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.ALIGNING_SUBTITLES,
                StepStatus.IN_PROGRESS, current_progress, f"Processing language: {lang}"
            )

            # Determine which text key to use for this language
            if lang == 'src':
                text_key = 'text'
            else:
                text_key = f'text_{lang}'
                # Verify translation data exists
                if text_key not in base_segments[0]:
                    proc_logger.log_error(f"Translation key '{text_key}' not found in alignment data for '{lang}'")
                    has_subtitle_errors = True
                    continue

                valid_count = sum(1 for seg in base_segments if seg.get(text_key, '').strip())
                if not valid_count:
                    proc_logger.log_warning(f"No valid translations for '{lang}'. Skipping.")
                    has_subtitle_errors = True
                    continue
                proc_logger.log_info(f"Found {valid_count} valid translations for '{lang}'")

            try:
                # ── Generate SRT ──
                srt_content = self._generate_srt_from_segments(base_segments, text_key, proc_logger)

                if not srt_content:
                    raise ValueError("Generated empty SRT content")

                srt_file_path = self.file_manager.get_file_path(
                    context=context, file_type=FileType.SUBTITLE_SRT, language=lang)
                self.file_manager.write_text(srt_file_path, srt_content)
                proc_logger.log_info(f"SRT saved for {lang}: {srt_file_path}")

                from app.models.job import JobResult
                from app.models.job import ResultType as RT
                self.db.add(JobResult(
                    job_id=job.id, result_type=RT.SUBTITLE_SRT, language=lang,
                    file_path=srt_file_path, created_at=datetime.utcnow(),
                    metadata_={
                        "file_name": os.path.basename(srt_file_path),
                        "file_size": self._get_file_size_safe(srt_file_path),
                        "mime_type": "text/plain",
                        "source_language": job.source_language,
                        "is_source": lang == 'src',
                        "aligned_from": "aligned_chunks.json"
                    }
                ))
                self.file_manager.auto_sync_file_to_remote(srt_file_path, proc_logger.log_info)

                # ── Generate VTT ──
                import re as _re
                vtt_body = _re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_content)
                vtt_content = "WEBVTT\n\n" + vtt_body

                vtt_file_path = self.file_manager.get_file_path(
                    context=context, file_type=FileType.SUBTITLE_VTT, language=lang)
                self.file_manager.write_text(vtt_file_path, vtt_content)
                proc_logger.log_info(f"VTT saved for {lang}: {vtt_file_path}")

                self.db.add(JobResult(
                    job_id=job.id,
                    result_type=RT.TRANSLATED_SUBTITLE_VTT if lang != job.source_language else RT.SUBTITLE_VTT,
                    language=lang, file_path=vtt_file_path, created_at=datetime.utcnow(),
                    metadata_={
                        "file_name": os.path.basename(vtt_file_path),
                        "file_size": self._get_file_size_safe(vtt_file_path),
                        "mime_type": "text/vtt",
                        "source_language": job.source_language,
                        "is_source": lang == 'src',
                        "aligned_from": "aligned_chunks.json"
                    }
                ))
                self.file_manager.auto_sync_file_to_remote(vtt_file_path, proc_logger.log_info)

                # ── Generate JSON for subtitle editor (with long subtitle splitting) ──
                json_subtitles = []
                sub_id = 0
                for seg in base_segments:
                    start_time = float(seg.get('start', 0.0))
                    end_time = float(seg.get('end', start_time + 2.0))
                    if end_time <= start_time:
                        end_time = start_time + 2.0
                    text_val = str(seg.get(text_key, '')).strip()
                    if not text_val:
                        continue

                    source_text = str(seg.get('text', '')).strip()
                    seg_words = seg.get('words', [])
                    parts = self._split_by_sentence_punct(text_val, start_time, end_time, source_text, seg_words)

                    for s, e, t in parts:
                        t = t.rstrip('.,;:!?…。，；：！？、')
                        if not t:
                            continue
                        sub_id += 1
                        json_subtitles.append({
                            "id": str(sub_id),
                            "text": t,
                            "startTime": s,
                            "endTime": e,
                        })

                json_file_path = self.file_manager.get_file_path(context, FileType.SUBTITLE_LANG_JSON, language=lang)
                self.file_manager.write_json(json_file_path, json_subtitles)
                proc_logger.log_info(f"JSON saved for {lang}: {json_file_path}")

                subtitle_files[lang] = {
                    'srt': srt_file_path,
                    'vtt': vtt_file_path,
                    'json': json_file_path,
                }

            except Exception as e:
                proc_logger.log_error(f"Failed during subtitle generation for '{lang}': {e}")
                has_subtitle_errors = True
                continue
            # --- End of per-language processing ---

        # Commit all job results
        self.db.commit()

        # --- Final Stage Completion ---
        if has_subtitle_errors:
            proc_logger.complete_stage(
                ProcessingStage.SUBTITLE_GENERATION, 
                "Subtitle generation completed with some errors. Please check logs."
            )
        else:
            proc_logger.complete_stage(
                ProcessingStage.SUBTITLE_GENERATION, 
                "Subtitle generation completed successfully for all languages."
            )
        
        # Update workflow status after subtitle generation
        try:
            # Final progress updates with gradual completion
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.ALIGNING_SUBTITLES, 
                StepStatus.IN_PROGRESS, 90.0, "Finalizing subtitle files"
            )
            
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.ALIGNING_SUBTITLES, 
                StepStatus.IN_PROGRESS, 95.0, "Validating subtitle output"
            )
            
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.ALIGNING_SUBTITLES, 
                StepStatus.COMPLETED, 100.0, "Subtitle generation and alignment complete"
            )
        except Exception as e_status:
            proc_logger.log_error(f"Error updating job status after subtitle generation: {str(e_status)}")

        return subtitle_files

    # Maximum subtitle duration before splitting (seconds)
    MAX_SUBTITLE_DURATION = 5.0
    # Chinese reading speed (chars/sec) for duration estimation
    CJK_CHARS_PER_SEC = 5.0
    # Latin reading speed (words/sec)
    LATIN_WORDS_PER_SEC = 3.0

    def _generate_srt_from_segments(self, segments: List[Dict], text_key: str,
                                    proc_logger: ProcessingLogger) -> str:
        """
        Generate SRT content from aligned segment list.
        Automatically splits long subtitles into shorter display units.
        """
        srt_lines = []
        subtitle_num = 0

        import re as _re_srt
        for seg in segments:
            text_content = str(seg.get(text_key, '')).strip()
            if not text_content:
                continue

            start = float(seg.get('start', 0.0))
            end = float(seg.get('end', 0.0))

            # Split by sentence-ending punctuation in the translated text
            # Use Whisper word timestamps for precise time boundaries
            source_text = str(seg.get('text', '')).strip()
            seg_words = seg.get('words', [])
            sub_parts = self._split_by_sentence_punct(text_content, start, end, source_text, seg_words)

            for s, e, text in sub_parts:
                # Strip trailing punctuation from each subtitle
                text = text.rstrip('.,;:!?…。，；：！？、')
                if not text:
                    continue
                subtitle_num += 1
                srt_lines.extend([
                    str(subtitle_num),
                    f"{self._format_srt_time(s)} --> {self._format_srt_time(e)}",
                    text,
                    "",
                ])

        return "\n".join(srt_lines)

    def _split_by_sentence_punct(self, text: str, start: float, end: float,
                                source_text: str = '',
                                words: list = None) -> list:
        """
        Split translated text by punctuation.
        Time is determined by Whisper word timestamps — NOT by character ratio.

        When source text and word timestamps are available:
        1. Split source at same punctuation points
        2. Count words per source part
        3. Map word timestamps to find exact split time
        """
        import re
        # Split translated text at punctuation boundaries
        parts = re.split(r'(?<=[。！？，、；.!?,;:])\s*', text)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            duration = end - start
            if duration > self.MAX_SUBTITLE_DURATION:
                return self._split_long_subtitle(text, start, end)
            return [(start, end, text)]

        # Strategy 1: Use word timestamps for precise split
        if words and source_text:
            src_parts = re.split(r'(?<=[.!?,;:])\s*', source_text)
            src_parts = [p.strip() for p in src_parts if p.strip()]

            if len(src_parts) == len(parts):
                # Count words per source part to find split word index
                result = []
                word_idx = 0
                for i, (src_part, tgt_part) in enumerate(zip(src_parts, parts)):
                    src_word_count = len(src_part.split())
                    part_start_idx = word_idx
                    word_idx += src_word_count

                    # Get time from word timestamps
                    if part_start_idx < len(words):
                        t_start = words[part_start_idx].get('start', start)
                    else:
                        t_start = start

                    if word_idx - 1 < len(words):
                        t_end = words[word_idx - 1].get('end', end)
                    else:
                        t_end = end

                    # Last part always ends at segment end
                    if i == len(parts) - 1:
                        t_end = end

                    result.append((t_start, t_end, tgt_part))
                return result

        # Strategy 2: Use source word count ratio (no word timestamps)
        if source_text:
            src_parts = re.split(r'(?<=[.!?,;:])\s*', source_text)
            src_parts = [p.strip() for p in src_parts if p.strip()]

            if len(src_parts) == len(parts):
                total_words = sum(len(p.split()) for p in src_parts)
                if total_words > 0:
                    result = []
                    t = start
                    duration = end - start
                    for i, (src_part, tgt_part) in enumerate(zip(src_parts, parts)):
                        ratio = len(src_part.split()) / total_words
                        part_end = t + duration * ratio if i < len(parts) - 1 else end
                        result.append((t, part_end, tgt_part))
                        t = part_end
                    return result

        # Source and target split counts don't match — do NOT split.
        # Keep the original timing from Whisper intact.
        # Splitting with estimated time would cause misalignment.
        return [(start, end, text)]

    def _split_long_subtitle(self, text: str, start: float, end: float) -> list:
        """
        Split a long subtitle into shorter parts, proportionally by text length.
        Tries to split at punctuation (，。、；,.;) or spaces.
        """
        duration = end - start
        total_len = len(text)
        if total_len == 0:
            return [(start, end, text)]

        # Determine ideal number of parts
        ideal_parts = max(2, int(duration / self.MAX_SUBTITLE_DURATION + 0.5))

        # Find split points at punctuation or spaces
        split_chars = set('，。、；,.;:： ')
        target_chunk_len = total_len / ideal_parts
        parts = []
        current_start_idx = 0

        for p in range(ideal_parts - 1):
            target_idx = int((p + 1) * target_chunk_len)
            # Search nearby for a good split point
            best_idx = target_idx
            for offset in range(0, min(15, total_len - target_idx)):
                if target_idx + offset < total_len and text[target_idx + offset] in split_chars:
                    best_idx = target_idx + offset + 1
                    break
                if target_idx - offset > current_start_idx and text[target_idx - offset] in split_chars:
                    best_idx = target_idx - offset + 1
                    break

            chunk = text[current_start_idx:best_idx].strip()
            if chunk:
                parts.append(chunk)
            current_start_idx = best_idx

        # Last part
        last = text[current_start_idx:].strip()
        if last:
            parts.append(last)

        if not parts:
            return [(start, end, text)]

        # Distribute time proportionally
        total_chars = sum(len(p) for p in parts)
        result = []
        t = start
        for i, part in enumerate(parts):
            ratio = len(part) / total_chars if total_chars > 0 else 1.0 / len(parts)
            part_duration = duration * ratio
            part_end = t + part_duration if i < len(parts) - 1 else end
            result.append((t, part_end, part))
            t = part_end

        return result

    def _format_srt_time(self, seconds: float) -> str:
        """
        Format time in seconds to SRT time format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            str: Formatted time string
        """
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)
            
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
        except (ValueError, TypeError):
            # Fallback for invalid time values
            return "00:00:00,000"

