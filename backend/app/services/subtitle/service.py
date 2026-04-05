import os
import re
import logging
import threading
import traceback
from typing import Optional, List, Tuple, Dict, Any, Union
import pandas as pd
import numpy as np
from functools import lru_cache
from pathlib import Path
# pysbd removed - not used in current implementation
import json
# import torch
# from sentence_transformers import SentenceTransformer, util
from dataclasses import dataclass
from enum import Enum

# Import from local modules
from .alignment import generate_srt_content
from .utils import time_to_srt_format

logger = logging.getLogger(__name__)

class AlignmentStrategy(Enum):
    """Enum for available alignment strategies."""
    HEURISTIC = "heuristic"
    SEMANTIC = "semantic"

@dataclass
class AlignmentConfig:
    """Configuration for subtitle alignment with tunable parameters.
    
        Attributes:
    
            model_name: Name of the sentence transformer model to use for semantic similarity.
    
            min_similarity: Minimum similarity score (0-1) to consider segments matching.
    
            gap_penalty: Penalty for introducing gaps in the alignment.
    
            match_score: Score multiplier for matched segments.
    
            mismatch_penalty: Penalty for mismatched segments (allows path continuation).
    
            max_chars_per_second: Maximum characters per second for subtitle readability.
    
            max_chars_per_line: Maximum characters per line in subtitles.
    
            max_lines_per_sub: Maximum number of lines per subtitle block.
    
            min_segment_duration: Minimum duration in seconds for a subtitle segment.
    
            max_segment_duration: Maximum duration in seconds for a subtitle segment.
    
        """
    
        # Model configuration
    
        # model_name: str = "paraphrase-multilingual-mpnet-base-v2"
    
        
    
        # Alignment parameters
    
        min_similarity: float = 0.3  # Slightly increased for better matching
    
        gap_penalty: float = -1.5    # Increased penalty to prevent excessive gaps
    
        match_score: float = 1.2     # Increased reward for matches
    
        mismatch_penalty: float = -2.5  # Increased penalty for mismatches
    
        
    
        # Subtitle readability parameters - adjusted for Chinese text
    
        max_chars_per_second: int = 15      # Reduced for better readability
    
        max_chars_per_line: int = 20        # Chinese characters take more space
    
        max_lines_per_sub: int = 2          # Keep at 2 for readability
    
        
    
        # Timing constraints - adjusted for better segmentation
    
        min_segment_duration: float = 1.5   # Slightly longer minimum duration
    
        max_segment_duration: float = 5.0   # Shorter max duration for better comprehension
    
    
    
    class SubtitleService:
    
        """
    
        Service for handling subtitle processing, including advanced semantic alignment.
    
        """
    
        
    
        # --- 1. Initialization and Core Setup -- -
    
        
    
        def __init__(self):
    
            """
    
            Initializes the SubtitleService, setting up model caches, configurations, and locks.
    
            """
    
            # Semantic alignment components
    
            # self.st_models: Dict[str, "SentenceTransformer"] = {}
    
            # self.st_model_lock = threading.Lock()
    
            self.default_alignment_config = AlignmentConfig()
        
        # General configuration (can be loaded from settings)
        self.config: Dict[str, Any] = self._load_default_config()
        
        logger.info("SubtitleService initialized with heuristic and semantic alignment support.")
        
    def _load_default_config(self) -> Dict[str, Any]:
        """Loads the default configuration dictionary."""
        # In a real app, this might come from a settings file.
        return {
            'max_subtitle_line_length': 42,
            'min_subtitle_duration': 1.0,
            'max_subtitle_duration': 7.0,
        }

    # --- 2. Semantic Alignment Core Methods ---

    # def _get_st_model(self, model_name: Optional[str] = None) -> "SentenceTransformer":
    #     """
    #     Loads a SentenceTransformer model from cache or from disk in a thread-safe manner.
    #     """
    #     model_name = model_name or self.default_alignment_config.model_name
        
    #     if model_name in self.st_models:
    #         return self.st_models[model_name]
            
    #     with self.st_model_lock:
    #         if model_name in self.st_models:
    #             return self.st_models[model_name]

    #         logger.info(f"Loading SentenceTransformer model: {model_name}")
    #         device = 'cuda' if torch.cuda.is_available() else 'cpu'
    #         try:
    #             model = SentenceTransformer(model_name, device=device)
    #             self.st_models[model_name] = model
    #             logger.info(f"Successfully loaded model '{model_name}' on {device}")
    #             return model
    #         except Exception as e:
    #             logger.error(f"Failed to load SentenceTransformer model {model_name}: {e}", exc_info=True)
    #             raise

    # def _get_sentence_embeddings(self, sentences: List[str], model: "SentenceTransformer") -> "torch.Tensor":
    #     """Generates sentence embeddings for a list of text segments."""
    #     if not sentences:
    #         return torch.empty(0, model.get_sentence_embedding_dimension(), device=model.device)
        
    #     # Replace empty strings to avoid errors
    #     processed_sentences = [s if s.strip() else " " for s in sentences]
    #     return model.encode(
    #         processed_sentences,
    #         show_progress_bar=False,
    #         convert_to_tensor=True,
    #         normalize_embeddings=True
    #     )

    # def _calculate_similarity_matrix(self, source_embed: "torch.Tensor", target_embed: "torch.Tensor") -> "torch.Tensor":
    #     """Calculates the cosine similarity matrix between two sets of embeddings."""
    #     if source_embed.numel() == 0 or target_embed.numel() == 0:
    #         return torch.zeros(len(source_embed), len(target_embed))
    #     return util.cos_sim(source_embed, target_embed)
        
    # def _find_optimal_alignment(self, sim_matrix: "torch.Tensor", config: AlignmentConfig) -> List[Tuple[int, int]]:
    #     """Finds the optimal alignment path using dynamic programming with mismatch handling.
        
    #     This implementation uses a dynamic programming approach to find the optimal alignment
    #     between source and target segments, considering both matching and mismatching pairs.
        
    #     Args:
    #         sim_matrix: 2D tensor of similarity scores between source and target segments
    #         config: Alignment configuration parameters
            
    #     Returns:
    #         List of (source_idx, target_idx) pairs representing the optimal alignment path
    #     """
    #     if sim_matrix.numel() == 0:
    #         return []
            
    #     source_len, target_len = sim_matrix.shape
    #     device = sim_matrix.device
        
    #     # Initialize DP matrix with negative infinity
    #     dp = torch.full((source_len + 1, target_len + 1), float('-inf'), device=device)
    #     dp[0, 0] = 0  # Base case
        
    #     # For tracking the path
    #     path = torch.zeros((source_len + 1, target_len + 1, 2), dtype=torch.long, device=device)
        
    #     # Fill DP table
    #     for i in range(source_len + 1):
    #         for j in range(target_len + 1):
    #             if i == 0 and j == 0:
    #                 continue
                    
    #             options = []
                
    #             # Match/mismatch (diagonal move)
    #             if i > 0 and j > 0:
    #                 sim_score = sim_matrix[i-1, j-1].item()
    #                 score = dp[i-1, j-1] + (config.match_score * sim_score if sim_score >= config.min_similarity 
    #                                       else config.mismatch_penalty * (1 - sim_score))
    #                 options.append((score, i-1, j-1))
                
    #             # Gap in source (vertical move)
    #             if i > 0:
    #                 score = dp[i-1, j] + config.gap_penalty
    #                 options.append((score, i-1, j))
                
    #             # Gap in target (horizontal move)
    #             if j > 0:
    #                 score = dp[i, j-1] + config.gap_penalty
    #                 options.append((score, i, j-1))
                
    #             # Choose the best option
    #             if options:
    #                 best_score, best_i, best_j = max(options, key=lambda x: x[0])
    #                 dp[i, j] = best_score
    #                 path[i, j] = torch.tensor([best_i, best_j], device=device)
        
    #     # Backtrack to find the alignment path
    #     alignment = []
    #     i, j = source_len, target_len
        
    #     while i > 0 or j > 0:
    #         prev_i, prev_j = path[i, j].tolist()
            
    #         # Only add to alignment if it's a match/mismatch (not a gap)
    #         if i - prev_i == 1 and j - prev_j == 1:
    #             alignment.append((prev_i, prev_j))
                
    #         i, j = prev_i, prev_j
        
    #     # If we didn't find any matches, create a 1:1 alignment as fallback
    #     if not alignment and source_len > 0 and target_len > 0:
    #         min_len = min(source_len, target_len)
    #         alignment = [(i, i) for i in range(min_len)]
        
    #     # Reverse to get correct order (from start to end)
    #     return alignment[::-1]

    # def _split_and_format_merged_text(self, text: str, start: float, end: float, 
    #                               config: AlignmentConfig, lang_code: str) -> List[Dict]:
    #     """Splits and formats merged text into readable subtitle segments.
        
    #     This method handles both Chinese and other languages, ensuring subtitles are
    #     properly segmented for readability and timing. It respects the alignment
    #     configuration parameters for maximum line length and duration.
        
    #     Args:
    #         text: The text to split and format
    #         start: Start time in seconds
    #         end: End time in seconds
    #         config: Alignment configuration
    #         lang_code: Target language code
            
    #     Returns:
    #         List of formatted subtitle segments with timing information
    #     """
    #     total_duration = max(0.1, end - start)
    #     if not text or not text.strip():
    #         return []

    #     # Clean the text first to remove any unwanted characters
    #     text = text.strip()
        
    #     # Check if this is Chinese text
    #     is_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
        
    #     # Calculate maximum characters per chunk based on duration and configuration
    #     max_chars_per_chunk = min(
    #         int(total_duration * config.max_chars_per_second * 0.85),  # 85% of max for better readability
    #         config.max_chars_per_line * config.max_lines_per_sub
    #     )
        
    #     # Split text into sentences based on language
    #     sentences = self._segment_text_naturally(text, lang_code)
    #     if not sentences:
    #         return []
        
    #     # Group sentences into chunks that respect character limits
    #     chunks = []
    #     current_chunk = []
    #     current_length = 0
        
    #     for sent in sentences:
    #         sent = sent.strip()
    #         if not sent:
    #             continue
                
    #         sent_length = len(sent)
            
    #         # If adding this sentence would exceed the limit, finalize current chunk
    #         if current_chunk and current_length + sent_length > max_chars_per_chunk:
    #             # For Chinese, join without spaces; for others, join with spaces
    #             chunk = ''.join(current_chunk) if is_chinese else ' '.join(current_chunk)
    #             chunks.append(chunk)
    #             current_chunk = []
    #             current_length = 0
            
    #         current_chunk.append(sent)
    #         current_length += sent_length
        
    #     # Add any remaining chunks
    #     if current_chunk:
    #         chunk = ''.join(current_chunk) if is_chinese else ' '.join(current_chunk)
    #         chunks.append(chunk)
        
    #     # Create segments from chunks
    #     if not chunks:
    #         return []
            
    #     chunk_duration = total_duration / len(chunks)
    #     segments = []
        
    #     for i, chunk in enumerate(chunks):
    #         chunk_start = start + i * chunk_duration
    #         chunk_end = start + (i + 1) * chunk_duration if i < len(chunks) - 1 else end
            
    #         # Clean and format the text
    #         cleaned_text = self._clean_final_subtitle_text(chunk)
    #         if not cleaned_text:
    #             continue
                
    #         segments.append({
    #             'text': cleaned_text,
    #             'start': chunk_start,
    #             'end': chunk_end
    #         })
        
    #     return segments

    # def _build_final_segments_from_path(self, alignment_path: List[Tuple[int, int]], 
    #                                  original_segs: List[Dict], 
    #                                  translated_sents: List[str], 
    #                                  target_lang: str,
    #                                  config: AlignmentConfig) -> List[Dict]:
    #     """Builds final subtitle segments from the alignment path.
        
    #     Args:
    #         alignment_path: List of (source_idx, target_idx) alignment pairs
    #         original_segs: Original segments with timestamps
    #         translated_sents: List of translated sentences
    #         target_lang: Target language code
    #         config: Alignment configuration
            
    #     Returns:
    #         List of subtitle segments with text and timing
    #     """
    #     if not alignment_path or not original_segs or not translated_sents:
    #         return []
        
    #     final_segments = []
    #     path_with_boundaries = [(-1, -1)] + alignment_path + [(len(original_segs), len(translated_sents))]

    #     for k in range(len(path_with_boundaries) - 1):
    #         start_orig_idx, start_trans_idx = path_with_boundaries[k]
    #         end_orig_idx, end_trans_idx = path_with_boundaries[k+1]
            
    #         # Get the groups of original and translated segments
    #         orig_group = original_segs[start_orig_idx + 1 : end_orig_idx + 1]
    #         trans_group = translated_sents[start_trans_idx + 1 : end_trans_idx + 1]

    #         if not orig_group or not trans_group:
    #             continue

    #         # Join translated segments with appropriate connector
    #         connector = "" if target_lang.startswith(('zh', 'ja', 'ko')) else " "
    #         merged_text = connector.join(trans_group).strip()
            
    #         if not merged_text:
    #             continue
                
    #         # Get timing from original segments
    #         start_time = orig_group[0]['start']
    #         end_time = orig_group[-1]['end']
            
    #         # Calculate duration and check if we need to split
    #         duration = end_time - start_time
            
    #         # If duration is too long or text is too long, split it
    #         if (duration > config.max_segment_duration or 
    #             len(merged_text) > (duration * config.max_chars_per_second)):
    #             segments = self._split_and_format_merged_text(
    #                 merged_text, start_time, end_time, config, target_lang
    #             )
    #             final_segments.extend(segments)
    #         else:
    #             # Clean and add as single segment
    #             cleaned_text = self._clean_subtitle_text(merged_text)
    #             if cleaned_text:
    #                 final_segments.append({
    #                     'text': cleaned_text,
    #                     'start': start_time,
    #                     'end': end_time
    #                 })
        
    #     return final_segments
        
    # def align_translation_semantically(self, translated_text: str, 
    #                                  word_timestamps_df: pd.DataFrame, 
    #                                  source_lang: str, 
    #                                  target_lang: str, 
    #                                  config: AlignmentConfig) -> List[Dict]:
    #     """Orchestrates the semantic alignment process.
        
    #     This method aligns translated text segments with the original timing information
    #     using semantic similarity. It handles the full pipeline from text segmentation
    #     to final subtitle generation.
        
    #     Args:
    #         translated_text: The full translated text to align
    #         word_timestamps_df: DataFrame containing word-level timestamps
    #         source_lang: Source language code (e.g., 'en')
    #         target_lang: Target language code (e.g., 'zh')
    #         config: Alignment configuration parameters
            
    #     Returns:
    #         List of aligned subtitle segments with timing information
    #     """
    #     logger.info(f"[Semantic Alignment] Starting alignment from {source_lang} -> {target_lang}")
        
    #     try:
    #         # Generate original segments with timestamps
    #         original_segments = self._generate_original_segments_with_timestamps(word_timestamps_df, source_lang)
    #         logger.info(f"[Semantic Alignment] Generated {len(original_segments)} original segments")
            
    #         if not original_segments:
    #             logger.error("[Semantic Alignment] No original segments generated from word timestamps")
    #             return []
            
    #         # Clean and preprocess the translated text
    #         cleaned_text = self._clean_subtitle_text(translated_text)
    #         if not cleaned_text:
    #             logger.error("[Semantic Alignment] No valid text after cleaning")
    #             return []
            
    #         # Segment the translated text
    #         translated_sentences = self._segment_text_naturally(cleaned_text, target_lang)
    #         logger.info(f"[Semantic Alignment] Segmented translation into {len(translated_sentences)} sentences")
            
    #         if not translated_sentences:
    #             logger.error("[Semantic Alignment] No translated sentences generated from text")
    #             return []
            
    #         # Get sentence embeddings
    #         logger.debug("[Semantic Alignment] Generating sentence embeddings...")
    #         model = self._get_st_model(config.model_name)
            
    #         # Clean source texts for better embedding quality
    #         source_texts = [self._clean_subtitle_text(s['text']) for s in original_segments]
    #         source_texts = [t for t in source_texts if t]  # Remove any empty segments
            
    #         if not source_texts:
    #             logger.error("[Semantic Alignment] No valid source texts after cleaning")
    #             return []
            
    #         logger.debug(f"[Semantic Alignment] Source text samples: {source_texts[:3]}...")
    #         logger.debug(f"[Semantic Alignment] Translation samples: {translated_sentences[:3]}...")
            
    #         # Get embeddings for both source and target
    #         source_embeddings = self._get_sentence_embeddings(source_texts, model)
    #         target_embeddings = self._get_sentence_embeddings(translated_sentences, model)
            
    #         # Calculate similarity and find alignment
    #         logger.debug("[Semantic Alignment] Calculating similarity matrix...")
    #         similarity_matrix = self._calculate_similarity_matrix(source_embeddings, target_embeddings)
            
    #         logger.debug("[Semantic Alignment] Finding optimal alignment path...")
    #         alignment_path = self._find_optimal_alignment(similarity_matrix, config)
            
    #         # Log alignment statistics
    #         if alignment_path:
    #             logger.info(f"[Semantic Alignment] Found alignment path with {len(alignment_path)} segments")
    #         else:
    #             logger.warning("[Semantic Alignment] Empty alignment path generated, using fallback")
    #             # Fallback to 1:1 alignment if no path found
    #             min_len = min(len(source_texts), len(translated_sentences))
    #             alignment_path = [(i, i) for i in range(min_len)]
            
    #         # Build final segments with the alignment path
    #         final_segments = self._build_final_segments_from_path(
    #             alignment_path, 
    #             original_segments, 
    #             translated_sentences, 
    #             target_lang,
    #             config
    #         )
            
    #         # Apply final cleaning to all segments
    #         for segment in final_segments:
    #             if 'text' in segment:
    #                 segment['text'] = self._clean_final_subtitle_text(segment['text'])
            
    #         # Remove any empty segments that might have been created during cleaning
    #         final_segments = [s for s in final_segments if s.get('text')]
            
    #         logger.info(f"[Semantic Alignment] Built {len(final_segments)} final segments")
    #         return final_segments
            
    #     except Exception as e:
    #         logger.error(f"[Semantic Alignment] Error during alignment: {str(e)}")
    #         logger.error(traceback.format_exc())
    #         return []
        
    #     return final_segments

    # --- 3. Heuristic Alignment and Text Segmentation ---

    def _clean_subtitle_text(self, text: str) -> str:
        """Clean up subtitle text for display.
        
        This is a lighter cleaning pass that preserves more of the original
        formatting and punctuation for further processing.
        
        Args:
            text: The text to clean
            
        Returns:
            Partially cleaned text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 1. Remove control characters except newlines
        cleaned = re.sub(r'[\x00-\x09\x0b-\x1f\x7f-\x9f]', '', text)
        
        # 2. Normalize whitespace (but preserve newlines)
        cleaned = re.sub(r'[\t\r\f\v]+', ' ', cleaned)  # Convert all whitespace to space except newline
        cleaned = re.sub(r' +', ' ', cleaned)  # Collapse multiple spaces
        
        # 3. Clean up leading/trailing whitespace
        cleaned = cleaned.strip()
        
        # 4. Remove unwanted leading punctuation (but preserve quotes, brackets, etc.)
        cleaned = re.sub(r'^[\s\.,;:。，；：\-\*\_\[\]\(\)"\'\`]+', '', cleaned)
        
        # 5. Ensure proper spacing around certain punctuation in non-CJK text
        cleaned = re.sub(r'([a-zA-Z])([,.!?])([^\d\s])', r'\1\2 \3', cleaned)
        
        return cleaned.strip()
    
    def _clean_final_subtitle_text(self, text: str) -> str:
        """Perform final cleanup on subtitle text before output to SRT.
        
        This is a more aggressive cleaning step that should be applied right before
        generating the final SRT output. Handles both English and Chinese text.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text ready for SRT output
        """
        if not text or not isinstance(text, str):
            return ""
            
        # 1. Apply standard cleaning first
        cleaned = self._clean_subtitle_text(text)
        
        try:
            # 2. Remove any remaining control characters
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
            
            # 3. Normalize quotes and other common issues
            cleaned = (
                cleaned.replace('"', '"')
                      .replace('\u201c', '"')
                      .replace('\u201d', '"')
                      .replace('''\u2018''', "'")
                      .replace('\u2019', "'")
            )
            
            # 4. Handle Chinese-specific formatting
            # Remove spaces between Chinese characters and Chinese punctuation
            cleaned = re.sub(r'([\u4e00-\u9fff])\s+([，。！？])', r'\1\2', cleaned)
            cleaned = re.sub(r'([，。！？])\s+([\u4e00-\u9fff])', r'\1\2', cleaned)
            
            # 5. Fix common spacing issues with parentheses and brackets
            # For Chinese text, no space after opening or before closing brackets
            cleaned = re.sub(r'([（【])\s+', r'\1', cleaned)  # No space after Chinese opening brackets
            cleaned = re.sub(r'\s+([）】])', r'\1', cleaned)  # No space before Chinese closing brackets
            
            # For English text
            cleaned = re.sub(r'\s+([.,;:!?])', r'\1', cleaned)  # Remove space before punctuation
            cleaned = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', cleaned)  # Add space after sentence end
            
            # 6. Fix multiple spaces and clean up
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            # 7. Fix spacing with quotes and brackets (only do this once)
            cleaned = re.sub(r'"\s+([^\s])', r'"\1', cleaned)  # Remove space after opening quote
            cleaned = re.sub(r'([^\s])\s+"', r'\1"', cleaned)  # Remove space before closing quote
            cleaned = re.sub(r'\(\s+', '(', cleaned)  # Remove space after opening bracket
            cleaned = re.sub(r'\s+\)', ')', cleaned)  # Remove space before closing bracket
            
            # 8. Remove any remaining leading/trailing punctuation/whitespace
            cleaned = re.sub(r'^[\s\.,;:!?]+', '', cleaned)
            cleaned = re.sub(r'[\s\.,;:!?]+$', '', cleaned)
            
        except re.error as e:
            # If regex error occurs, log the error and return the text as is
            logger.error(f"Regex error during final text cleaning: {e}. Problematic text: '{text}'")
            return text.strip()
        
        return cleaned.strip()
        
    def _segment_text_naturally(self, text: str, lang_code: str) -> List[str]:
        """Segments text into sentences using pysbd with a regex fallback."""
        if not text or not text.strip(): 
            return []
        
        # Handle 'auto' language code by defaulting to 'en'
        if not lang_code or lang_code.lower() == 'auto':
            logger.warning("Received 'auto' as lang_code, defaulting to 'en' for segmentation.")
            lang_code = 'en'
        
        # Normalize language code for pysbd
        lang_map = {'zh': 'zh', 'en': 'en', 'ja': 'ja', 'ko': 'ko', 'es': 'es', 'fr': 'fr', 'de': 'de', 'ru': 'ru'}
        lang = lang_map.get(lang_code.lower().split('-')[0], 'en')
            
        # try:
        #     segmenter = pysbd.Segmenter(language=lang, clean=False)
        #     return segmenter.segment(text)
        # except Exception:
        #     logger.warning(f"pysbd failed for lang '{lang}'. Falling back to regex.")
        return [s.strip() for s in re.split(r'(?<=[.!?。！？])\s*', text) if s.strip()]
            
    def _generate_original_segments_with_timestamps(
        self,
        word_timestamps_df: pd.DataFrame,
        lang_code: str
    ) -> List[Dict[str, Any]]:
        """
        Creates timestamped text segments from word-level data using regex-based segmentation.
        """
        if word_timestamps_df.empty:
            return []

        # 1. Get full text and all words
        all_words = word_timestamps_df['word'].tolist()
        full_text = " ".join(str(w) for w in all_words if w)

        # 2. Use regex for natural sentence segmentation
        natural_segments_text = self._segment_text_naturally(full_text, lang_code)
        if not natural_segments_text:
            # If segmentation fails, treat the entire text as one segment
            natural_segments_text = [full_text]

        final_segments = []
        word_cursor = 0  # Track our position in the all_words list

        # 3. Map the segmented text back to words and timestamps
        for text_seg in natural_segments_text:
            text_seg = text_seg.strip()
            if not text_seg:
                continue
            
            # Get the number of words in this segment
            # Note: The .split() here must match how we joined full_text above
            num_words_in_seg = len(text_seg.split())
            
            if num_words_in_seg == 0:
                continue
                
            # Determine the range in word_timestamps_df that this text segment corresponds to
            start_idx = word_cursor
            end_idx = word_cursor + num_words_in_seg
            
            # Prevent index out of bounds
            if start_idx >= len(word_timestamps_df):
                break
            end_idx = min(end_idx, len(word_timestamps_df))

            # Extract the corresponding DataFrame subset
            segment_df = word_timestamps_df.iloc[start_idx:end_idx]

            if not segment_df.empty:
                # Create a segment with timestamps from the first word's start to the last word's end
                final_segments.append({
                    'text': " ".join(str(w) for w in segment_df['word'] if w),
                    'start': segment_df.iloc[0]['start'],
                    'end': segment_df.iloc[-1]['end']
                })
            
            # Update cursor position for the next segment
            word_cursor = end_idx
                
        return final_segments

    def _reconcile_segments(self, segments: List[str], target_count: int, target_lang: str) -> List[str]:
        """Adjusts segment count by merging or splitting based on length."""
        # Merge shortest adjacent segments
        while len(segments) > target_count and len(segments) > 1:
            lengths = [len(s) for s in segments]
            merge_idx = np.argmin([lengths[i] + lengths[i+1] for i in range(len(lengths)-1)])
            connector = "" if target_lang.startswith(('zh','ja','ko')) else " "
            segments[merge_idx] = segments[merge_idx] + connector + segments.pop(merge_idx+1)
        
        # Split longest segments
        while len(segments) < target_count and segments:
            longest_idx = np.argmax([len(s) for s in segments])
            segment_to_split = segments.pop(longest_idx)
            mid = len(segment_to_split) // 2
            part1 = segment_to_split[:mid].strip()
            part2 = segment_to_split[mid:].strip()
            if part1 and part2:
                segments.insert(longest_idx, part1)
                segments.insert(longest_idx, part2)
            else:
                segments.insert(longest_idx, segment_to_split) # Put it back if split fails
                break # Avoid infinite loop
        return segments

    def align_translation_heuristically(self, translated_text, word_timestamps_df, source_lang, target_lang) -> List[Dict]:
        """Orchestrates the heuristic (length-based) alignment process."""
        logger.info(f"Starting heuristic alignment for {source_lang} -> {target_lang}")

        original_segments = self._generate_original_segments_with_timestamps(word_timestamps_df, source_lang)
        translated_segments = self._segment_text_naturally(translated_text, target_lang)
        
        if not original_segments or not translated_segments: return []

        reconciled_segments = self._reconcile_segments(translated_segments, len(original_segments), target_lang)
        
        final_segments = []
        for orig_seg, trans_text in zip(original_segments, reconciled_segments):
            # Clean up the text before adding to final segments
            cleaned_text = self._clean_subtitle_text(trans_text.strip())
            
            if cleaned_text:  # Only add non-empty segments
                final_segments.append({
                    'text': cleaned_text,
                    'start': orig_seg['start'],
                    'end': orig_seg['end']
                })
        return final_segments

    # --- 4. Public API and Main Entry Points ---

    def align_translation_with_original_rhythm(self, translated_text, word_timestamps_df, source_lang, target_lang, 
                                               alignment_strategy, alignment_config) -> List[Dict]:
        """Dispatches to the correct alignment strategy."""
        # Force heuristic alignment to remove torch dependency
        logger.info(f"Aligning with original rhythm using 'heuristic' strategy (forced).")
        
        return self.align_translation_heuristically(translated_text, word_timestamps_df, source_lang, target_lang)

    def align_translation_to_timeline(self, translated_text: str, word_timestamps_df: pd.DataFrame,
                                      source_language: str, target_language: str,
                                      alignment_strategy: Union[str, AlignmentStrategy] = AlignmentStrategy.SEMANTIC,
                                      alignment_config: Optional[AlignmentConfig] = None) -> pd.DataFrame:
        """
        Main public method to align translated text to a timeline.
        
        Args:
            translated_text: The full translated text.
            word_timestamps_df: DataFrame with original word-level timestamps.
            source_language: The source language code (e.g., 'en').
            target_language: The target language code (e.g., 'zh').
            alignment_strategy: The strategy to use ('semantic' or 'heuristic').
            alignment_config: Custom configuration for alignment.

        Returns:
            A pandas DataFrame with 'start', 'end', 'text' columns for the aligned subtitles.
            Returns an empty DataFrame on failure.
        """
        logger.info(f"Received alignment request for {source_language}->{target_language} using {alignment_strategy} strategy.")
        
        try:
            if word_timestamps_df is None or word_timestamps_df.empty: raise ValueError("Word timestamps DataFrame is missing.")
            if not translated_text or not translated_text.strip(): raise ValueError("Translated text is empty.")
            
            if isinstance(alignment_strategy, str):
                alignment_strategy = AlignmentStrategy(alignment_strategy.lower())
            
            config = alignment_config or self.default_alignment_config

            subtitles = self.align_translation_with_original_rhythm(
                translated_text=translated_text,
                word_timestamps_df=word_timestamps_df,
                source_lang=source_language,
                target_lang=target_language,
                alignment_strategy=alignment_strategy,
                alignment_config=config
            )
            
            if not subtitles:
                logger.warning("Alignment process produced no subtitles.")
                return pd.DataFrame(columns=['start', 'end', 'text'])
                
            return pd.DataFrame(subtitles)
            
        except Exception as e:
            logger.error(f"Timeline alignment failed for language '{target_language}': {e}", exc_info=True)
            return pd.DataFrame(columns=['start', 'end', 'text'])


    def generate_srt_from_dataframe(self, subtitles_df: pd.DataFrame, output_path: Optional[str] = None, split_sentences: bool = False) -> str:
        """
        Generates an SRT formatted string or file from a subtitles DataFrame.
        
        Args:
            subtitles_df: DataFrame containing subtitle data with 'start', 'end', and text columns
            output_path: Optional path to save the SRT file
            split_sentences: Whether to split segments into sentence-level subtitles (default: False)
            
        Returns:
            SRT formatted string
        """
        if subtitles_df.empty: 
            return ""
            
        srt_content = generate_srt_content(subtitles_df, split_sentences=split_sentences)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            logger.info(f"Saved SRT file to {output_path}")
            
        return srt_content
        
    def generate_srt_from_original_segments(self, segments: List[Dict], output_path: Optional[str] = None) -> str:
        """
        Generates an SRT formatted string or file from a list of original segments.
        This is typically used for the source language subtitles.
        
        Args:
            segments: List of segment dictionaries with 'start', 'end', and 'text' keys
            output_path: Optional path to save the SRT file
            
        Returns:
            SRT formatted string
        """
        if not segments:
            logger.warning("generate_srt_from_original_segments received an empty list.")
            return ""
        
        # Create a DataFrame from the segments
        df = pd.DataFrame(segments)
        
        # Ensure required columns exist
        required_columns = ['start', 'end', 'text']
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Missing required column '{col}' in segments")
                return ""
        
        # Use the existing method to generate SRT
        return self.generate_srt_from_dataframe(df, output_path)