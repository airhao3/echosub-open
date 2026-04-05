import os
import re
import json
import logging
import traceback
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.job import Job
from app.models.job_context import JobContext
from app.models.translation_job import StepName, StepStatus
from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.services.status_service import StatusUpdateService
from app.services.transcription.segmentation import TranscriptionSegmenter
from app.services.transcription.text_tagging import TextTaggingService
from app.services.semantic_service import SemanticService
from app.utils.file_path_manager import FileType, get_file_path_manager

logger = logging.getLogger(__name__)


class TranscriptionProcessorService:
    """
    Service for handling transcription processing operations in the workflow.

    This service orchestrates a 2-phase pipeline:

    Phase 1 — Transcription:
      - Call Whisper API to produce raw transcript

    Phase 2 — Content Understanding & Correction (post-transcription):
      Step 2.1: Global Scan + Scene Division (1 LLM call)
      Step 2.2: Scene-by-Scene Correction (N LLM calls, sequential, chained context)
      Step 2.3: Segmentation + Tagging (no LLM, reuses existing services)
      Step 2.4: Export (package results for translation step)
    """

    def __init__(self, db: Session):
        self.db = db
        self.file_manager = get_file_path_manager()
        self.semantic_service = SemanticService()

    def process_transcription(self, job: Job, context: JobContext, whisper_audio: str, proc_logger: ProcessingLogger) -> str:
        """
        Main transcription processing method that orchestrates all transcription steps.

        Args:
            job: The job being processed
            context: Job context with user and job information
            whisper_audio: Path to the processed audio file
            proc_logger: Processing logger for tracking progress

        Returns:
            str: Path to the final processed transcription file
        """
        try:
            # ============================================
            # Phase 1: Transcription (Whisper API)
            # ============================================
            proc_logger.start_stage(ProcessingStage.TRANSCRIPTION, "Starting audio transcription")

            from app.services.transcription_service import TranscriptionService
            transcription_service = TranscriptionService()

            proc_logger.log_info(f"Transcribing audio file: {whisper_audio}")

            transcription_path = transcription_service.transcribe(
                job_context_or_dir=context,
                audio_path=whisper_audio,
                progress_callback=lambda progress, message="": proc_logger.log_info(f"Transcription progress: {progress}% - {message}")
            )

            proc_logger.log_info(f"Transcription completed. Output: {transcription_path}")
            proc_logger.complete_stage(ProcessingStage.TRANSCRIPTION, "Audio transcription completed")

            # ============================================
            # Phase 1.5: Sentence Splitting (word-level)
            # Split Whisper output into proper sentences using
            # word timestamps, punctuation, and linguistic cues
            # Adjust params based on video orientation
            # ============================================
            import json as _json
            json_content = self.file_manager.read_text(transcription_path)
            whisper_segments = _json.loads(json_content)

            # Detect video orientation and adjust splitting params
            self._adapt_params_to_video(job, context, proc_logger)

            sentences = self._split_into_sentences(whisper_segments, proc_logger)
            proc_logger.log_info(f"Sentence splitting: {len(sentences)} sentences from Whisper output")

            # Save sentence-split results (JSON with word timestamps + tagged text)
            job_dir = self.file_manager._get_job_dir(context.user_id, context.job_id)
            seg_dir = os.path.join(job_dir, "segmented_transcript")
            os.makedirs(seg_dir, exist_ok=True)

            seg_json_path = os.path.join(seg_dir, "transcript_segmented.json")
            self.file_manager.write_json(seg_json_path, {
                "segments": sentences,
                "metadata": {"sentence_split": {"total_sentences": len(sentences)}}
            })

            # Build tagged text: each sentence = one [N] line
            tagged_lines = [f"[{i+1}] {s['text']}" for i, s in enumerate(sentences)]
            tagged_text = '\n'.join(tagged_lines)

            seg_txt_path = os.path.join(seg_dir, "transcript_segmented.txt")
            with open(seg_txt_path, 'w', encoding='utf-8') as f:
                f.write(tagged_text + '\n')

            proc_logger.log_info(f"Sentences saved: {seg_json_path} ({len(sentences)} lines)")

            # ============================================
            # Phase 2: Content Understanding & Correction
            # ============================================
            proc_logger.start_stage(ProcessingStage.CONTENT_UNDERSTANDING, "Starting content understanding & correction")

            # Step 2.1: Global Scan + Scene Division (on sentence-split tagged text)
            proc_logger.log_info("Step 2.1: Global content scan and scene division")
            scan_result = self.semantic_service.scan_content(
                text=tagged_text,
                source_lang=job.source_language,
                job_id=str(job.id)
            )

            global_analysis = scan_result.get('global_analysis', {})
            scenes = scan_result.get('scenes', [])

            # Safety: split mega-scenes
            MAX_SCENE_LINES = 50
            split_scenes = []
            for scene in scenes:
                s, e = scene.get('start_line', 1), scene.get('end_line', 1)
                if e - s + 1 > MAX_SCENE_LINES:
                    for cs in range(s, e + 1, MAX_SCENE_LINES):
                        ce = min(cs + MAX_SCENE_LINES - 1, e)
                        split_scenes.append({**scene, 'scene_id': f"{scene.get('scene_id',1)}.{(cs-s)//MAX_SCENE_LINES+1}", 'start_line': cs, 'end_line': ce})
                else:
                    split_scenes.append(scene)
            scenes = split_scenes

            proc_logger.log_info(f"Global scan complete: {len(scenes)} scenes, domain={global_analysis.get('domain', 'unknown')}")

            # Save global analysis
            global_analysis_path = self.file_manager.get_file_path(context=context, file_type=FileType.GLOBAL_ANALYSIS_JSON)
            self.file_manager.write_json(global_analysis_path, {"global_analysis": global_analysis, "scenes": scenes, "generated_at": datetime.utcnow().isoformat()})

            # Step 2.2: Scene-by-Scene Correction
            proc_logger.log_info(f"Step 2.2: Scene-by-scene correction ({len(scenes)} scenes)")
            corrected_text, scene_digests = self._correct_all_scenes(
                tagged_text=tagged_text, scenes=scenes, global_analysis=global_analysis,
                source_lang=job.source_language, job_id=str(job.id), proc_logger=proc_logger
            )

            # Save corrected transcript + scene digests
            corrected_path = self.file_manager.get_file_path(context=context, file_type=FileType.CORRECTED_TRANSCRIPT)
            self.file_manager.write_text(corrected_path, corrected_text)

            scene_digests_path = self.file_manager.get_file_path(context=context, file_type=FileType.SCENE_DIGESTS_JSON)
            self.file_manager.write_json(scene_digests_path, {"scene_digests": scene_digests, "total_scenes": len(scene_digests), "generated_at": datetime.utcnow().isoformat()})

            self._register_job_result(job, corrected_path, "transcript_corrected.txt", "text/plain")
            proc_logger.complete_stage(ProcessingStage.CONTENT_UNDERSTANDING, f"Content understanding complete: {len(scenes)} scenes")

            # Step 2.3: Export analysis artifacts
            self._export_analysis_artifacts(job, context, global_analysis, scan_result, proc_logger)

            # Return the sentence-split tagged text as final transcription output
            proc_logger.log_info(f"Transcription processing completed. Final file: {seg_txt_path}")
            return seg_txt_path

        except Exception as e:
            proc_logger.log_error(f"Error in transcription processing: {str(e)}")
            raise

    def _adapt_params_to_video(self, job, context, proc_logger):
        """Detect video orientation and adjust sentence splitting params."""
        try:
            import subprocess
            # Find source video
            job_dir = self.file_manager._get_job_dir(context.user_id, context.job_id)
            source_dir = os.path.join(job_dir, "source")
            video_files = [f for f in os.listdir(source_dir) if f.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))] if os.path.isdir(source_dir) else []

            if not video_files:
                proc_logger.log_info("No video file found, using default params (landscape)")
                return

            video_path = os.path.join(source_dir, video_files[0])
            probe = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'stream=width,height',
                 '-of', 'csv=p=0', video_path],
                capture_output=True, text=True, timeout=10)

            parts = probe.stdout.strip().split(',')
            if len(parts) >= 2:
                width, height = int(parts[0]), int(parts[1])
                ratio = width / height if height > 0 else 1.78

                if ratio < 0.8:
                    # Portrait (TikTok/Reels) — short lines
                    self._TARGET_WORDS = 8
                    self._MAX_WORDS = 12
                    self._MAX_DURATION = 4.0
                    proc_logger.log_info(f"Portrait video ({width}x{height}) → TARGET={self._TARGET_WORDS}, MAX={self._MAX_WORDS}")
                elif ratio < 1.2:
                    # Square — medium lines
                    self._TARGET_WORDS = 10
                    self._MAX_WORDS = 15
                    self._MAX_DURATION = 4.5
                    proc_logger.log_info(f"Square video ({width}x{height}) → TARGET={self._TARGET_WORDS}, MAX={self._MAX_WORDS}")
                else:
                    # Landscape — long lines, higher flush threshold
                    self._TARGET_WORDS = 15
                    self._MAX_WORDS = 22
                    self._MAX_DURATION = 6.0
                    self._SOFT_MIN_WORDS = 8
                    self._MIN_WORDS = 5
                    proc_logger.log_info(f"Landscape video ({width}x{height}) → TARGET={self._TARGET_WORDS}, MAX={self._MAX_WORDS}, MIN_FLUSH=5")
        except Exception as e:
            proc_logger.log_warning(f"Video orientation detection failed: {e}, using defaults")

    # ============================================
    # Phase 1.5: Word-level sentence splitting
    # ============================================

    # Split priority constants
    _SENTENCE_ENDERS = set('.?!')
    _SOFT_PUNCT = set(',;:')
    _SUBORDINATING = {'because', 'since', 'while', 'when', 'where', 'if', 'unless',
                      'until', 'after', 'before', 'although', 'though', 'whereas', 'whenever'}
    _COORDINATING = {'and', 'but', 'or', 'nor', 'so', 'yet', 'for'}
    _RELATIVE = {'that', 'which', 'who', 'whom', 'whose', 'where', 'how', 'what'}

    _TARGET_WORDS = 12      # Ideal words per subtitle (横屏可以长一些)
    _MAX_WORDS = 18         # Hard limit — always split before this
    _MAX_DURATION = 5.0
    _SOFT_MIN_WORDS = 6
    _MIN_WORDS = 3
    _PAUSE_THRESHOLD = 0.4

    def _split_into_sentences(self, whisper_segments: list, proc_logger) -> list:
        """
        Split Whisper output into sentences using word-level timestamps.

        Priority for split points (when sentence exceeds limits):
        1. Sentence-ending punctuation (.?!)
        2. Soft punctuation (,;:)
        3. Subordinating conjunctions (because, when, while...)
        4. Coordinating conjunctions (and, but, or...)
        5. Relative pronouns (that, which, who...)
        6. Speech pauses (>0.2s gap)
        """
        # Flatten all words
        all_words = []
        for seg in whisper_segments:
            for w in seg.get('words', []):
                all_words.append(w)

        if not all_words:
            proc_logger.log_warning("No word-level timestamps found, using raw segments")
            return [{'text': seg.get('text', '').strip(), 'start': seg.get('start', 0),
                      'end': seg.get('end', 0), 'words': seg.get('words', [])}
                     for seg in whisper_segments if seg.get('text', '').strip()]

        sentences = []
        buf = []

        def make_sentence(words):
            text = ' '.join(w.get('word', '').strip() for w in words if w.get('word', '').strip())
            while '  ' in text:
                text = text.replace('  ', ' ')
            # Strip trailing punctuation for clean subtitle display
            text = text.strip().rstrip('.,;:!?…。，；：！？')
            return {
                'text': text.strip(),
                'start': words[0].get('start', 0),
                'end': words[-1].get('end', 0),
                'words': list(words),
            }

        def flush():
            nonlocal buf
            if buf:
                sentences.append(make_sentence(buf))
                buf = []

        def _find_best_split(words):
            """
            Find best split position using linguistic priority.

            Calculates ideal split position based on MAX_WORDS target,
            then searches nearby for the best linguistic break point.
            """
            n = len(words)
            if n < 4:
                return None

            # Calculate ideal position: target subtitle length
            total_dur = words[-1].get('end', 0) - words[0].get('start', 0)
            ideal_by_words = min(self._TARGET_WORDS, n - 2)
            ideal_by_time = int(n * (self._MAX_DURATION / total_dur)) if total_dur > 0 else self._TARGET_WORDS
            ideal = min(ideal_by_words, ideal_by_time)
            ideal = max(3, min(ideal, n - 2))

            # Search the full valid range — let score (type + distance) pick the winner
            search_start = max(2, self._MIN_WORDS)
            search_end = min(n - 2, n - self._MIN_WORDS)

            if search_start >= search_end:
                search_start = max(2, n // 4)
                search_end = min(n - 2, n * 3 // 4)

            best_pos, best_score = None, -1

            for pos in range(search_start, search_end + 1):
                prev_word = words[pos - 1].get('word', '').strip()
                next_word_lower = words[pos].get('word', '').strip().lower() if pos < n else ''
                last_char = prev_word[-1] if prev_word else ''

                # Distance from ideal — mild penalty, linguistic type matters more
                dist_penalty = abs(pos - ideal) * 0.15

                if last_char in self._SENTENCE_ENDERS:
                    score = 100 - dist_penalty
                elif last_char in self._SOFT_PUNCT:
                    score = 80 - dist_penalty
                elif next_word_lower in self._SUBORDINATING:
                    score = 60 - dist_penalty
                elif next_word_lower in self._COORDINATING:
                    score = 50 - dist_penalty
                elif next_word_lower in self._RELATIVE:
                    score = 40 - dist_penalty
                else:
                    gap = words[pos].get('start', 0) - words[pos - 1].get('end', 0) if pos < n else 0
                    if gap > 0.15:
                        score = 30 + gap * 10 - dist_penalty
                    else:
                        continue

                # Penalize bad cut points — but NOT when next word is a conjunction (natural break)
                is_next_conjunction = next_word_lower in self._COORDINATING | self._SUBORDINATING
                if not is_next_conjunction:
                    prev_lower = prev_word.rstrip('.,;:!?').lower()
                    if prev_lower in ('the', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'for',
                                      'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be',
                                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                                      'can', 'could', 'should', 'may', 'might', 'shall', 'not',
                                      'no', 'my', 'your', 'his', 'her', 'its', 'our', 'their'):
                        score -= 20
                    elif prev_lower.endswith('ing'):
                        score -= 15

                if score > best_score:
                    best_score = score
                    best_pos = pos

            return best_pos if best_score > 0 else None

        def _recursive_split(words, depth=0):
            """Recursively split word list until each part is within limits."""
            if not words:
                return []
            n = len(words)
            dur = words[-1].get('end', 0) - words[0].get('start', 0)

            # Within limits → return as single sentence
            if (n < self._MAX_WORDS and dur < self._MAX_DURATION) or n < 4 or depth > 5:
                return [words]

            pos = _find_best_split(words)
            if pos:
                left, right = words[:pos], words[pos:]
                return _recursive_split(left, depth + 1) + _recursive_split(right, depth + 1)
            else:
                # No good split point, force split at midpoint
                mid = n // 2
                return _recursive_split(words[:mid], depth + 1) + _recursive_split(words[mid:], depth + 1)

        def smart_split():
            """Recursively split buf until all parts are within limits."""
            nonlocal buf
            parts = _recursive_split(buf)
            buf = []
            for part in parts:
                if part:
                    sentences.append(make_sentence(part))

        ALL_PUNCT = self._SENTENCE_ENDERS | self._SOFT_PUNCT
        MIN_FLUSH = self._MIN_WORDS  # Use adaptive value based on video orientation

        for i, word in enumerate(all_words):
            wt = word.get('word', '').strip()

            # Pause before this word → flush
            if buf and i > 0:
                gap = word.get('start', 0) - all_words[i - 1].get('end', 0)
                # Long pause (>1s): always flush regardless of buf size
                # Normal pause (>0.4s): flush if buf has enough words
                if gap > 1.0:
                    flush()
                elif gap > self._PAUSE_THRESHOLD and len(buf) >= MIN_FLUSH:
                    flush()

            buf.append(word)

            last_char = wt[-1] if wt else ''
            n = len(buf)
            dur = buf[-1].get('end', 0) - buf[0].get('start', 0)

            # Punctuation: flush only if buf has enough words (elastic)
            if last_char in self._SENTENCE_ENDERS and n >= MIN_FLUSH:
                flush()
            elif last_char in self._SOFT_PUNCT and n >= self._SOFT_MIN_WORDS:
                flush()
            # Over hard limits → smart recursive split
            elif n >= self._MAX_WORDS or dur >= self._MAX_DURATION:
                smart_split()

        flush()

        proc_logger.log_info(f"Word-level split: {len(all_words)} words → {len(sentences)} sentences")
        return sentences

    # ============================================
    # Legacy: Sentence merge (kept for compatibility but no longer called)
    # ============================================

    def _merge_segments_into_sentences(self, job: Job, context: JobContext,
                                       proc_logger: ProcessingLogger) -> str:
        """
        Merge fragmented segments into complete sentences using word timestamps.

        Flow:
        1. Load transcript_segmented.json (segments with word-level timestamps)
        2. Merge adjacent segments that don't end with sentence-ending punctuation
        3. Use first word's start and last word's end for sentence timing
        4. Save merged result as the new segmented transcript
        5. Return path to the merged tagged text file

        This ensures translation receives complete sentences, not fragments.
        """
        import json as _json

        # Segmenter writes to segmented_transcript/ directory directly
        job_dir = self.file_manager._get_job_dir(context.user_id, context.job_id)
        segmented_json_path = os.path.join(job_dir, "segmented_transcript", "transcript_segmented.json")

        if not os.path.exists(segmented_json_path):
            proc_logger.log_warning(f"Segmented JSON not found at {segmented_json_path}, skipping sentence merge")
            return self.file_manager.get_file_path(
                context=context, file_type=FileType.SEGMENTED_TRANSCRIPT)

        data = self.file_manager.read_json(segmented_json_path)
        segments = data.get('segments', [])
        if not segments:
            proc_logger.log_warning("No segments in segmented JSON")
            return self.file_manager.get_file_path(
                context=context, file_type=FileType.SEGMENTED_TRANSCRIPT)

        original_count = len(segments)
        proc_logger.log_info(f"Sentence merge: starting with {original_count} segments")

        # Sentence-ending punctuation
        # Light post-processing on TranscriptionSegmenter output:
        # 1. Merge short fragments that don't end with sentence punctuation
        # 2. Keep segments that are already well-formed
        # TranscriptionSegmenter already did the heavy lifting (semantic splitting + timestamp alignment)

        SENTENCE_ENDERS = {'.', '?', '!'}
        MIN_CHARS = 10          # Merge fragments shorter than this
        MAX_MERGE_DURATION = 5.0  # Don't merge if combined duration exceeds this
        MAX_MERGE_CHARS = 60    # Don't merge if combined text exceeds this

        merged = []
        buf_texts = []
        buf_words = []
        buf_start = None

        def flush():
            nonlocal buf_texts, buf_words, buf_start
            if not buf_texts:
                return
            text = ' '.join(buf_texts)
            while '  ' in text:
                text = text.replace('  ', ' ')
            start = buf_start if buf_start is not None else 0
            end = buf_words[-1].get('end', start) if buf_words else start
            merged.append({
                'text': text.strip(),
                'start': start,
                'end': end,
                'words': list(buf_words),
            })
            buf_texts = []
            buf_words = []
            buf_start = None

        for seg in segments:
            text = seg.get('text', '').strip()
            words = seg.get('words', [])
            if not text:
                continue

            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)

            # If buffer is empty, start new
            if not buf_texts:
                buf_start = seg_start
                buf_texts.append(text)
                buf_words.extend(words)
            else:
                # Check if we should merge this segment into the buffer
                combined_text = ' '.join(buf_texts + [text])
                combined_duration = seg_end - buf_start

                can_merge = (
                    combined_duration <= MAX_MERGE_DURATION and
                    len(combined_text) <= MAX_MERGE_CHARS
                )

                prev_text = buf_texts[-1].rstrip()
                prev_ends_sentence = prev_text and prev_text[-1] in SENTENCE_ENDERS
                prev_is_short = len(' '.join(buf_texts)) < MIN_CHARS

                if can_merge and (prev_is_short or not prev_ends_sentence):
                    # Merge: previous fragment is too short or doesn't end a sentence
                    buf_texts.append(text)
                    buf_words.extend(words)
                else:
                    # Flush previous, start new
                    flush()
                    buf_start = seg_start
                    buf_texts.append(text)
                    buf_words.extend(words)

            # Check if current buffer ends a sentence → flush
            last_char = text.rstrip()[-1] if text.rstrip() else ''
            if last_char in SENTENCE_ENDERS and len(' '.join(buf_texts)) >= MIN_CHARS:
                flush()

        flush()

        proc_logger.log_info(f"Sentence merge: {original_count} segments → {len(merged)} sentences")

        # Save merged segments back to segmented JSON
        data['segments'] = merged
        data['metadata'] = data.get('metadata', {})
        data['metadata']['sentence_merge'] = {
            'original_segments': original_count,
            'merged_sentences': len(merged),
        }
        self.file_manager.write_json(segmented_json_path, data)

        # Save merged text with tags to the same directory
        tagged_lines = [f"[{i+1}] {s['text']}" for i, s in enumerate(merged)]
        segmented_txt_path = os.path.join(
            os.path.dirname(segmented_json_path), "transcript_segmented.txt")
        with open(segmented_txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(tagged_lines) + '\n')

        proc_logger.log_info(f"Sentence merge saved: {segmented_txt_path}")
        return segmented_txt_path

    # ============================================
    # Phase 2 helper methods
    # ============================================

    def _ensure_line_tags(self, text: str) -> str:
        """Ensure each non-empty line has a [N] tag prefix."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        has_tags = any(re.match(r'^\[\d+\]', line) for line in lines[:5])

        if has_tags:
            return '\n'.join(lines)

        tagged = [f"[{i}] {line}" for i, line in enumerate(lines, 1)]
        return '\n'.join(tagged)

    def _correct_all_scenes(
        self,
        tagged_text: str,
        scenes: List[Dict],
        global_analysis: Dict,
        source_lang: str,
        job_id: str,
        proc_logger: ProcessingLogger
    ) -> tuple:
        """
        Iterate through all scenes, correcting each one with chained context.

        Returns:
            Tuple of (corrected_full_text, scene_digests_list)
        """
        # Build a line map: tag_number -> line_text
        lines = [line.strip() for line in tagged_text.split('\n') if line.strip()]
        line_map = {}
        for line in lines:
            match = re.match(r'\[(\d+)\]', line)
            if match:
                line_map[int(match.group(1))] = line

        corrected_lines = {}
        scene_digests = []

        for i, scene in enumerate(scenes):
            scene_id = scene.get('scene_id', i + 1)
            start_line = scene.get('start_line', 1)
            end_line = scene.get('end_line', len(line_map))

            # Extract scene text from line map
            scene_lines = []
            for ln in range(start_line, end_line + 1):
                if ln in line_map:
                    scene_lines.append(line_map[ln])

            scene_text = '\n'.join(scene_lines)

            if not scene_text.strip():
                proc_logger.log_warning(f"Scene {scene_id} is empty (lines {start_line}-{end_line}), skipping correction")
                scene_digests.append({
                    "scene_id": scene_id,
                    "topic": scene.get('topic', ''),
                    "digest": f"Empty scene ({start_line}-{end_line})"
                })
                continue

            proc_logger.log_info(f"Correcting scene {scene_id}/{len(scenes)} (lines {start_line}-{end_line}, {len(scene_lines)} lines)")

            # Call LLM for scene correction
            result = self.semantic_service.correct_scene(
                scene_text=scene_text,
                scene_info=scene,
                global_analysis=global_analysis,
                previous_digests=scene_digests,
                source_lang=source_lang,
                job_id=job_id
            )

            # Parse corrected lines back into the line map
            corrected_text = result.get('corrected_text', scene_text)
            for cline in corrected_text.split('\n'):
                cline = cline.strip()
                if not cline:
                    continue
                match = re.match(r'\[(\d+)\]', cline)
                if match:
                    corrected_lines[int(match.group(1))] = cline

            # Accumulate scene digest for chained context
            scene_digests.append({
                "scene_id": scene_id,
                "topic": scene.get('topic', ''),
                "digest": result.get('scene_digest', '')
            })

            proc_logger.log_info(f"Scene {scene_id} corrected. Digest: {result.get('scene_digest', '')[:80]}...")

        # Merge corrected lines with originals (corrected takes priority)
        all_tags = sorted(set(list(line_map.keys()) + list(corrected_lines.keys())))
        final_lines = []
        for tag in all_tags:
            if tag in corrected_lines:
                final_lines.append(corrected_lines[tag])
            elif tag in line_map:
                final_lines.append(line_map[tag])

        return '\n'.join(final_lines), scene_digests

    def _export_analysis_artifacts(self, job: Job, context: JobContext,
                                    global_analysis: Dict, scan_result: Dict,
                                    proc_logger: ProcessingLogger):
        """
        Step 2.4: Export summary and terminology from global analysis.
        These are derived from scan_content() results — no additional LLM calls needed.
        """
        try:
            # Export summary from global_analysis
            summary_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.SUMMARY_JSON
            )
            summary_data = {
                "summary": global_analysis,
                "status": "success",
                "generated_at": datetime.utcnow().isoformat()
            }
            self.file_manager.write_json(summary_path, summary_data)
            self._register_job_result(job, summary_path, "summary.json", "application/json")
            self.file_manager.auto_sync_file_to_remote(summary_path, proc_logger.log_info)
            proc_logger.log_info(f"Summary exported to: {summary_path}")

            # Export terminology from key_terms
            key_terms = global_analysis.get('key_terms', [])
            terminology_data = {
                "terms": key_terms,
                "domain": global_analysis.get('domain', 'general'),
                "source_language": job.source_language,
                "extracted_at": datetime.utcnow().isoformat()
            }
            terminology_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.TERMINOLOGY_JSON
            )
            self.file_manager.write_json(terminology_path, terminology_data)
            self._register_job_result(job, terminology_path, "terminology.json", "application/json")
            self.file_manager.auto_sync_file_to_remote(terminology_path, proc_logger.log_info)
            proc_logger.log_info(f"Terminology exported to: {terminology_path}")

        except Exception as e:
            proc_logger.log_error(f"Error exporting analysis artifacts: {str(e)}")
            # Non-fatal — don't raise

    def _register_job_result(self, job: Job, file_path: str, filename: str, mime_type: str):
        """Helper to register a file as a JobResult."""
        from app.models.job import JobResult
        from app.models.job import ResultType as RT

        # Determine result type from filename
        type_map = {
            "summary.json": RT.SUMMARY_JSON,
            "terminology.json": RT.TERMINOLOGY_JSON,
        }
        result_type = type_map.get(filename, RT.TRANSCRIPTION_REFINED)

        result = JobResult(
            job_id=job.id,
            result_type=result_type,
            language=job.source_language,
            file_path=file_path,
            metadata_={
                "file_name": filename,
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                "mime_type": mime_type
            }
        )
        self.db.add(result)
        self.db.commit()

    # ============================================
    # Segmentation + Tagging (reused from original)
    # ============================================

    def process_transcription_segmentation(self, job: Job, context: JobContext,
                                         transcription_path: str, proc_logger: ProcessingLogger) -> str:
        """
        Process transcription segmentation and text tagging.

        Args:
            job: The job being processed
            context: Job context with user and job information
            transcription_path: Path to the corrected transcription file
            proc_logger: Processing logger for tracking progress

        Returns:
            str: Path to the processed transcription file
        """
        try:
            # Segmentation
            enable_segmentation = getattr(job, 'enable_segmentation', True)
            if enable_segmentation:
                proc_logger.log_info("Initializing TranscriptionSegmenter...")
                segmenter = TranscriptionSegmenter()

                proc_logger.log_info(f"Calling process_transcription_file with context: {context.job_id}")
                segmentation_results = segmenter.process_transcription_file(
                    context=context,
                    video_path=None,
                    max_length=80,
                    flexibility=0.2
                )

                if segmentation_results and segmentation_results.get('output_txt'):
                    proc_logger.log_info(f"Segmentation completed successfully. Results: {segmentation_results}")
                    transcription_path = segmentation_results.get('output_txt')
                    proc_logger.log_info(f"Updated transcription_path to: {transcription_path}")

                    # Text Tagging
                    enable_text_tagging = getattr(job, 'enable_text_tagging', True)
                    if enable_text_tagging:
                        proc_logger.log_info("Starting text tagging process...")
                        try:
                            text_tagging_service = TextTaggingService()
                            tagging_results = text_tagging_service.process_segmented_transcript(
                                context=context
                            )

                            if tagging_results and tagging_results.get('output_path'):
                                proc_logger.log_info(f"Text tagging completed successfully. Results: {tagging_results}")
                                transcription_path = tagging_results.get('output_path')
                                proc_logger.log_info(f"Updated transcription_path to tagged transcript: {transcription_path}")
                            else:
                                proc_logger.log_warning("Text tagging did not produce expected output, continuing with segmented transcript")

                        except Exception as e:
                            proc_logger.log_error(f"Error during text tagging: {str(e)}")
                            proc_logger.log_info("Continuing with segmented transcript without tagging")
                    else:
                        proc_logger.log_info("Text tagging is disabled, skipping...")

                else:
                    proc_logger.log_warning("Segmentation did not produce expected output, using corrected transcript")
            else:
                proc_logger.log_info("Segmentation is disabled, using corrected transcript")

        except Exception as e:
            proc_logger.log_error(f"Error during transcription segmentation: {str(e)}")
            proc_logger.log_info("Continuing with corrected transcript")

        return transcription_path
