#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch Processor
Handles batch translation processing of multiple chunks across multiple languages
"""

import os
import time
import json
import logging
import concurrent.futures
import pandas as pd
import threading # Added for lock
from typing import Dict, List, Union, Optional, Any # Added Any
from datetime import datetime

from .utils import format_time
from app.utils.file_path_manager import get_file_path_manager, FileType

logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Handles batch translation processing with optimized memory usage and parallelism
    """
    DEFAULT_CONTEXT_WINDOW = {"previous": 5, "next": 5, "min_sentence_length": 10, "max_sentence_length": 150}
    
    def _get_context_config_for_content_type(self, content_type: str) -> Dict:
        """Get Netflix-optimized context configuration based on content type."""
        
        context_configs = {
            "interview": {
                "max_segments": 3,  # Conversational - less context needed
                "target_length": 120,  # Shorter context for natural flow
            },
            "sports": {
                "max_segments": 2,  # Fast-paced - minimal context
                "target_length": 80,
            },
            "documentary": {
                "max_segments": 4,  # Educational - more context helpful
                "target_length": 200,
            },
            "educational": {
                "max_segments": 4,  # Learning content - context important
                "target_length": 180,
            },
            "news": {
                "max_segments": 3,  # Factual - moderate context
                "target_length": 150,
            },
            "entertainment": {
                "max_segments": 3,  # Varied content - balanced approach
                "target_length": 140,
            },
            "tutorial": {
                "max_segments": 4,  # Step-by-step - context crucial
                "target_length": 180,
            },
            "presentation": {
                "max_segments": 3,  # Business context - moderate
                "target_length": 160,
            }
        }
        
        return context_configs.get(content_type, {
            "max_segments": 3,  # Default: balanced approach
            "target_length": 150,
        })
    
    def __init__(self, service):
        """
        Initialize the batch processor
        
        Args:
            service: Parent translation service instance
        """
        self.service = service
        self.translation_lock = threading.Lock()
        self.file_manager = get_file_path_manager()
        
    def process_batch_translation(self, job_id: int, job_dir: str, source_lang: str, 
                                target_langs: Union[str, List[str]], max_workers: int = 5) -> str:
        """
        Process batch translation of multiple chunks to multiple languages
        
        Args:
            job_id: Job ID
            job_dir: Directory containing the input files and where results will be saved
            source_lang: Source language code
            target_langs: Target language code(s) as a string or list
            max_workers: Maximum number of parallel workers for translation
            
        Returns:
            Path to the translation results file
        """
        try:
            # Preprocess target languages list
            if isinstance(target_langs, str):
                logger.info(f"Converting target_langs from string '{target_langs}' to list")
                target_langs = [lang.strip() for lang in target_langs.split(',')] if ',' in target_langs else [target_langs]
                logger.info(f"Target languages: {target_langs}")
            
            # Prepare translation configuration
            config = self._prepare_translation_config(job_dir, source_lang, target_langs)
            logger.info(f"Normalized target languages: {config['target_langs']}")
            
            # Check if results already exist and not forced to retranslate
            if os.path.exists(config["base_output_path"]) and not config["force_retranslation"]:
                logger.info("Translation results already exist, skipping translation.")
                return config["base_output_path"]
            elif os.path.exists(config["base_output_path"]):
                logger.info("FORCE_RETRANSLATION is enabled, proceeding with new translation")
            
            # Load source chunks using file_path_manager
            from app.models.job_context import JobContext
            # Create context for file_path_manager (assuming user_id=1 as default)
            context = JobContext(user_id=1, job_id=job_id, content_hash=None)
            chunks_df = self.service.load_chunks_from_context(context)
            if chunks_df is None or len(chunks_df) == 0:
                logger.warning("No chunks found to translate")
                return None
            
            # Load metadata and terminology
            metadata = self._load_metadata(job_id, job_dir)
            terminology = self.service.load_terminology(job_dir)
            logger.info(f"Loaded {len(terminology)} terminology entries")
            
            # Process all languages
            translation_data = self._process_all_languages(
                chunks_df=chunks_df,
                config=config,
                metadata=metadata,
                terminology=terminology,
                max_workers=max_workers
            )
            
            # Save results
            self._save_translation_results(translation_data, config)
            
            # Generate translation report
            self._generate_translation_report(translation_data["stats"], config)
            
            return config["base_output_path"]
                
        except Exception as e:
            logger.error(f"Error in batch translation process: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _prepare_translation_config(self, job_dir: str, source_lang: str, target_langs: List[str]) -> Dict:
        """
        Prepare translation configuration
        
        Args:
            job_dir: Job directory path
            source_lang: Source language code
            target_langs: Target language codes list
            
        Returns:
            Dictionary with translation configuration
        """
        # Normalize language codes
        from .utils import normalize_language_code
        
        normalized_target_langs = []
        for lang in target_langs:
            if not lang or not isinstance(lang, str):
                logger.warning(f"Skipping invalid language code: {lang}")
                continue
                
            normalized_lang = normalize_language_code(lang)
            if normalized_lang != lang.strip():
                logger.warning(f"Converting language code '{lang}' to standard code '{normalized_lang}'")
            normalized_target_langs.append(normalized_lang)
        
        # Get content hash from job_dir (assumed to be the last part of the path)
        content_hash = os.path.basename(os.path.normpath(job_dir))
        
        # Build configuration dictionary with FilePathManager paths
        config = {
            "job_dir": job_dir,
            "content_hash": content_hash,
            "source_lang": normalize_language_code(source_lang) or "en",
            "target_langs": normalized_target_langs,
            # Removed base_output_path - no longer generating cleaned_chunks_translated.xlsx
            "stats_path": self.file_manager.get_file_path(
                content_hash,
                FileType.LOG,
                segment_id='translation_stats.json'
            ),
            "translations_dir": self.file_manager.get_file_path(
                content_hash,
                FileType.TRANSLATION,
                segment_id='translations'
            ),
            "json_output_path": self.file_manager.get_file_path(
                content_hash,
                FileType.TRANSLATION,
                segment_id='all_translations.json'
            ),
            "translation_style": os.environ.get("TRANSLATION_STYLE", "subtitle"),
            "max_char_length": int(os.environ.get("TRANSLATION_MAX_CHARS", "30")),
            "force_retranslation": os.environ.get("FORCE_RETRANSLATION", "false").lower() == "true"
        }
        
        return config
    
    def _load_metadata(self, job_id: int, job_dir: str) -> Dict:
        """
        Load video metadata for context enhancement, including summary and terminology.
        Generates summary and extracts terminology if not already available.
        
        Args:
            job_id: Job ID
            job_dir: Job directory path
            
        Returns:
            Metadata dictionary with summary and terminology
        """
        metadata = {}
        content_hash = os.path.basename(os.path.normpath(job_dir))
        
        try:
            # Get paths using FilePathManager
            log_dir = os.path.dirname(self.file_manager.get_file_path(
                content_hash, 
                FileType.LOG,
                segment_id='dummy'  # Just to get the log directory
            ))
            
            # Load standard metadata file
            metadata_path = self.file_manager.get_file_path(
                content_hash,
                FileType.METADATA,
                segment_id='metadata.json'
            )
            
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                logger.info(f"Loaded metadata from {metadata_path}")
            
            # Get summary and terminology paths
            summary_path = self.file_manager.get_file_path(
                content_hash,
                FileType.LOG,
                segment_id='summary.json'
            )
            terminology_path = self.file_manager.get_file_path(
                content_hash,
                FileType.LOG,
                segment_id='terminology.json'
            )
            
            needs_analysis = False
            
            # Check if we need to generate summary and terminology
            if not os.path.exists(summary_path) or not os.path.exists(terminology_path):
                logger.info("Summary or terminology not found, will generate them")
                needs_analysis = True
            
            # If we have a transcript, we can generate summary and terminology
            transcript_path = self.file_manager.get_file_path(
                content_hash,
                FileType.TRANSCRIPT,
                segment_id='transcript.txt'
            )
            
            if needs_analysis and os.path.exists(transcript_path):
                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript = f.read()
                    
                    # Get source and target languages from metadata or use defaults
                    source_lang = metadata.get('source_language', 'en')
                    target_langs = metadata.get('target_languages', ['zh'])
                    
                    # Generate summary and terminology
                    analysis_result = self.service.analyze_content(
                        job_id=job_id,
                        job_dir=job_dir,
                        source_lang=source_lang,
                        target_langs=target_langs
                    )
                    
                    if analysis_result.get('status') == 'success':
                        # Save summary to file as JSON using FilePathManager
                        summary_path = self.file_manager.get_file_path(
                            content_hash,
                            FileType.LOG,
                            segment_id='summary.json'
                        )
                        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump({"summary": analysis_result.get('summary', '')}, f, ensure_ascii=False, indent=2)
                        logger.info(f"Saved summary to {summary_path}")
                        
                        # Save terminology using centralized method
                        from app.services.semantic_service import SemanticService
                        semantic_service = SemanticService(self.service)
                        terminology_path = semantic_service.save_terminology_to_file(
                            analysis_result.get('terminology', {}),
                            os.path.dirname(summary_path),  # Use the log directory
                            "terminology.json"
                        )
                        logger.info(f"Saved terminology to {terminology_path}")
                        
                        # Update metadata with paths and analysis info
                        metadata['summary'] = analysis_result.get('summary', '')
                        metadata['terminology'] = analysis_result.get('terminology', {})
                        metadata['summary_path'] = summary_path
                        metadata['terminology_path'] = terminology_path
                        metadata['last_analyzed'] = datetime.now().isoformat()
                        
                        # Save updated metadata
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, ensure_ascii=False, indent=2)
                            
                        logger.info("Successfully generated and saved summary and terminology")
                    else:
                        logger.warning(f"Failed to generate analysis: {analysis_result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"Error during content analysis: {str(e)}")
            
            # Load existing summary if available and not already in metadata
            if 'summary' not in metadata and os.path.exists(summary_path):
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary_data = json.load(f)
                        metadata['summary'] = summary_data.get('summary', '')
                except Exception as e:
                    logger.error(f"Error loading summary from {summary_path}: {str(e)}")
            
            # Load existing terminology if available and not already in metadata
            if 'terminology' not in metadata and os.path.exists(terminology_path):
                try:
                    # Use the semantic service's load method which handles path fallbacks
                    from app.services.semantic_service import SemanticService
                    semantic_service = SemanticService(self.service)
                    metadata['terminology'] = semantic_service.load_terminology_from_file(terminology_path)
                except Exception as e:
                    logger.error(f"Error loading terminology from {terminology_path}: {str(e)}")
                    metadata['terminology'] = {"terms": [], "source_language": "en", "target_languages": ["zh"]}
            
            # Ensure we have at least empty values for summary and terminology
            if 'summary' not in metadata:
                metadata['summary'] = ""
            if 'terminology' not in metadata:
                metadata['terminology'] = {"terms": [], "source_language": "en", "target_languages": ["zh"]}
            
            # Limit summary length to avoid overly long prompts
            if metadata['summary']:
                metadata['summary'] = metadata['summary'][:300] + "..." if len(metadata['summary']) > 300 else metadata['summary']
                logger.info("Added content summary to translation metadata")
        except Exception as e:
            logger.warning(f"Could not load metadata or summary: {str(e)}")
        
        # Use directory name as basic title (if not exists)
        if "title" not in metadata and os.path.basename(job_dir):
            metadata["title"] = os.path.basename(job_dir)
        
        return metadata
    
    def _process_all_languages(self, chunks_df: pd.DataFrame, config: Dict, metadata: Dict, 
                            terminology: Dict, max_workers: int) -> Dict:
        """
        Process all languages with optimized memory usage and parallelism
        
        Args:
            chunks_df: Source text dataframe
            config: Translation configuration
            metadata: Video metadata
            terminology: Terminology dictionary
            max_workers: Maximum worker threads
            
        Returns:
            Dictionary with all translation results and statistics
        """
        # Global statistics initialization
        stats = {"global": {"total_chunks": len(chunks_df)}}
        
        # Prepare base dataframe, add columns for all languages to avoid multiple copies
        base_df = chunks_df.copy()  # Only copy once
        for lang in config["target_langs"]:
            # Only create necessary columns for each language
            base_df[f"text_{lang}"] = ""
            base_df[f"status_{lang}"] = "pending"
            base_df[f"needs_review_{lang}"] = False
        
        # Process each language
        all_results = {}
        logger.info(f"BatchProcessor._process_all_languages - Metadata for job: {config.get('job_id', 'N/A')}, Content Hash: {config.get('content_hash', 'N/A')}, Metadata: {{metadata}}")
        
        for lang in config["target_langs"]:
            logger.info(f"=== Starting translation to {lang} ===")
            
            # Process translation for current language
            base_df, lang_stats = self._translate_single_language(
                df=base_df,
                source_lang=config["source_lang"],
                target_lang=lang,
                metadata=metadata,
                terminology=terminology,
                style=config["translation_style"],
                max_length=config["max_char_length"],
                max_workers=max_workers
            )
            
            # Save statistics
            stats[lang] = lang_stats
            
            # Save single-language results
            lang_output_path = os.path.join(config["translations_dir"], f"translated_{lang}.xlsx")
            lang_df = base_df[["text", f"text_{lang}", f"status_{lang}", f"needs_review_{lang}", "start", "end"]].copy()
            lang_df.to_excel(lang_output_path, index=False)
            logger.info(f"Saved {lang} translations to {lang_output_path}")
            
            all_results[lang] = True  # Just record completion flag, don't store full DataFrame to save memory
        
        return {
            "df": base_df,  # Dataframe with all language translation results
            "stats": stats,  # Statistics information
            "processed_languages": list(all_results.keys())  # List of successfully processed languages
        }
    
    def _translate_single_language(self, df: pd.DataFrame, source_lang: str, target_lang: str,
                             metadata: Dict, terminology: Dict, style: str, max_length: int,
                             max_workers: int) -> Dict:
        """
        Process single language translation with optimized memory usage and parallelism
        
        Args:
            df: Dataframe with source text and target columns
            source_lang: Source language code
            target_lang: Target language code
            metadata: Job metadata dictionary
            terminology: Dictionary containing terminology per language
            style: Translation style to apply
            max_length: Maximum output length constraint
            max_workers: Maximum parallel workers
        
        Returns:
            Statistics dictionary for this language
        """
        stats = {
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "needs_review_count": 0,
            "time_taken": 0
            # terminology_metrics will be initialized after extracting language-specific terms
        }
        
        # Extract the relevant terminology for the current target_lang
        # This should be a dictionary like {"terms": [...]} or an empty dict if not found
        lang_specific_terminology_dict = terminology.get(target_lang, {})
        
        # Initialize terminology_metrics based on the specific terms for this language
        terms_list_for_metrics = lang_specific_terminology_dict.get("terms", [])
        if not isinstance(terms_list_for_metrics, list):
            terms_list_for_metrics = []
            logger.warning(f"Terminology for {target_lang} does not have a valid 'terms' list. Found: {lang_specific_terminology_dict.get('terms')}")
        
        stats["terminology_metrics"] = {"total_terms": len(terms_list_for_metrics), "applied": 0, "missed": 0}
        
        to_translate = []
        lang_col = f"text_{target_lang}"
        status_col = f"status_{target_lang}"
        review_col = f"needs_review_{target_lang}"
        
        context_window_config = self.DEFAULT_CONTEXT_WINDOW.copy()
        num_previous = context_window_config.get('previous', 0)
        num_next = context_window_config.get('next', 0)
        min_sentence_length = context_window_config.get('min_sentence_length', 10)
        max_sentence_length = context_window_config.get('max_sentence_length', 150)

        def is_complete_sentence(text):
            """Check if text ends with a sentence terminator"""
            text = text.strip()
            if not text:
                return False
            return text[-1] in ('.', '!', '?', '。', '！', '？')

        def get_context_segments(idx, direction, max_segments):
            """Netflix-optimized context selection with content-aware sizing"""
            segments = []
            current_text = ""
            
            # Dynamic context window based on content type
            content_type = metadata.get('summary', {}).get('content_type', 'general') if isinstance(metadata.get('summary'), dict) else 'general'
            context_config = self._get_context_config_for_content_type(content_type)
            
            effective_max_segments = min(max_segments, context_config['max_segments'])
            target_context_length = context_config['target_length']
            
            for i in range(1, effective_max_segments + 1):
                current_idx = idx + (i if direction == 'next' else -i)
                
                # Check boundaries
                if current_idx < 0 or current_idx >= len(df):
                    break
                
                segment_text = df.iloc[current_idx]["text"].strip()
                if not segment_text:
                    continue
                
                # Smart length management - prioritize quality over quantity
                combined_length = len(current_text) + len(segment_text)
                if combined_length > target_context_length:
                    # If we haven't collected any context yet, take at least this segment (truncated)
                    if not segments and not current_text:
                        truncated = segment_text[:target_context_length]
                        segments.append(truncated)
                    break
                    
                # Add space between segments if needed
                if current_text and not current_text[-1].isspace() and not segment_text[0].isspace():
                    current_text += " "
                    
                current_text += segment_text
                
                # Check for natural stopping points
                if is_complete_sentence(segment_text) and len(current_text) >= min_sentence_length:
                    segments.insert(0, current_text) if direction == 'prev' else segments.append(current_text)
                    current_text = ""
                    
                    # Stop if we have sufficient context
                    total_context_length = sum(len(s) for s in segments)
                    if total_context_length >= target_context_length * 0.8:  # 80% of target is sufficient
                        break
            
            # Add any remaining text
            if current_text:
                segments.insert(0, current_text) if direction == 'prev' else segments.append(current_text)
                
            return segments

        for idx, row in df.iterrows():
            # Prepare chunk-specific metadata, starting with a copy of job metadata
            chunk_metadata = metadata.copy()
            chunk_metadata["style"] = style
            chunk_metadata["max_length"] = max_length
            
            # Timing information is no longer added to metadata as it's not needed for translation

            # Get context segments with smart aggregation
            previous_segments = get_context_segments(idx, 'prev', num_previous)
            next_segments = get_context_segments(idx, 'next', num_next)

            chunk = {
                "idx": idx,
                "text": row["text"],
                "source_lang": source_lang,
                "target_lang": target_lang,
                "previous_segments": previous_segments,
                "next_segments": next_segments,
                "metadata": chunk_metadata, # Contains style, max_length, and timing info
                # Pass the language-specific terminology dictionary
                "terminology": lang_specific_terminology_dict, 
                "context_window": context_window_config
            }
            to_translate.append(chunk)
        
        start_time = time.time()

        if not to_translate: # Handle case with no chunks to translate
            logger.info(f"No chunks to translate for {target_lang}.")
            return stats
            
        effective_workers = min(max_workers, len(to_translate), 20) # Max 20 threads
        logger.info(f"Translating {len(to_translate)} chunks to {target_lang} with {effective_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_to_chunk = {executor.submit(self._translate_chunk_safely, chunk_data): chunk_data for chunk_data in to_translate}
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    original_chunk = future_to_chunk[future]
                    result_dict = future.result()
                    current_idx = original_chunk["idx"]
                    
                    df.at[current_idx, lang_col] = result_dict["target_text"]
                    df.at[current_idx, status_col] = result_dict["translation_status"]
                    df.at[current_idx, review_col] = result_dict["needs_review"]
                    
                    self._update_translation_stats(stats, result_dict)
                    
                except Exception as e:
                    logger.error(f"Error processing translation result for chunk {original_chunk.get('idx', 'unknown')}: {str(e)}", exc_info=True)
                    stats["failed_count"] += 1 
            
        stats["time_taken"] = time.time() - start_time
        logger.info(f"Completed translation to {target_lang} in {stats['time_taken']:.2f} seconds")
        logger.info(f"Success: {stats['success_count']}, Failed: {stats['failed_count']}, Needs Review: {stats['needs_review_count']}")
        # Log terminology metrics if available and meaningful
        if "terminology_metrics" in stats and stats["terminology_metrics"]["total_terms"] > 0:
            logger.info(f"Terminology for {target_lang}: Total terms: {stats['terminology_metrics']['total_terms']}, Applied: {stats['terminology_metrics'].get('applied', 'N/A')}, Missed: {stats['terminology_metrics'].get('missed', 'N/A')}")
        return df, stats
        
    def _translate_chunk_safely(self, chunk_data: Dict) -> Dict:
        """
        Safely execute translation using TranslationService.translate_chunk, handling errors.
        
        Args:
            chunk_data: Dictionary containing all necessary info for translating one chunk.
            
        Returns:
            A dictionary with translation results, status, and any errors.
        """
        try:
            # Metadata including timing, style, max_length is already prepared in chunk_data["metadata"]
            # by _translate_single_language
            
            service_context_param = {
                "previous_segments": chunk_data.get("previous_segments", []),
                "next_segments": chunk_data.get("next_segments", []),
                "metadata": chunk_data.get("metadata", {}) 
            }

            translated_text_str = ""
            with self.translation_lock:
                translated_text_str = self.service.translate_chunk(
                    text=chunk_data["text"],
                    source_lang=chunk_data["source_lang"],
                    target_lang=chunk_data["target_lang"],
                    terminology=chunk_data.get("terminology"),
                    context=service_context_param,
                    context_window=chunk_data.get("context_window")
                )
            
            # Determine status based on result
            status = "success"
            needs_review = False
            
            # Handle empty or identical translation results
            if not translated_text_str or translated_text_str == chunk_data["text"]:
                # Check if this is due to translation failure rather than legitimate same-language content
                if not translated_text_str:
                    translated_text_str = chunk_data["text"] # Ensure target_text is not None for DataFrame update
                    status = "empty_translation"
                    needs_review = True
                elif translated_text_str == chunk_data["text"]:
                    # Same text could be valid (e.g., names, technical terms) or translation failure
                    status = "identical_to_source"
                    needs_review = True
            
            # Handle translation error indicators
            elif translated_text_str.startswith("[Translation Error:"):
                status = "translation_error"
                needs_review = True

            return {
                "source_text": chunk_data["text"],
                "target_text": translated_text_str,
                "translation_status": status,
                "needs_review": needs_review,
                "error": None
            }
        except Exception as e:
            logger.error(f"Error translating chunk (idx {chunk_data.get('idx', 'unknown')}): {str(e)}", exc_info=True)
            return {
                "source_text": chunk_data["text"],
                "target_text": chunk_data["text"],  # Fallback to source text on error
                "translation_status": "error",
                "needs_review": True,
                "error": str(e)
            }
    def _update_translation_stats(self, stats: Dict, result: Dict) -> None:
        """
        Update translation statistics
        
        Args:
            stats: Statistics dictionary
            result: Translation result
        """
        if result["translation_status"] == "success":
            stats["success_count"] += 1
        elif result["translation_status"] == "failed":
            stats["failed_count"] += 1
        elif result["translation_status"] == "skipped_empty":
            stats["skipped_count"] += 1
            
        if result.get("needs_review", False):
            stats["needs_review_count"] += 1
            
        # Update terminology match statistics
        if "terminology_matches" in result and result["terminology_matches"]:
            stats["terminology_metrics"]["applied"] += result["terminology_matches"].get("applied", 0)
            stats["terminology_metrics"]["missed"] += result["terminology_matches"].get("missed", 0)
            
    def _save_translation_results(self, translation_data: Dict, config: Dict) -> pd.DataFrame:
        """
        Save translation results with smart repair and alignment
        
        Args:
            translation_data: Translation result data containing dataframe and stats
            config: Translation configuration with target languages and paths
            
        Returns:
            pd.DataFrame: The translation results dataframe with repaired and aligned text
        """
        # Get content hash from the job directory path
        content_hash = os.path.basename(os.path.dirname(config["base_output_path"]))
        
        # Get the dataframe copy
        df = translation_data["df"].copy()
        
        # Get the cleaned chunks file path for alignment
        cleaned_chunks_path = self.file_manager.get_file_path(
            content_hash,
            FileType.DEBUG_FILE,
            filename='cleaned_chunks.xlsx'
        )
        
        # Load cleaned chunks if exists, otherwise create a new DataFrame
        if os.path.exists(cleaned_chunks_path):
            cleaned_df = pd.read_excel(cleaned_chunks_path)
            expected_count = len(cleaned_df)
        else:
            cleaned_df = pd.DataFrame()
            expected_count = len(df)
        
        # Save translations for each target language
        for lang in config["target_langs"]:
            col_name = f"translated_text_{lang}"
            if col_name not in df.columns:
                continue
                
            # Get the translated text with segment numbers
            translated_texts = []
            for i, row in enumerate(df[df[col_name].notna()].itertuples(), 1):
                translated_texts.append(f"[{i}] {getattr(row, col_name)}")
            
            # Join the translated texts with newlines
            raw_content = '\n'.join(translated_texts)
            
            # Apply smart repair and realignment
            from app.services.subtitle.alignment import smart_repair_and_realign
            repaired_lines = smart_repair_and_realign(
                raw_content=raw_content,
                expected_count=expected_count,
                lang_code=lang
            )
            
            # Save the repaired lines to the cleaned chunks DataFrame
            repaired_col = f"repaired_{lang}"
            cleaned_df[repaired_col] = pd.Series(repaired_lines)
            
            # Save the original translation as plain text
            output_txt = self.file_manager.get_file_path(
                content_hash,
                FileType.TRANSLATION_SEGMENTED_TXT,
                language=lang
            )
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_txt), exist_ok=True)
            
            # Write original text output
            with open(output_txt, 'w', encoding='utf-8') as f:
                f.write(raw_content)
            
            # Save the repaired text as a separate file
            repaired_txt = output_txt.replace('.txt', '_repaired.txt')
            with open(repaired_txt, 'w', encoding='utf-8') as f:
                for i, line in enumerate(repaired_lines, 1):
                    f.write(f"[{i}] {line}\n")
        
        # Save the cleaned chunks with repaired translations
        if not cleaned_df.empty:
            cleaned_df.to_excel(cleaned_chunks_path, index=False)
            logger.info(f"Saved repaired translations to {cleaned_chunks_path}")
        
        return df
        
    def _generate_translation_report(self, stats: Dict, config: Dict) -> None:
        """
        Log basic translation completion information
        
        Args:
            stats: Translation statistics
            config: Translation configuration
        """
        # Log a simple completion message
        logger.info("\n" + "="*80)
        logger.info("TRANSLATION COMPLETED")
        logger.info("="*80)
        logger.info(f"Source Language: {config['source_lang']}")
        logger.info(f"Target Languages: {', '.join(config['target_langs'])}")
        logger.info("="*80)
        logger.info("Translation process completed successfully")
