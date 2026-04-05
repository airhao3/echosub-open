"""
Utility functions for the transcription module.
Contains helper functions for file handling, result processing, etc.
"""

import os
import sys
import json
import logging
import traceback
import re
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union, Tuple
from datetime import timedelta, datetime
# nltk removed - not used in current implementation
# from app.services.subtitle.alignment import generate_srt_content  # Imported but never used
from app.utils.file_path_manager import get_file_path_manager, FileType
from app.models.job_context import JobContext

# spaCy functionality removed - not used in current implementation
has_spacy = False

# Configure logger
logger = logging.getLogger(__name__)
class TranscriptionUtils:
    """Utility functions for transcription processing."""

    # Configurable splitting parameters (can be overridden via user preferences)
    split_trigger_duration: float = 2.5
    split_trigger_words: int = 8
    pause_split_threshold: float = 0.3
    max_words_per_segment: int = 7
    split_on_comma: bool = True

    def configure(self, preferences: dict):
        """Apply user processing preferences."""
        self.split_trigger_duration = preferences.get('split_trigger_duration', 2.5)
        self.split_trigger_words = preferences.get('split_trigger_words', 8)
        self.pause_split_threshold = preferences.get('pause_split_threshold', 0.3)
        self.max_words_per_segment = preferences.get('max_words_per_segment', 7)
        self.split_on_comma = preferences.get('split_on_comma', True)
        logger.info(f"TranscriptionUtils configured: duration={self.split_trigger_duration}s, "
                     f"words={self.split_trigger_words}, pause={self.pause_split_threshold}s, "
                     f"max_words={self.max_words_per_segment}, comma_split={self.split_on_comma}")

    def process_long_sentences(self, results: List[Dict]) -> List[Dict]:
        """
        Process and split long sentences for better subtitle display with improved dialogue handling.
        
        Enhanced to better handle conversations by:
        1. Detecting dialogue patterns
        2. Better handling of short interjections
        3. Improved segmentation based on speech patterns
        
        Args:
            results: List of transcription results from WhisperX
            
        Returns:
            Processed results with improved segmentation for dialogue
        """
        logger.info("Processing segments with enhanced dialogue handling")
        processed_results = []
        
        for result in results:
            if not isinstance(result, dict) or 'segments' not in result:
                processed_results.append(result)
                continue
                
            processed_segments = []
            original_segments = result['segments']
            
            for segment in original_segments:
                duration = segment.get('end', 0) - segment.get('start', 0)
                text = segment.get('text', '').strip()
                words = segment.get('words', [])
                word_count = len(text.split())
                
                # Skip empty segments or segments without word-level timing
                if not text or not words:
                    processed_segments.append(segment)
                    continue
                
                # Enhanced segmentation for dialogue
                if self._is_dialogue_segment(text):
                    processed_segments.extend(self._process_dialogue_segment(segment))
                    continue
                    
                # Standard segmentation for regular text
                if duration > self.split_trigger_duration or word_count > self.split_trigger_words:
                    processed_segments.extend(self._split_segment(segment))
                else:
                    processed_segments.append(segment)
            
            # Final cleanup and validation
            processed_segments = self._cleanup_segments(processed_segments)
            
            processed_result = result.copy()
            processed_result['segments'] = processed_segments
            processed_results.append(processed_result)
            
            logger.info(f"Processed {len(original_segments)} segments into {len(processed_segments)} segments")
            
        return processed_results
        
    @staticmethod
    def _is_dialogue_segment(text: str) -> bool:
        """Check if a segment appears to be dialogue."""
        # Check for common dialogue patterns
        dialogue_indicators = [
            'I ', 'you ', 'we ', 'they ', 'he ', 'she ', 'it ',
            'me ', 'my ', 'your ', 'our ', 'their ', 'his ', 'her ',
            '?', '!', '...', ' - ', '—', '... ', '...\n', '\n',
        ]
        return any(indicator in text.lower() for indicator in dialogue_indicators)
        
    @staticmethod
    def _process_dialogue_segment(segment: Dict) -> List[Dict]:
        """Process a segment that appears to be dialogue."""
        words = segment.get('words', [])
        if not words:
            return [segment]
            
        segments = []
        current_segment = []
        
        for i, word in enumerate(words):
            word_text = word.get('word', '').strip()
            current_segment.append(word)
            
            # Split on punctuation that often ends dialogue turns
            if word_text and word_text[-1] in ['.', '?', '!', '...']:
                if len(current_segment) > 2:  # Don't create too short segments
                    segments.append(current_segment)
                    current_segment = []
        
        # Add any remaining words
        if current_segment:
            segments.append(current_segment)
        
        # Convert word lists back to segment format
        result_segments = []
        for i, seg_words in enumerate(segments):
            if not seg_words:
                continue
                
            first_word = seg_words[0]
            last_word = seg_words[-1]
            
            new_segment = {
                'id': f"{segment.get('id', 0)}.{i}",
                'start': first_word.get('start', 0),
                'end': last_word.get('end', 0),
                'text': ' '.join(w.get('word', '').strip() for w in seg_words),
                'words': seg_words.copy()
            }
            
            # Ensure minimum duration (0.8s for dialogue)
            if new_segment['end'] - new_segment['start'] < 0.8:
                new_segment['end'] = new_segment['start'] + 0.8
                
            result_segments.append(new_segment)
            
        return result_segments or [segment]
        
    def _split_segment(self, segment: Dict) -> List[Dict]:
        """Split a long segment into smaller chunks."""
        words = segment.get('words', [])
        if not words:
            return [segment]

        split_punctuation = ['.', '?', '!', '...']
        if self.split_on_comma:
            split_punctuation.append(',')

        segments = []
        current_segment = []
        last_end_time = words[0].get('start', 0)

        for word in words:
            word_text = word.get('word', '').strip()
            word_start = word.get('start', 0)

            # Check for natural break points
            should_split = (
                word_start - last_end_time > self.pause_split_threshold or
                (word_text and word_text[-1] in split_punctuation) or
                len(current_segment) >= self.max_words_per_segment
            )
            
            if should_split and current_segment:
                segments.append(current_segment)
                current_segment = []
                
            current_segment.append(word)
            last_end_time = word.get('end', 0)
        
        if current_segment:
            segments.append(current_segment)
            
        # Convert to segment format
        return [
            {
                'id': f"{segment.get('id', 0)}.{i}",
                'start': seg[0].get('start', 0),
                'end': seg[-1].get('end', 0),
                'text': ' '.join(w.get('word', '').strip() for w in seg),
                'words': seg.copy()
            }
            for i, seg in enumerate(segments)
        ]
        
    @staticmethod
    def _cleanup_segments(segments: List[Dict]) -> List[Dict]:
        """Clean up and validate segments after processing."""
        if not segments:
            return []
            
        # Sort by start time
        segments = sorted(segments, key=lambda x: x.get('start', 0))
        
        # Ensure no overlaps and minimum durations
        for i in range(1, len(segments)):
            prev_end = segments[i-1].get('end', 0)
            curr_start = segments[i].get('start', 0)
            
            if curr_start < prev_end:
                # Add small gap between segments
                gap = (prev_end - curr_start) / 2
                segments[i-1]['end'] = prev_end - gap
                segments[i]['start'] = curr_start + gap
                
            # Ensure minimum duration
            duration = segments[i]['end'] - segments[i]['start']
            if duration < 0.8:  # Slightly shorter min duration for dialogue
                segments[i]['end'] = segments[i]['start'] + 0.8
                
        return segments
    
    @staticmethod
    def save_transcription_results(results: List[Dict], context: JobContext) -> str:
        """
        Save transcription results to standard locations.
        This function is now simplified to only save the raw transcription JSON and TXT.
        Labeled transcripts and cleaned chunks are handled by the segmentation module.

        Args:
            results: List of transcription results from WhisperX
            context: JobContext containing user_id and job_id for file operations

        Returns:
            Path to the saved transcription JSON file
        """
        # Log information about results for debugging
        logger.info(f"Processing transcription results: {len(results)} result sets")
        
        # First, process long sentences to improve subtitle segmentation
        utils_instance = TranscriptionUtils()
        # Load user processing preferences if available
        try:
            from app.core.database import SessionLocal
            from app.models.user import User
            db = SessionLocal()
            user = db.query(User).filter(User.id == context.user_id).first()
            if user and user.processing_preferences:
                utils_instance.configure(user.processing_preferences)
            db.close()
        except Exception as e:
            logger.warning(f"Could not load user preferences: {e}")
        processed_results = utils_instance.process_long_sentences(results)
        logger.info(f"Processed long sentences: {len(processed_results)} result sets")
        
        # Consolidate all segments from all results
        all_segments = []
        for i, result in enumerate(processed_results):
            logger.info(f"Processing result set {i+1}: {type(result)}")
            if isinstance(result, dict) and 'segments' in result:
                segments = result['segments']
                logger.info(f"  - Contains {len(segments)} segments")
                
                # Log if word-level timestamps are available
                if segments and 'words' in segments[0] and segments[0]['words']:
                    logger.info(f"  - Word-level timestamps available: {len(segments[0]['words'])} words in first segment")
                
                all_segments.extend(segments)
            else:
                logger.warning(f"  - Invalid result format: {type(result)}. Expected dict with 'segments'.")
                # If it's the raw result and not a dict, try to handle it
                if isinstance(result, dict):
                    logger.info(f"  - Keys in result: {list(result.keys())}")
        
        logger.info(f"Total segments collected: {len(all_segments)}")
        
        # If no valid segments, log an informative error message
        if len(all_segments) == 0:
            logger.warning("No valid transcription segments found - output will contain error information")
            all_segments.append({
                'start': 0.0,
                'end': 1.0,
                'text': '[Error: No valid transcription segments were produced]',
                'words': []
            })
        
        # Sort segments by start time
        all_segments.sort(key=lambda x: x.get('start', 0))
        
        # Split long segments into smaller chunks for better readability and timing
        all_segments = TranscriptionUtils.split_long_segments(all_segments)
        
        # Get file path manager instance
        file_manager = get_file_path_manager()
        
        # Save the original segments with word timing (transcription.json)
        segments_json_path = file_manager.get_file_path(context, FileType.TRANSCRIPTION_JSON)
        try:
            os.makedirs(os.path.dirname(segments_json_path), exist_ok=True)
            with open(segments_json_path, 'w', encoding='utf-8') as f:
                json.dump(all_segments, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved original segments with word timing: {segments_json_path}")
            
        except Exception as json_e:
            logger.error(f"Error saving original segments: {str(json_e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Do not re-raise, allow other files to be saved if possible

        # Create a simple text transcript (transcription.txt)
        log_transcript_path = file_manager.get_file_path(context, FileType.TRANSCRIPTION_TXT)
        try:
            os.makedirs(os.path.dirname(log_transcript_path), exist_ok=True)
            with open(log_transcript_path, 'w', encoding='utf-8') as f:
                for segment in all_segments:
                    text = segment.get('text', '').strip()
                    if text:  # Only write non-empty lines
                        f.write(f"{text}\n")
            logger.info(f"Saved simple text transcript: {log_transcript_path}")
        except Exception as e:
            logger.error(f"Error saving text transcript: {str(e)}")
        

        return segments_json_path
                    
    @staticmethod
    def split_by_connectors(text: str, nlp=None) -> List[str]:
        """
        Split text by conjunctions and connector words.
        
        This function looks for transition and connector words that indicate
        a logical break in the text, enabling more natural sentence segmentation.
        
        Args:
            text: Text to be split
            nlp: Optional spaCy NLP model (if None, falls back to simple regex)
            
        Returns:
            List of text segments split at logical connector points
        """
        # Skip short text
        if len(text) < 40:
            return [text]
            
        # English connectors that indicate topic transitions or logical breaks
        eng_connectors = ["and", "but", "or", "so", "because", "while", "although", "though", 
                      "however", "therefore", "thus", "hence", "consequently", "nevertheless",
                      "nonetheless", "yet", "still", "meanwhile", "thereafter", "furthermore",
                      "moreover", "since", "unless", "if", "when", "where", "after", "before"]
                      
        # Chinese connectors
        chn_connectors = ["但是", "然而", "不过", "可是", "而且", "因此", "所以", "因为", "由于",
                       "如果", "虽然", "尽管", "即使", "无论", "只要", "只有", "除非", "为了"]
        
        # Try to use spaCy if available
        if nlp:
            try:
                doc = nlp(text)
                parts = []
                start_idx = 0
                
                for token in doc:
                    if token.text.lower() in eng_connectors and token.i > 3 and token.i < len(doc) - 4:
                        # Check if this is a good split point (not too close to the start/end)
                        parts.append(text[start_idx:token.idx].strip())
                        start_idx = token.idx
                
                # Add the last part
                if start_idx < len(text):
                    parts.append(text[start_idx:].strip())
                    
                # Use the parts if they make sense, otherwise keep original
                if len(parts) > 1 and all(len(p) > 15 for p in parts):
                    return parts
            except Exception as e:
                logger.warning(f"Error in spaCy connector splitting: {str(e)}. Using fallback.")
        
        # Fallback: Simple regex-based approach for Chinese connectors
        result = [text]
        for connector in chn_connectors:
            new_result = []
            for segment in result:
                if connector in segment and len(segment) > 40:
                    idx = segment.find(connector)
                    if idx > 15 and idx < len(segment) - 20:  # Ensure not at edges
                        new_result.append(segment[:idx].strip())
                        new_result.append(segment[idx:].strip())
                    else:
                        new_result.append(segment)
                else:
                    new_result.append(segment)
            result = new_result
            
        return result
        
    @staticmethod
    def split_long_segments(segments: List[Dict]) -> List[Dict]:
        """
        Split long segments into smaller chunks based on word timing and punctuation.
        
        This function identifies long segments (by duration or word count) and splits them
        into more manageable chunks based on natural pauses and punctuation, improving
        readability and timing accuracy for subtitles.
        
        Args:
            segments: List of transcription segments from WhisperX with word-level timing
            
        Returns:
            List of segments split into smaller, optimized chunks
        """
        # If no segments or empty segments, return as is
        if not segments:
            return segments
        
        # Check if we have word-level timestamps - if not, can't split effectively
        if not all('words' in segment and segment['words'] for segment in segments):
            logger.warning("Word-level timestamps missing in some segments - cannot split long segments")
            return segments
        
        result_segments = []
        
        # Define segment length thresholds
        MAX_DURATION_SECONDS = 5.0
        MAX_WORD_COUNT = 10
        WORD_GAP_THRESHOLD = 0.5  # Minimum pause between words to consider a natural break
        IDEAL_MIN_WORDS = 8  # Min words in a segment (ideal case)
        IDEAL_MAX_WORDS = 18  # Max words in a segment (ideal case)
        MIN_SEGMENT_DURATION = 1.0  # Minimum duration for a segment in seconds
        
        # Regular expression for punctuation that indicates natural pauses
        PAUSE_PUNCTUATION = re.compile(r'[,.?!…]$')
        
        for segment in segments:
            # Skip segments without words
            if 'words' not in segment or not segment['words']:
                result_segments.append(segment)
                continue
                
            # Check if this is a long segment that needs splitting
            duration = segment.get('end', 0) - segment.get('start', 0)
            word_count = len(segment['words'])
            
            # If segment is short enough, keep it as is
            if duration <= MAX_DURATION_SECONDS and word_count <= MAX_WORD_COUNT:
                result_segments.append(segment)
                continue
                
            # Segment needs splitting - prepare for splitting logic
            words = segment['words']
            subsegments = []
            current_words = []
            
            # Track the last potential split point
            last_split_idx = 0
            
            for i in range(len(words)):
                current_words.append(words[i])
                
                # Determine if this is a good place to split:
                # 1. Natural pause (gap between this word and next)
                # 2. Punctuation indicating a pause
                # 3. Reaching ideal max word count
                
                is_last_word = (i == len(words) - 1)
                has_punctuation = bool(PAUSE_PUNCTUATION.search(words[i].get('word', '')))
                
                # Check time gap with next word (if not last word)
                has_pause = False
                if not is_last_word and i < len(words) - 1:
                    current_end = words[i].get('end', words[i].get('start', 0))
                    next_start = words[i+1].get('start', words[i+1].get('end', 0))
                    word_gap = next_start - current_end
                    has_pause = (word_gap >= WORD_GAP_THRESHOLD)
                
                # Decide if we should split here
                should_split = (
                    is_last_word or 
                    has_punctuation or 
                    has_pause or 
                    (len(current_words) >= IDEAL_MAX_WORDS)
                )
                
                # Only split if we have enough words (unless it's the last word or has punctuation)
                reached_min_words = len(current_words) >= IDEAL_MIN_WORDS
                if should_split and (reached_min_words or is_last_word or has_punctuation or has_pause):
                    # Create a new subsegment
                    if current_words:
                        # Get timing from word timestamps
                        start_time = current_words[0].get('start', segment.get('start', 0))
                        end_time = current_words[-1].get('end', segment.get('end', 0))
                        
                        # Skip segments that are too short
                        segment_duration = end_time - start_time
                        if segment_duration < MIN_SEGMENT_DURATION and len(subsegments) > 0 and not is_last_word:
                            # Add this word to the next segment instead
                            continue
                            
                        # Create text from the words
                        text = ' '.join(word.get('word', '') for word in current_words).strip()
                        
                        subsegment = {
                            'start': start_time,
                            'end': end_time,
                            'text': text,
                            'words': current_words.copy()  # Keep word-level timing for future processing
                        }
                        subsegments.append(subsegment)
                        
                        # Reset for next segment
                        current_words = []
                        last_split_idx = i + 1
            
            # If we have any remaining words, create a final subsegment
            if current_words and last_split_idx < len(words):
                start_time = current_words[0].get('start', segment.get('start', 0))
                end_time = current_words[-1].get('end', segment.get('end', 0))
                text = ' '.join(word.get('word', '') for word in current_words).strip()
                
                subsegment = {
                    'start': start_time,
                    'end': end_time,
                    'text': text,
                    'words': current_words.copy()
                }
                subsegments.append(subsegment)
            
            # Check for time overlaps and fix them with small offsets if needed
            for i in range(1, len(subsegments)):
                prev_end = subsegments[i-1]['end']
                curr_start = subsegments[i]['start']
                
                # If there's an overlap, shift the current segment start time slightly
                if curr_start < prev_end:
                    # Add a small 50ms offset to avoid exact overlap
                    subsegments[i]['start'] = prev_end + 0.05
            
            # If we created subsegments, add them all; otherwise, keep the original
            if subsegments:
                result_segments.extend(subsegments)
                logger.info(f"Split segment of {duration:.2f}s and {word_count} words into {len(subsegments)} subsegments")
            else:
                # spaCy-based connector splitting has been removed - not used in current implementation
                
                # If all else fails, keep the original segment
                result_segments.append(segment)
        
        return result_segments
    
    @staticmethod
    def log_error(error_message: str, context: Optional[JobContext] = None) -> str:
        """
        Log an error message and save it to a file for debugging.
        
        Args:
            error_message: Detailed error message explaining the issue
            context: JobContext for file operations (optional)
            
        Returns:
            Path to the error log file
        """
        logger.error(f"Transcription error: {error_message}")
        
        if context:
            try:
                # Get file path manager and create error log
                file_manager = get_file_path_manager()
                error_file = file_manager.get_file_path(context, FileType.JOB_LOG)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(error_file), exist_ok=True)
                
                # Create an error file with timestamp
                import time
                timestamp = int(time.time())
                error_file_timestamped = error_file.replace('.log', f'_error_{timestamp}.log')
                
                try:
                    with open(error_file_timestamped, 'w') as f:
                        f.write(f"Transcription Error: {error_message}\n")
                        f.write(traceback.format_exc())
                    logger.info(f"Error details written to {error_file_timestamped}")
                    return error_file_timestamped
                except Exception as e:
                    logger.error(f"Failed to write error to file: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to get error log path: {str(e)}")
        
        return ""
    
    @staticmethod
    def _generate_segmented_transcript(segments: List[Dict], context: JobContext, file_manager) -> None:
        """
        Generate segmented transcript in pure text format (like transcript.txt but with better segmentation).
        
        Args:
            segments: List of transcription segments
            context: JobContext containing user_id and job_id
            file_manager: FilePathManager instance
        """
        segmented_transcript_path = file_manager.get_file_path(context, FileType.SEGMENTED_TRANSCRIPT)
        try:
            os.makedirs(os.path.dirname(segmented_transcript_path), exist_ok=True)
            with open(segmented_transcript_path, 'w', encoding='utf-8') as f:
                for segment in segments:
                    text = segment.get('text', '').strip()
                    if text:  # Only write non-empty segments
                        f.write(f"{text}\n")
                        
            logger.info(f"Saved segmented transcript in pure text format: {segmented_transcript_path}")
            
        except Exception as e:
            logger.error(f"Error saving segmented transcript: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
   