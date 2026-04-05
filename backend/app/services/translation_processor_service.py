"""
Translation Processor Service — Scene-based batch translation.

Translates content by semantic scenes (from Step 2) rather than line-by-line.
Each scene is sent to the LLM as one block with full context (global analysis,
scene digest, terminology, previous/next scene hints), then split back by [N]
tags for downstream subtitle alignment.
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.job import Job, JobResult
from app.models.job_context import JobContext
from app.models.job import ResultType as RT
from app.models.translation_job import StepName, StepStatus
from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.services.status_service import StatusUpdateService
from app.services.usage_tracker_service import UsageTrackerService
from app.services.translation_providers.yunwu_provider import YunwuTranslationProvider
from app.utils.file_path_manager import FileType, get_file_path_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

# Language code to display name
LANG_NAMES = {
    'en': 'English', 'zh': 'Chinese', 'es': 'Spanish', 'fr': 'French',
    'de': 'German', 'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian',
    'ar': 'Arabic', 'pt': 'Portuguese', 'it': 'Italian', 'hi': 'Hindi',
}


class TranslationProcessorService:
    """
    Orchestrates scene-based translation for the workflow pipeline.

    Responsibilities:
    - Load Step 2 outputs (global analysis, scenes, digests, terminology)
    - Group tagged lines into scene blocks
    - Translate each scene with rich context via LLM
    - Split translated scenes back into tagged lines
    - Validate tag completeness
    - Build alignment file for subtitle generation
    """

    def __init__(self, db: Session, job_service, semantic_service):
        self.db = db
        self.job_service = job_service
        self.semantic_service = semantic_service
        self.file_manager = get_file_path_manager()
        self.usage_tracker = UsageTrackerService(db)

        # Initialize LLM provider for scene translation
        provider_name = settings.TRANSLATION_PROVIDER
        if provider_name == "translator":
            cfg = {
                "api_key": settings.TRANSLATOR_API_KEY,
                "base_url": settings.TRANSLATOR_BASE_URL,
                "model": settings.TRANSLATOR_MODEL,
                "temperature": settings.TRANSLATOR_TEMPERATURE,
                "max_tokens": settings.TRANSLATOR_MAX_TOKENS,
                "timeout": settings.TRANSLATOR_TIMEOUT,
            }
        else:
            cfg = {
                "api_key": settings.YUNWU_API_KEY,
                "base_url": settings.YUNWU_BASE_URL,
                "model": settings.YUNWU_MODEL,
                "temperature": settings.YUNWU_TEMPERATURE,
                "max_tokens": settings.YUNWU_MAX_TOKENS,
                "timeout": settings.YUNWU_TIMEOUT,
            }
        self.provider = YunwuTranslationProvider(cfg)

    # ──────────────────────────────────────────────
    # Public API called by WorkflowService
    # ──────────────────────────────────────────────

    def prepare_translation_input(self, job: Job, context: JobContext,
                                  transcription_path: str, proc_logger: ProcessingLogger) -> str:
        """Copy processed transcription to the translation input location."""
        proc_logger.start_stage(ProcessingStage.TERMINOLOGY_EXTRACTION,
                                "Preparing translation input")

        translation_input_path = self.file_manager.get_file_path(
            context=context,
            file_type=FileType.TRANSLATION_SEGMENTED_TXT,
            language=job.source_language
        )

        text_content = self.file_manager.read_text(transcription_path)
        self.file_manager.write_text(translation_input_path, text_content)

        proc_logger.log_info(f"Translation input ready: {translation_input_path}")
        proc_logger.complete_stage(ProcessingStage.TERMINOLOGY_EXTRACTION,
                                   "Translation input prepared")
        return translation_input_path

    def perform_translation(self, job: Job, context: JobContext,
                            translation_input_path: str,
                            proc_logger: ProcessingLogger) -> Dict[str, str]:
        """
        Main entry point: scene-based batch translation for all target languages.

        Flow:
        1. Load input lines + Step 2 context
        2. Group lines into scenes
        3. For each target language, translate each scene block
        4. Split back by [N] tags → sorted file
        5. Build alignment xlsx for subtitle generation
        """
        target_langs = self._parse_target_langs(job)

        proc_logger.start_stage(ProcessingStage.TRANSLATION,
                                f"Translating to {len(target_langs)} language(s)")

        if not target_langs:
            proc_logger.log_warning("No target languages, skipping")
            proc_logger.complete_stage(ProcessingStage.TRANSLATION, "Skipped")
            return {}

        self._update_step(job.id, StepName.TRANSLATING, StepStatus.IN_PROGRESS, 0, "Starting")

        # ── Load inputs ──────────────────────────────
        lines = self._load_lines(translation_input_path)
        tag_map = self._build_tag_map(lines)
        expected_tags = sorted(tag_map.keys())
        proc_logger.log_info(f"Loaded {len(lines)} lines, {len(expected_tags)} tags")

        # ── Load Step 2 context ──────────────────────
        global_analysis, scenes, scene_digests, terminology = self._load_step2_context(context, proc_logger)

        # ── Group by scene, then chunk large scenes ──
        scene_blocks = self._group_by_scene(tag_map, scenes, proc_logger)
        scene_blocks = self._chunk_large_scenes(scene_blocks, max_lines_per_chunk=15)
        proc_logger.log_info(f"Grouped into {len(scene_blocks)} translation chunks")

        # ── Translate each language ──────────────────
        translation_files: Dict[str, str] = {}

        for lang in target_langs:
            proc_logger.log_info(f"── Translating to {lang} ──")

            sorted_sentences = self._translate_language(
                job=job, context=context, lang=lang,
                scene_blocks=scene_blocks,
                global_analysis=global_analysis,
                scene_digests=scene_digests,
                terminology=terminology,
                expected_tags=expected_tags,
                proc_logger=proc_logger,
            )

            # Save sorted (one tagged line per row)
            sorted_path = self.file_manager.get_file_path(
                context=context, file_type=FileType.TRANSLATION_SORTED_TXT, language=lang)
            self.file_manager.write_text(sorted_path, '\n'.join(sorted_sentences) + '\n')

            # Also save raw (same content, different FileType for downstream compatibility)
            raw_path = self.file_manager.get_file_path(
                context=context, file_type=FileType.TRANSLATION_TXT, language=lang)
            self.file_manager.write_text(raw_path, '\n'.join(sorted_sentences) + '\n')

            translation_files[lang] = raw_path
            proc_logger.log_info(f"{lang}: saved {len(sorted_sentences)} lines")

        # ── Post-translation: alignment file + job results ──
        self._register_translation_results(job, translation_files, proc_logger)
        self._build_alignment_file(job, context, translation_files, proc_logger)

        self._update_step(job.id, StepName.TRANSLATING, StepStatus.COMPLETED, 100, "Done")
        proc_logger.complete_stage(ProcessingStage.TRANSLATION,
                                   f"Translated to {len(translation_files)} language(s)")
        return translation_files

    # ──────────────────────────────────────────────
    # Core: translate one language across all scenes
    # ──────────────────────────────────────────────

    def _translate_language(
        self, job: Job, context: JobContext, lang: str,
        scene_blocks: List[Tuple[Dict, List[str]]],
        global_analysis: Dict, scene_digests: List[Dict],
        terminology: List[Dict], expected_tags: List[int],
        proc_logger: ProcessingLogger,
    ) -> List[str]:
        """
        Translate all scenes for a single target language.

        For each scene:
        1. Send scene block to LLM
        2. Immediately parse + validate tags against that scene's expected tags
        3. Any missing tag falls back to the original source line (not empty)

        Returns sorted tagged lines covering all expected_tags.
        """
        source_lang_name = LANG_NAMES.get(job.source_language, job.source_language)
        target_lang_name = LANG_NAMES.get(lang, lang)
        total_scenes = len(scene_blocks)
        prev_scene_hint = ""

        # Global tag → translated line map (accumulated across scenes)
        translated_map: Dict[int, str] = {}

        # Build source fallback map (tag → original source line)
        source_map: Dict[int, str] = {}
        for _, lines in scene_blocks:
            for line in lines:
                m = re.match(r'\[(\d+)\]', line)
                if m:
                    source_map[int(m.group(1))] = line

        # Scene-level translation results for JSON export
        scene_results: List[Dict] = []

        # ── Build all prompts first ──
        scene_tasks = []
        for idx, (scene_info, scene_lines) in enumerate(scene_blocks):
            scene_id = scene_info.get('scene_id', idx + 1)
            scene_expected = []
            for line in scene_lines:
                m = re.match(r'\[(\d+)\]', line)
                if m:
                    scene_expected.append(int(m.group(1)))

            prompt = self._build_scene_prompt(
                scene_lines=scene_lines, scene_info=scene_info,
                global_analysis=global_analysis, scene_digests=scene_digests,
                terminology=terminology, source_lang_name=source_lang_name,
                target_lang_name=target_lang_name, prev_scene_hint="",
                next_scene_topic=scene_blocks[idx + 1][0].get('topic', '') if idx + 1 < total_scenes else '',
            )
            scene_tasks.append((idx, scene_id, scene_expected, prompt, scene_info, scene_lines))

        # ── Parallel LLM translation ──
        from concurrent.futures import ThreadPoolExecutor, as_completed
        MAX_PARALLEL = 4

        def _translate_one(task):
            idx, scene_id, scene_expected, prompt, scene_info, scene_lines = task
            try:
                resp = self.provider.translate(
                    prompt, job.source_language, lang,
                    metadata={"type": "scene_translation"}
                )
                raw_output = str(resp.get("translated_text", "")).strip()
            except Exception as e:
                proc_logger.log_error(f"Scene {scene_id} LLM error: {e}")
                raw_output = ""
            return idx, scene_id, scene_expected, raw_output, scene_info, scene_lines

        proc_logger.log_info(f"Translating {len(scene_tasks)} chunks (parallel={MAX_PARALLEL})")

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
            futures = {executor.submit(_translate_one, t): t for t in scene_tasks}
            results_by_idx = {}
            for future in as_completed(futures):
                idx, scene_id, scene_expected, raw_output, scene_info, scene_lines = future.result()
                results_by_idx[idx] = (scene_id, scene_expected, raw_output, scene_info, scene_lines)
                done = len(results_by_idx)
                self._update_step(job.id, StepName.TRANSLATING, StepStatus.IN_PROGRESS,
                                  int(done / total_scenes * 100),
                                  f"Chunk {done}/{total_scenes} for {lang}")

        # ── Process results in order ──
        for idx in range(len(scene_tasks)):
            scene_id, scene_expected, raw_output, scene_info, scene_lines = results_by_idx[idx]

            parsed = self._robust_tag_split(raw_output)

            scene_missing = []
            scene_recovered = []
            for tag in scene_expected:
                if tag in parsed:
                    translated_map[tag] = parsed[tag]
                else:
                    scene_missing.append(tag)
                    if tag in source_map:
                        translated_map[tag] = source_map[tag]
                        scene_recovered.append(tag)

            if scene_missing:
                proc_logger.log_warning(
                    f"Scene {scene_id}: {len(scene_missing)} missing → recovered {len(scene_recovered)}")

            scene_results.append({
                "scene_id": scene_id, "topic": scene_info.get('topic', ''),
                "expected_tags": scene_expected,
                "translated_tags": [t for t in scene_expected if t in parsed],
                "missing_tags": scene_missing, "recovered_from_source": scene_recovered,
            })

        # ── Assemble final sorted output ──
        final_lines = []
        still_missing = []
        for tag in expected_tags:
            if tag in translated_map:
                final_lines.append(translated_map[tag])
            elif tag in source_map:
                final_lines.append(source_map[tag])  # ultimate fallback
                still_missing.append(tag)
            else:
                final_lines.append(f"[{tag}] ")
                still_missing.append(tag)

        if still_missing:
            proc_logger.log_warning(f"Final: {len(still_missing)} tags fell back to source: {still_missing[:20]}")

        # ── Save structured JSON result (for debugging / downstream) ──
        self._save_translation_json(context, lang, translated_map, source_map,
                                     scene_results, expected_tags, proc_logger)

        return final_lines

    # ──────────────────────────────────────────────
    # Prompt builder
    # ──────────────────────────────────────────────

    def _build_scene_prompt(
        self,
        scene_lines: List[str],
        scene_info: Dict,
        global_analysis: Dict,
        scene_digests: List[Dict],
        terminology: List[Dict],
        source_lang_name: str,
        target_lang_name: str,
        prev_scene_hint: str,
        next_scene_topic: str,
    ) -> str:
        """Build a self-contained prompt for translating one scene block."""

        scene_text = '\n'.join(scene_lines)
        scene_id = scene_info.get('scene_id', '?')

        # ── Global context section ──
        global_parts = []
        if global_analysis.get('content_overview'):
            global_parts.append(f"Content: {global_analysis['content_overview']}")
        if global_analysis.get('domain'):
            global_parts.append(f"Domain: {global_analysis['domain']}")
        if global_analysis.get('tone'):
            global_parts.append(f"Tone: {global_analysis['tone']}")
        if global_analysis.get('target_audience'):
            global_parts.append(f"Audience: {global_analysis['target_audience']}")
        global_section = '\n'.join(global_parts) if global_parts else 'General content'

        # ── Scene context section ──
        digest = ''
        for sd in scene_digests:
            if sd.get('scene_id') == scene_info.get('scene_id'):
                digest = sd.get('digest', '')
                break

        scene_context_parts = []
        if scene_info.get('topic'):
            scene_context_parts.append(f"Topic: {scene_info['topic']}")
        if digest:
            scene_context_parts.append(f"Context: {digest}")
        if prev_scene_hint:
            scene_context_parts.append(prev_scene_hint)
        if next_scene_topic:
            scene_context_parts.append(f"[Next scene topic: {next_scene_topic}]")
        scene_section = '\n'.join(scene_context_parts) if scene_context_parts else ''

        # ── Terminology section ──
        term_lines = []
        for t in terminology[:15]:  # Cap at 15 terms
            if isinstance(t, dict):
                term = t.get('term', '')
                explanation = t.get('explanation', '')
                term_lines.append(f"• {term}" + (f" — {explanation}" if explanation else ''))
            elif isinstance(t, str):
                term_lines.append(f"• {t}")
        term_section = "KEY TERMS (preserve or translate accurately):\n" + '\n'.join(term_lines) if term_lines else ''

        # ── Assemble prompt ──
        prompt = f"""Translate {source_lang_name} → {target_lang_name} subtitles. Scene {scene_id}.

CONTEXT:
{global_section}
{scene_section}

{term_section}

CRITICAL RULES:
1. Keep ALL [N] tags exactly — same count, same order
2. One translated line per input line with [N] tag at start
3. Sound like NATURAL {target_lang_name} speech — colloquial, not literary
4. Match the speaker's tone: casual→casual, angry→angry, funny→funny
5. Keep swear words at equal intensity, do NOT censor or soften
6. Keep concise but NEVER omit meaning — translate the COMPLETE sentence
7. Proper nouns from terms list must be consistent

SOURCE:
{scene_text}

{target_lang_name} TRANSLATION:"""

        return prompt

    # ──────────────────────────────────────────────
    # Step 2 context loading
    # ──────────────────────────────────────────────

    def _load_step2_context(self, context: JobContext, proc_logger: ProcessingLogger) -> Tuple:
        """
        Load all Step 2 outputs: global_analysis, scenes, scene_digests, terminology.
        Returns (global_analysis_dict, scenes_list, digests_list, terms_list).
        """
        global_analysis = {}
        scenes = []
        scene_digests = []
        terminology = []

        try:
            ga_path = self.file_manager.get_file_path(context=context, file_type=FileType.GLOBAL_ANALYSIS_JSON)
            if self.file_manager.exists(ga_path):
                data = self.file_manager.read_json(ga_path)
                global_analysis = data.get('global_analysis', {})
                scenes = data.get('scenes', [])
                proc_logger.log_info(f"Step 2 context loaded: {len(scenes)} scenes, domain={global_analysis.get('domain', '?')}")
        except Exception as e:
            proc_logger.log_warning(f"Failed to load global analysis: {e}")

        try:
            sd_path = self.file_manager.get_file_path(context=context, file_type=FileType.SCENE_DIGESTS_JSON)
            if self.file_manager.exists(sd_path):
                data = self.file_manager.read_json(sd_path)
                scene_digests = data.get('scene_digests', [])
                proc_logger.log_info(f"Loaded {len(scene_digests)} scene digests")
        except Exception as e:
            proc_logger.log_warning(f"Failed to load scene digests: {e}")

        try:
            t_path = self.file_manager.get_file_path(context=context, file_type=FileType.TERMINOLOGY_JSON)
            if self.file_manager.exists(t_path):
                data = self.file_manager.read_json(t_path)
                terminology = data.get('terms', [])
                proc_logger.log_info(f"Loaded {len(terminology)} terminology terms")
        except Exception as e:
            proc_logger.log_warning(f"Failed to load terminology: {e}")

        return global_analysis, scenes, scene_digests, terminology

    # ──────────────────────────────────────────────
    # Line / tag helpers
    # ──────────────────────────────────────────────

    def _load_lines(self, path: str) -> List[str]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Translation input not found: {path}")
        content = self.file_manager.read_text(path)
        return [l.strip() for l in content.splitlines() if l.strip()]

    def _build_tag_map(self, lines: List[str]) -> Dict[int, str]:
        """tag_number → full line text"""
        m = {}
        for line in lines:
            match = re.match(r'\[(\d+)\]', line)
            if match:
                m[int(match.group(1))] = line
        return m

    def _group_by_scene(self, tag_map: Dict[int, str], scenes: List[Dict],
                        proc_logger: ProcessingLogger) -> List[Tuple[Dict, List[str]]]:
        """Group tagged lines into scene blocks."""
        all_tags = sorted(tag_map.keys())
        if not all_tags:
            return []

        if not scenes:
            single = {"scene_id": 1, "start_line": all_tags[0], "end_line": all_tags[-1], "topic": "Full content"}
            return [(single, [tag_map[t] for t in all_tags])]

        blocks = []
        for scene in scenes:
            s, e = scene.get('start_line', 0), scene.get('end_line', 0)
            scene_lines = [tag_map[t] for t in all_tags if s <= t <= e]
            if scene_lines:
                blocks.append((scene, scene_lines))

        # Orphan check
        covered = set()
        for scene in scenes:
            covered.update(range(scene.get('start_line', 0), scene.get('end_line', 0) + 1))
        orphans = [t for t in all_tags if t not in covered]
        if orphans:
            proc_logger.log_warning(f"{len(orphans)} orphan tags appended to last scene")
            if blocks:
                s_info, s_lines = blocks[-1]
                blocks[-1] = (s_info, s_lines + [tag_map[t] for t in orphans])
            else:
                blocks.append(({"scene_id": 0, "topic": "Uncategorized"}, [tag_map[t] for t in orphans]))

        return blocks

    @staticmethod
    def _chunk_large_scenes(scene_blocks: List[Tuple[Dict, List[str]]],
                            max_lines_per_chunk: int = 15) -> List[Tuple[Dict, List[str]]]:
        """Split scene blocks that exceed max_lines_per_chunk into smaller chunks."""
        result = []
        for scene_info, lines in scene_blocks:
            if len(lines) <= max_lines_per_chunk:
                result.append((scene_info, lines))
            else:
                # Split into chunks
                for i in range(0, len(lines), max_lines_per_chunk):
                    chunk = lines[i:i + max_lines_per_chunk]
                    chunk_info = {
                        **scene_info,
                        "scene_id": f"{scene_info.get('scene_id', 1)}.{i // max_lines_per_chunk + 1}",
                        "topic": scene_info.get('topic', ''),
                    }
                    result.append((chunk_info, chunk))
        return result

    # ──────────────────────────────────────────────
    # Robust tag parsing from LLM output
    # ──────────────────────────────────────────────

    def _robust_tag_split(self, raw_text: str) -> Dict[int, str]:
        """
        Parse LLM output into {tag_number: "full line with tag"} map.

        Handles:
        - Normal: one [N] per line
        - Merged:  [1] Hello [2] World [3] Foo  (multiple tags on one line)
        - Preamble: "Here is the translation:\n[1] Hello" (junk before first tag)
        - Missing newlines: "[1] Hello[2] World"  (no space between tags)

        Returns dict mapping tag_number → "[N] text content"
        """
        if not raw_text or not raw_text.strip():
            return {}

        result: Dict[int, str] = {}

        # Strategy: find ALL [N] positions in the raw text, then extract text between them
        tag_pattern = re.compile(r'\[(\d+)\]')
        matches = list(tag_pattern.finditer(raw_text))

        if not matches:
            return {}

        for i, match in enumerate(matches):
            tag_num = int(match.group(1))

            # Text for this tag runs from end of this match to start of next match (or end of string)
            start = match.end()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(raw_text)

            text_content = raw_text[start:end].strip()

            # Clean: remove trailing newlines, but keep the content
            text_content = text_content.split('\n')[0].strip() if '\n' in text_content and i + 1 < len(matches) else text_content.strip()

            # For multi-line content within a single tag (rare but possible),
            # join with space to keep it as one subtitle line
            text_content = ' '.join(text_content.split('\n')).strip()

            # Only keep first occurrence of each tag (LLM might repeat)
            if tag_num not in result:
                result[tag_num] = f"[{tag_num}] {text_content}"

        return result

    # ──────────────────────────────────────────────
    # JSON export for structured translation results
    # ──────────────────────────────────────────────

    def _save_translation_json(self, context: JobContext, lang: str,
                                translated_map: Dict[int, str],
                                source_map: Dict[int, str],
                                scene_results: List[Dict],
                                expected_tags: List[int],
                                proc_logger: ProcessingLogger):
        """
        Save structured translation result as JSON for debugging and downstream use.

        Format:
        {
            "language": "en",
            "tags": {
                "1": {"source": "[1] 原文", "translated": "[1] translation", "status": "ok"},
                "2": {"source": "[2] 原文", "translated": "[2] ...", "status": "fallback_source"},
            },
            "scenes": [...scene_results...],
            "stats": {"total": N, "translated": M, "fallback": K}
        }
        """
        try:
            tags_data = {}
            translated_count = 0
            fallback_count = 0

            for tag in expected_tags:
                src = source_map.get(tag, f"[{tag}] ")
                trl = translated_map.get(tag, "")

                if tag in translated_map and translated_map[tag] != source_map.get(tag, ''):
                    status = "ok"
                    translated_count += 1
                elif tag in translated_map:
                    status = "fallback_source"
                    fallback_count += 1
                else:
                    status = "missing"
                    fallback_count += 1

                tags_data[str(tag)] = {
                    "source": src,
                    "translated": trl or src,
                    "status": status,
                }

            output = {
                "language": lang,
                "generated_at": datetime.utcnow().isoformat(),
                "tags": tags_data,
                "scenes": scene_results,
                "stats": {
                    "total_tags": len(expected_tags),
                    "translated_ok": translated_count,
                    "fallback_source": fallback_count,
                    "total_scenes": len(scene_results),
                }
            }

            # Per-language JSON (DEBUG_FILE allows custom filename)
            json_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.DEBUG_FILE,
                filename=f"translation_{lang}.json"
            )
            self.file_manager.write_json(json_path, output)
            proc_logger.log_info(f"Translation JSON saved: {json_path} (ok={translated_count}, fallback={fallback_count})")

        except Exception as e:
            proc_logger.log_warning(f"Failed to save translation JSON for {lang}: {e}")

    # ──────────────────────────────────────────────
    # Alignment file for subtitle generation
    # ──────────────────────────────────────────────

    def _build_alignment_file(self, job: Job, context: JobContext,
                              translation_files: Dict[str, str],
                              proc_logger: ProcessingLogger):
        """
        Build aligned_chunks.json from segmented JSON + translation files.

        Output format:
        {
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "原文", "text_en": "translation", ...},
                ...
            ],
            "languages": ["en", "zh"],
            "total_segments": 123
        }
        """
        try:
            # Load timing segments (with word timestamps)
            job_dir = self.file_manager._get_job_dir(context.user_id, context.job_id)
            seg_json_path = os.path.join(job_dir, "segmented_transcript", "transcript_segmented.json")

            if not os.path.exists(seg_json_path):
                proc_logger.log_error(f"Segmented JSON not found at {seg_json_path}, cannot build alignment")
                return

            segments = self.file_manager.read_json(seg_json_path).get('segments', [])

            # Build base alignment list
            aligned = []
            for seg in segments:
                item = {
                    'start': seg.get('start', 0.0),
                    'end': seg.get('end', 0.0),
                    'text': seg.get('text', '').strip(),
                }
                # Carry word timestamps for precise subtitle timing
                if seg.get('words'):
                    item['words'] = seg['words']
                aligned.append(item)

            proc_logger.log_info(f"Alignment base: {len(aligned)} segments")

            # Merge translation columns
            for lang, file_path in translation_files.items():
                content = self.file_manager.read_text(file_path)
                cleaned = [re.sub(r'\[\d+\]\s*', '', l).strip()
                           for l in content.splitlines() if l.strip()]

                key = f"text_{lang}"
                for i, item in enumerate(aligned):
                    item[key] = cleaned[i] if i < len(cleaned) else ''

            # Save as JSON
            output = {
                "segments": aligned,
                "languages": list(translation_files.keys()),
                "total_segments": len(aligned),
            }

            json_path = self.file_manager.get_file_path(
                context=context, file_type=FileType.ALIGNED_CHUNKS_JSON)
            self.file_manager.write_json(json_path, output)
            proc_logger.log_info(f"Alignment JSON saved: {json_path} ({len(aligned)} segments)")

        except Exception as e:
            proc_logger.log_error(f"Alignment file error: {e}")

    # ──────────────────────────────────────────────
    # Job results & status helpers
    # ──────────────────────────────────────────────

    def _register_translation_results(self, job: Job, translation_files: Dict[str, str],
                                      proc_logger: ProcessingLogger):
        try:
            for lang, path in translation_files.items():
                result = JobResult(
                    job_id=job.id,
                    result_type=RT.SEGMENTED_TEXT,
                    language=lang,
                    file_path=path,
                    created_at=datetime.utcnow(),
                    metadata_={
                        "file_name": os.path.basename(path),
                        "file_size": os.path.getsize(path) if os.path.exists(path) else 0,
                        "mime_type": "text/plain",
                        "result_subtype": "translation_txt"
                    }
                )
                self.db.add(result)
            self.db.commit()

            for path in translation_files.values():
                self.file_manager.auto_sync_file_to_remote(path, proc_logger.log_info)

        except Exception as e:
            proc_logger.log_error(f"Error registering results: {e}")

    def _update_step(self, job_id: int, step: StepName, status: StepStatus,
                     progress: float, details: str):
        try:
            StatusUpdateService.update_step_status(self.db, job_id, step, status, progress, details)
        except Exception:
            pass

    def _parse_target_langs(self, job: Job) -> List[str]:
        if not job.target_languages:
            return []
        if isinstance(job.target_languages, str):
            return [l.strip() for l in job.target_languages.split(',') if l.strip()]
        return [l.strip() for l in job.target_languages if l.strip()]

    # ──────────────────────────────────────────────
    # Legacy: analyze_content (kept for API compatibility, no longer called by workflow)
    # ──────────────────────────────────────────────

    def analyze_content(self, job: Job, context: JobContext,
                       text_content: str, proc_logger: ProcessingLogger) -> Optional[Dict[str, Any]]:
        """Legacy method — content analysis is now done in Step 2 (transcription_processor)."""
        proc_logger.log_info("analyze_content called — skipping (handled by Step 2)")
        return {"status": "skipped", "reason": "Handled by Step 2 content understanding"}
