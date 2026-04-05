import os
import pandas as pd
import numpy as np
import logging
import re
import json
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from difflib import SequenceMatcher
from pathlib import Path

from .utils import clean_text_for_matching, time_to_srt_format
# sentence_splitter functions have been moved to .unused - not used in current implementation

# Set up logger first
logger = logging.getLogger(__name__)

# ffsubsync functionality has been removed - using tag-based alignment instead
FFSUBSYNC_AVAILABLE = False


# align_with_ffsubsync function has been removed - using tag-based alignment instead

def adjust_subtitle_timing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adjust subtitle timing to ensure proper display and improved readability
    
    Enhanced version that optimizes timing for better viewing experience with:
    1. Content-aware duration calculation
    2. Smart gap handling between subtitles
    3. Improved synchronization with speech
    4. Better reading rhythm with natural pauses
    
    Args:
        df: DataFrame containing subtitle data with 'start', 'end', and 'text' columns
        
    Returns:
        DataFrame with adjusted timing
    """
    result_df = df.copy()
    
    # Columns to check
    text_cols = ['text']
    if 'translation' in result_df.columns:
        text_cols.append('translation')
    
    for i in range(len(result_df)):
        # Calculate optimal duration based on content length
        text = ""
        for col in text_cols:
            if col in result_df.columns and pd.notna(result_df.iloc[i][col]):
                text += " " + str(result_df.iloc[i][col])
        
        text = text.strip()
        if not text:
            continue
        
        # Calculate optimal duration based on content length and complexity
        word_count = len(text.split())
        char_count = len(text)
        
        # Basic formula: approximately 0.3s per word + 0.5s padding
        optimal_duration = (word_count * 0.3) + 0.5
        
        # Adjust for complex sentences (more characters per word indicates complexity)
        if word_count > 0:
            chars_per_word = char_count / word_count
            complexity_factor = min(2.0, max(1.0, chars_per_word / 5.0))  # Cap at 2x
            optimal_duration *= complexity_factor
        
        # Ensure reasonable duration bounds
        min_duration = 2.5  # Increased from 1.5 to 2.5 seconds minimum for better readability
        max_duration = min(8.0, word_count * 0.6 + 2.0)  # Slightly increased max duration
        
        current_duration = result_df.iloc[i]['end'] - result_df.iloc[i]['start']
        
        # Only extend if needed, don't shorten subtitles that are already long enough
        if current_duration < optimal_duration:
            new_duration = min(max_duration, max(min_duration, optimal_duration))
            result_df.loc[result_df.index[i], 'end'] = result_df.iloc[i]['start'] + new_duration
    
    # Now optimize gaps between subtitles
    for i in range(1, len(result_df)):
        prev_end = result_df.iloc[i-1]['end']
        curr_start = result_df.iloc[i]['start']
        
        # Avoid overlapping subtitles
        if curr_start < prev_end:
            # Add a small gap of 0.05 seconds
            result_df.loc[result_df.index[i], 'start'] = prev_end + 0.05
            
            # Ensure the subtitle still has sufficient duration
            min_duration = 1.5
            if result_df.iloc[i]['end'] - result_df.iloc[i]['start'] < min_duration:
                result_df.loc[result_df.index[i], 'end'] = result_df.iloc[i]['start'] + min_duration
        
        # If gap is large (> 2s), reduce it unless there's a natural pause
        elif curr_start - prev_end > 2.0:
            # Check if this is a scene change or paragraph break by seeing if both adjacent subtitles end/start with sentence-ending punctuation
            prev_text = ""
            curr_text = ""
            
            for col in text_cols:
                if col in result_df.columns:
                    if pd.notna(result_df.iloc[i-1][col]):
                        prev_text += " " + str(result_df.iloc[i-1][col])
                    if pd.notna(result_df.iloc[i][col]):
                        curr_text += " " + str(result_df.iloc[i][col])
            
            prev_text = prev_text.strip()
            curr_text = curr_text.strip()
            
            # Check if previous subtitle ends with sentence-ending punctuation and current starts with capital
            ends_with_punct = bool(re.search(r'[.!?]\s*$', prev_text))
            starts_with_capital = bool(re.search(r'^\s*[A-Z]', curr_text))
            
            # Keep the gap if it looks like a natural break
            if not (ends_with_punct and starts_with_capital):
                # Reduce gap while keeping a slight pause
                max_gap = 1.5
                result_df.loc[result_df.index[i], 'start'] = prev_end + max_gap
                
                # Adjust end time to maintain duration
                original_duration = result_df.iloc[i]['end'] - curr_start
                result_df.loc[result_df.index[i], 'end'] = result_df.iloc[i]['start'] + original_duration
    
    return result_df


def get_text_column(df: pd.DataFrame) -> Optional[str]:
    """
    Identify the text column in a DataFrame
    
    Args:
        df: Input DataFrame
        
    Returns:
        Name of the text column if found, None otherwise
    """
    text_column_candidates = ['text', 'translation', 'content', 'subtitle']
    
    for col in text_column_candidates:
        if col in df.columns:
            return col
    
    return None


def find_best_match_position(query: str, text: str) -> int:
    """
    Use improved fuzzy matching to find the best position of a query string in text
    
    Args:
        query: String to search for
        text: Text to search in
        
    Returns:
        Best match position, or -1 if no match found
    """
    if not query or not text:
        return -1
    
    # Clean both strings for better matching
    cleaned_query = clean_text_for_matching(query)
    cleaned_text = clean_text_for_matching(text)
    
    if not cleaned_query or not cleaned_text:
        return -1
    
    # Try exact match first
    if cleaned_query in cleaned_text:
        return cleaned_text.find(cleaned_query)
    
    # Use difflib for fuzzy matching
    matcher = SequenceMatcher(None, cleaned_text, cleaned_query)
    match = matcher.find_longest_match(0, len(cleaned_text), 0, len(cleaned_query))
    
    # Check if the match is good enough (at least 70% of the query)
    if match.size >= len(cleaned_query) * 0.7:
        return match.a
    
    # If no good match found
    return -1


def enhance_word_level_timestamps(df_words: pd.DataFrame) -> pd.DataFrame:
    """
    Enhance word-level timestamp precision, adjust unusually short word durations and optimize gaps
    
    Args:
        df_words: DataFrame with word-level timestamps
        
    Returns:
        Enhanced DataFrame
    """
    if df_words is None or len(df_words) == 0:
        return pd.DataFrame()
    
    # Make a copy to avoid modifying the original
    df = df_words.copy()
    
    # Identify required columns
    required_cols = ['start', 'end', 'text']
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"Required column '{col}' missing in word-level timestamps")
            return df_words
    
    # Adjust unusually short words
    for i in range(len(df)):
        word = df.iloc[i]['text']
        if not pd.isna(word):
            start_time = float(df.iloc[i]['start'])
            end_time = float(df.iloc[i]['end'])
            duration = end_time - start_time
            
            # Calculate minimum duration based on word length
            min_duration = max(0.1, len(word) * 0.05)  # At least 0.1s, or 50ms per character
            
            # Adjust if duration is too short
            if duration < min_duration:
                # Try to extend end time if possible
                if i < len(df) - 1:
                    next_start = float(df.iloc[i+1]['start'])
                    possible_end = min(start_time + min_duration, next_start - 0.01)  # Leave small gap
                    df.loc[df.index[i], 'end'] = possible_end
                else:
                    # Last word, can extend more freely
                    df.loc[df.index[i], 'end'] = start_time + min_duration
    
    # Optimize gaps between words
    for i in range(1, len(df)):
        prev_end = float(df.iloc[i-1]['end'])
        curr_start = float(df.iloc[i]['start'])
        
        # Adjust excessive gaps (>0.3s) unless it's punctuation or paragraph boundary
        if curr_start - prev_end > 0.3:
            prev_word = str(df.iloc[i-1]['text']).strip()
            curr_word = str(df.iloc[i]['text']).strip()
            
            # Check if there should be a pause (e.g., at punctuation)
            is_punctuation_boundary = bool(re.search(r'[.,;:!?]$', prev_word))
            
            # If not a natural pause point, reduce gap
            if not is_punctuation_boundary:
                ideal_gap = 0.05  # 50ms between words
                df.loc[df.index[i], 'start'] = prev_end + ideal_gap
    
    return df


def extract_numeric_tags(text: str) -> List[Dict[str, Union[str, int]]]:
    """
    Extract numeric tags from text and return segments with their positions.
    
    Args:
        text: Text containing numeric tags like [1], [2], etc.
        
    Returns:
        List of dicts with 'text', 'tag', and 'position' for each segment
    """
    if not text:
        return []
        
    # Pattern to match [number] tags and capture the number
    pattern = r'(\[\d+\])'
    segments = []
    last_end = 0
    
    # Find all tag positions
    matches = list(re.finditer(pattern, text))
    
    if not matches:
        return [{'text': text.strip(), 'tag': None, 'position': 0}]
    
    # Process segments between tags
    for i, match in enumerate(matches):
        tag = match.group(1)
        tag_start = match.start()
        
        # Get text before this tag
        if tag_start > last_end:
            segment_text = text[last_end:tag_start].strip()
            if segment_text:
                segments.append({
                    'text': segment_text,
                    'tag': None,
                    'position': last_end
                })
        
        # Get the tagged segment
        next_match = matches[i+1] if i+1 < len(matches) else None
        segment_end = next_match.start() if next_match else len(text)
        
        segment_text = text[tag_start:segment_end].strip()
        if segment_text:
            segments.append({
                'text': segment_text,
                'tag': tag,
                'position': tag_start
            })
        
        last_end = segment_end
    
    # Add any remaining text after last tag
    if last_end < len(text):
        segment_text = text[last_end:].strip()
        if segment_text:
            segments.append({
                'text': segment_text,
                'tag': None,
                'position': last_end
            })
    
    return segments

def validate_tag_alignment(original_text: str, translated_text: str, tag: str) -> bool:
    """
    Validate that the tag appears in both original and translated text with proper context.
    
    Args:
        original_text: Original text segment
        translated_text: Translated text segment
        tag: The tag to validate (e.g., '[1]')
        
    Returns:
        bool: True if tag alignment is valid, False otherwise
    """
    if not tag or not isinstance(tag, str):
        return False
        
    # Check if tag exists in both texts
    tag_in_original = tag in original_text
    tag_in_translated = tag in translated_text
    
    # If tag is not in either text, consider it invalid
    if not tag_in_original and not tag_in_translated:
        return False
        
    # If tag is in one but not the other, log a warning
    if tag_in_original != tag_in_translated:
        logger.warning(f"Tag {tag} appears in {'original' if tag_in_original else 'translated'} but not in {'translated' if tag_in_original else 'original'}")
        return False
        
    # Check if the surrounding context is similar (basic check)
    original_context = original_text.split(tag)
    translated_context = translated_text.split(tag)
    
    # If we have text before the tag, check if it's similar
    if len(original_context) > 1 and len(translated_context) > 1:
        orig_before = original_context[0].strip()
        trans_before = translated_context[0].strip()
        if orig_before and trans_before and len(orig_before) > 3 and len(trans_before) > 3:
            # Simple similarity check - if the last 3 characters don't match, might be misaligned
            if orig_before[-3:].lower() != trans_before[-3:].lower():
                logger.warning(f"Context before tag {tag} doesn't match between original and translated text")
                return False
                
    return True


def align_with_numeric_tags(original_df: pd.DataFrame, translated_text: str, max_missing_percent: float = 10.0) -> pd.DataFrame:
    """
    Align translated text with numeric tags to original subtitle timing with strict tag validation.
    
    This version enforces strict tag-based alignment between original and translated text segments.
    It requires that the translated text contains numeric tags (e.g., [1], [2]) that correspond
    to segments in the original text.
    
    Args:
        original_df: DataFrame with original subtitles (source language), including 'start' and 'end' times.
        translated_text: A single string containing all translated segments, each prefixed with a numeric tag like [1].
        max_missing_percent: Maximum allowed percentage of missing tags (0-100). Default is 10%.
                            If more tags are missing, raises an error.
        
    Returns:
        DataFrame with translated text precisely aligned to the original timing based on numeric tags.
        
    Raises:
        ValueError: If input validation fails or tags are missing/invalid
    """
    if original_df is None or not isinstance(original_df, pd.DataFrame):
        raise ValueError("Original DataFrame is required and must be a pandas DataFrame.")
    
    if not translated_text or not isinstance(translated_text, str):
        raise ValueError("Translated text is required and must be a string.")
        
    if not (0 <= max_missing_percent <= 100):
        raise ValueError("max_missing_percent must be between 0 and 100")

    # Create a dictionary for quick lookup of original timings by index
    timing_map = {i: {'start': row['start'], 'end': row['end'], 'original_text': row.get('text', '')} 
                  for i, row in original_df.iterrows()}

    # Extract segments and their tags from the translated text
    segments = extract_numeric_tags(translated_text)
    
    aligned_data = []
    processed_indices = set()
    missing_indices = set()

    # Filter for segments that have a numeric tag
    tagged_segments = [seg for seg in segments if seg.get('tag')]

    if not tagged_segments:
        logger.warning("No numeric tags found in translated text. Falling back to sequential alignment.")
        return _fallback_to_sequential(original_df, translated_text)

    # First pass: Process all tagged segments with validation
    tag_to_index = {}
    valid_tags = set()
    
    # Create a mapping of original text to their indices for validation
    original_texts = {}
    for idx, row in original_df.iterrows():
        if 'text' in row:
            original_texts[idx] = row['text']
    
    # Process each tagged segment with validation
    for segment in tagged_segments:
        tag = segment.get('tag')
        try:
            # Extract the number from the tag, e.g., "[12]" -> 12
            tag_number = int(re.search(r'\d+', tag).group())
            # DataFrame index is 0-based, so subtract 1
            original_index = tag_number - 1
            
            # Only process if index is valid
            if 0 <= original_index < len(original_df):
                # Get original and translated text for validation
                original_text = original_texts.get(original_index, '')
                translated_text_segment = segment.get('text', '')
                
                # Validate tag alignment between original and translated text
                if validate_tag_alignment(original_text, translated_text_segment, tag):
                    tag_to_index[tag_number] = original_index
                    valid_tags.add(tag)
                else:
                    logger.warning(f"Skipping invalid tag alignment for {tag} - context mismatch")
                    
        except (AttributeError, ValueError) as e:
            logger.warning(f"Could not parse tag '{tag}'. Error: {e}")
    
    # Log tag validation results
    if valid_tags:
        logger.info(f"Validated {len(valid_tags)} tags for alignment")
    else:
        logger.warning("No valid tags found for alignment")
    
    # Check for missing tags
    all_indices = set(range(len(original_df)))
    found_indices = set(tag_to_index.values())
    missing_indices = all_indices - found_indices
    total_segments = len(original_df)
    missing_percent = (len(missing_indices) / total_segments) * 100 if total_segments > 0 else 100
    
    # If too many tags are missing, raise an error
    if missing_percent > max_missing_percent:
        error_msg = (
            f"Tag-based alignment failed: {missing_percent:.1f}% of tags are missing "
            f"(threshold: {max_missing_percent}%). "
            "Please ensure the translated text contains the correct numeric tags."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    elif missing_indices:
        logger.info(
            f"Found {len(missing_indices)} missing tags out of {total_segments} "
            f"({missing_percent:.1f}%), which is within the {max_missing_percent}% threshold. "
            "Proceeding with partial alignment."
        )
    
    # Second pass: Build aligned data with proper timing and tag validation
    for tag_number, original_index in tag_to_index.items():
        # Find the segment with this exact tag
        tag_str = f'[{tag_number}]'
        segment = next((s for s in tagged_segments if s.get('tag') == tag_str), None)
        if not segment:
            logger.warning(f"Tag {tag_str} not found in translated segments")
            continue
            
        # Get text and clean it (remove the tag itself from the text)
        text = segment.get('text', '').strip()
        clean_text = re.sub(r'\[\d+\]\s*', '', text).strip()
        
        # Verify timing info exists
        if original_index not in timing_map:
            logger.warning(f"No timing info found for tag {tag_str} at index {original_index}")
            continue
            
        timing_info = timing_map[original_index]
        
        # Add to aligned data with validation info
        aligned_data.append({
            'start': timing_info['start'],
            'end': timing_info['end'],
            'text': clean_text,
            'original_text': timing_info['original_text'],
            'tag': tag_str,
            'has_tag': True,
            'tag_valid': True,
            'tag_original_position': original_index
        })
        processed_indices.add(original_index)
        
        # Log detailed alignment info for debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Aligned tag {tag_str} to position {original_index}: "
                       f"'{clean_text[:50]}...'" if len(clean_text) > 50 else f"'{clean_text}'")
    
    # Add placeholders for missing segments
    for idx in missing_indices:
        if idx in timing_map:
            timing_info = timing_map[idx]
            aligned_data.append({
                'start': timing_info['start'],
                'end': timing_info['end'],
                'text': '',  # Empty text for missing segments
                'original_text': timing_info['original_text'],
                'tag': f'[{idx + 1}]',  # Tag is 1-based in the output
                'has_tag': False
            })
    
    # Sort by start time to maintain correct order
    aligned_data.sort(key=lambda x: x['start'])
    
    # Log alignment summary
    logger.info(
        f"Aligned {len(processed_indices)} out of {total_segments} segments. "
        f"Missing {len(missing_indices)} segments ({missing_percent:.1f}%)."
    )
    
    if not aligned_data:
        logger.error("Alignment process resulted in no data. Please check input text and tags.")
        return pd.DataFrame(columns=['start', 'end', 'text', 'original_text', 'tag', 'has_tag'])
    
    # Convert to DataFrame and return
    return pd.DataFrame(aligned_data)


def clean_sentence_punctuation(text: str) -> str:
    """
    Clean up punctuation at the start and end of a sentence.
    Removes unwanted punctuation like commas, periods, etc. from the start/end,
    while preserving question marks, exclamation marks, quotes, and other meaningful punctuation.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text with proper punctuation
    """
    if not text or not isinstance(text, str):
        return text
        
    # Define punctuation to remove from start/end
    START_PUNCTUATION = ',.，。、:：;；'  # Add more as needed
    END_PUNCTUATION = ',.，。、:：;；'    # Add more as needed
    
    # Clean start of string
    while text and text[0] in START_PUNCTUATION:
        text = text[1:].lstrip()
    
    # Clean end of string
    while text and text[-1] in END_PUNCTUATION:
        text = text[:-1].rstrip()
    
    return text


def smart_repair_and_realign(raw_content: str, expected_count: int, lang_code: str = "test_lang") -> list:
    """
    Parses raw text from a translation file, intelligently handles various format
    errors including missing segment numbers, and realigns the content to an expected count.

    It can handle:
    - Multiple segments on a single line (e.g., [8]...[9]...).
    - Missing segment numbers (e.g., jumps from [51] to [53]).
    - Un-numbered "orphaned" lines between segments, using them to fill gaps.
    - Cleans up unwanted punctuation at start/end of segments.

    Args:
        raw_content (str): The entire content of the translation file.
        expected_count (int): The final number of segments we expect.
        lang_code (str): The language code, used for logging.

    Returns:
        list[str]: A list of cleaned, repaired, and aligned translated lines.
    """
    logger.info(f"--- Starting smart repair process for language '{lang_code}' ---")
    
    # Initialize data structures
    parsed_segments = {}
    orphaned_lines = {}
    
    # Split content into parts using segment markers like [1], [2], etc.
    parts = re.split(r'(\[\d+\])', raw_content)
    
    # Process each segment and its content
    for i in range(1, len(parts), 2):
        try:
            # Extract segment number from the marker (e.g., '[1]' -> 1)
            segment_num = int(re.search(r'\d+', parts[i]).group())
            text_chunk = parts[i+1]
            
            # Split the text chunk into lines and clean them
            lines_in_chunk = [line.strip() for line in text_chunk.strip().split('\n') if line.strip()]

            if not lines_in_chunk:
                parsed_segments[segment_num] = ""
                continue

            # First line belongs to the current segment
            cleaned_line = clean_sentence_punctuation(lines_in_chunk[0])
            if segment_num not in parsed_segments:
                parsed_segments[segment_num] = cleaned_line
            else:  # Handle rare case of duplicate segment numbers
                parsed_segments[segment_num] = clean_sentence_punctuation(
                    f"{parsed_segments[segment_num]} {cleaned_line}"
                )

            # Any additional lines are considered orphaned
            if len(lines_in_chunk) > 1:
                orphans = lines_in_chunk[1:]
                if segment_num not in orphaned_lines:
                    orphaned_lines[segment_num] = []
                orphaned_lines[segment_num].extend(orphans)
                logger.info(f"Found {len(orphans)} orphaned line(s) after segment [{segment_num}]: {orphans}")

        except (ValueError, IndexError) as e:
            logger.warning(f"Error processing segment: {e}")
            continue
    
    logger.info(f"Parsed {len(parsed_segments)} unique segments from the file.")
    
    # Rebuild the aligned list with orphaned lines filling the gaps
    realigned_lines = []
    for i in range(1, expected_count + 1):
        if i in parsed_segments:
            realigned_lines.append(parsed_segments[i])
        elif (i - 1) in orphaned_lines and orphaned_lines[i - 1]:
            # Use an orphaned line from the previous segment to fill the gap
            filler_text = orphaned_lines[i - 1].pop(0)
            realigned_lines.append(filler_text)
            logger.info(f"SUCCESS: Filled gap at [{i}] with orphaned line: '{filler_text}'")
        else:
            realigned_lines.append("")
            logger.warning(f"Segment [{i}] not found and no orphan text available to fill. Using empty string.")

    logger.info(f"--- Smart repair process finished. Returning {len(realigned_lines)} lines. ---")
    return realigned_lines


def _require_numeric_tags(original_df: pd.DataFrame, translated_text: str) -> pd.DataFrame:
    """
    Enforce tag-based alignment by requiring numeric tags in the translated text.
    
    Args:
        original_df: DataFrame containing original subtitles with timing
        translated_text: Translated text that must contain numeric tags
        
    Returns:
        DataFrame with aligned subtitles based on numeric tags
        
    Raises:
        ValueError: If no numeric tags are found in the translated text
    """
    # Check if translated text contains numeric tags
    if not any(re.search(r'\[\d+\]', str(translated_text))):
        raise ValueError(
            "Tag-based alignment requires numeric tags (e.g., [1], [2]) in the translated text. "
            "No numeric tags were found."
        )
    
    # Use the existing tag-based alignment
    return align_with_numeric_tags(original_df, translated_text)

def align_translated_subtitles(original_df: pd.DataFrame, translated_df: pd.DataFrame) -> pd.DataFrame:
    """
    Align translated subtitles to match the timing of original subtitles using numeric tags.
    
    This function enforces strict tag-based alignment between original and translated subtitles.
    It requires that the translated text contains numeric tags (e.g., [1], [2]) that correspond
    to the segments in the original subtitles.
    
    Args:
        original_df: DataFrame with original subtitles (source language)
        translated_df: DataFrame with translated subtitles (target language)
        
    Returns:
        DataFrame with aligned and segmented translated subtitles
        
    Raises:
        ValueError: If validation fails or if numeric tags are missing
    """
    if original_df is None or translated_df is None:
        logger.error("Both original and translated DataFrames must be provided")
        return None
    
    # Check required columns
    required_columns = ['start', 'end', 'text']
    for col in required_columns:
        if col not in original_df.columns or col not in translated_df.columns:
            logger.error(f"Required column '{col}' missing in input DataFrames")
            return None
    
    # Combine all translated text for tag-based alignment
    combined_translation = " ".join(str(text) for text in translated_df['text'] if text)
    
    # Enforce tag-based alignment
    try:
        logger.info("Using tag-based alignment with numeric tags")
        return _require_numeric_tags(original_df, combined_translation)
    except ValueError as e:
        logger.error(f"Tag-based alignment failed: {str(e)}")
        raise

# Semantic alignment functionality has been removed


def _fallback_proportional_alignment(original_df: pd.DataFrame, translated_df: pd.DataFrame) -> pd.DataFrame:
    """Fallback alignment using proportional timing when other methods fail."""
    aligned_df = translated_df.copy()
    
    # Calculate total duration and text length
    orig_total_duration = original_df.iloc[-1]['end'] - original_df.iloc[0]['start']
    trans_total_length = sum(len(str(text)) for text in translated_df['text'])
    
    # If no text, just return with original timing
    if trans_total_length == 0:
        return aligned_df
    
    # Calculate cumulative text length for proportional timing
    cum_length = 0
    for i in range(len(aligned_df)):
        text = str(aligned_df.iloc[i]['text']).strip()
        text_length = len(text)
        
        # Calculate proportional start and end times
        start_ratio = cum_length / trans_total_length
        end_ratio = (cum_length + text_length) / trans_total_length
        
        # Apply timing
        aligned_df.at[i, 'start'] = original_df.iloc[0]['start'] + (start_ratio * orig_total_duration)
        aligned_df.at[i, 'end'] = original_df.iloc[0]['start'] + (end_ratio * orig_total_duration)
        
        # Ensure minimum duration
        min_duration = 1.0  # At least 1 second
        if aligned_df.at[i, 'end'] - aligned_df.at[i, 'start'] < min_duration:
            aligned_df.at[i, 'end'] = aligned_df.at[i, 'start'] + min_duration
        
        cum_length += text_length
    
    return aligned_df


# ffsubsync alignment functionality has been removed - using tag-based alignment instead


def load_original_segments(segments_path: Union[str, Path]) -> List[Dict]:
    """
    Load and parse original_segments.json file.
    
    Args:
        segments_path: Path to original_segments.json
        
    Returns:
        List of segment dictionaries with start, end, and text
    """
    try:
        with open(segments_path, 'r', encoding='utf-8') as f:
            segments = json.load(f)
            
        # Ensure all required fields are present
        processed_segments = []
        for seg in segments:
            if not all(k in seg for k in ['start', 'end', 'text']):
                logger.warning(f"Skipping invalid segment: {seg}")
                continue
                
            processed_segments.append({
                'start': float(seg['start']),
                'end': float(seg['end']),
                'text': seg['text'].strip()
            })
            
        return processed_segments
        
    except Exception as e:
        logger.error(f"Error loading original segments: {str(e)}")
        raise

def split_text_by_duration_ratios(text: str, durations: List[float]) -> List[str]:
    """
    Split text into parts based on duration ratios.
    
    Args:
        text: Text to split
        durations: List of durations for each part
        
    Returns:
        List of text segments
    """
    import re
    
    # Split by Chinese and English commas
    phrases = re.split(r'[，,]', text)
    total_duration = sum(durations)
    ratios = [d / total_duration for d in durations]
    total_phrases = len(phrases)

    # Calculate phrase counts per segment
    counts = [round(r * total_phrases) for r in ratios]

    # Adjust for rounding errors
    while sum(counts) > total_phrases:
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < total_phrases:
        counts[counts.index(min(counts))] += 1

    # Split the text
    result = []
    idx = 0
    for count in counts:
        segment = '，'.join(phrases[idx:idx+count]).strip('，')
        if segment:  # Only add non-empty segments
            result.append(segment)
        idx += count

    return result

# Smart text splitting functionality has been removed

def generate_srt_from_segments(segments: List[Dict], max_chars_per_segment: int = 42, use_duration_based_splitting: bool = False) -> str:
    """
    Generate SRT content from original segments with smart splitting for long segments.
    
    Args:
        segments: List of segment dictionaries with start, end, and text
        max_chars_per_segment: Maximum characters per subtitle segment before splitting
        
    Returns:
        String containing SRT formatted subtitles
    """
    srt_entries = []
    
    for i, seg in enumerate(segments, 1):
        start = seg['start']
        end = seg['end']
        text = seg['text'].strip()
        
        if not text:
            continue
            
        # Check if segment is too long and needs splitting
        if len(text) > max_chars_per_segment:
            # Simple character-based text splitting
            num_parts = (len(text) + max_chars_per_segment - 1) // max_chars_per_segment
            part_length = len(text) // num_parts
            parts = [text[i:i + part_length].strip() for i in range(0, len(text), part_length)]
            
            # Calculate duration per part
            duration = end - start
            part_duration = duration / len(parts)
            
            # Create sub-segments with proportional timing
            for j, part in enumerate(parts):
                part_start = start + (j * part_duration)
                part_end = start + ((j + 1) * part_duration)
                
                # Ensure we don't go beyond the original end time due to floating point inaccuracies
                part_end = min(part_end, end)
                
                srt_entries.append({
                    'index': len(srt_entries) + 1,
                    'start': part_start,
                    'end': part_end,
                    'text': part
                })
        else:
            srt_entries.append({
                'index': len(srt_entries) + 1,
                'start': start,
                'end': end,
                'text': text
            })
    
    # Generate final SRT content with proper timing
    final_entries = []
    for i, entry in enumerate(srt_entries, 1):
        start_time = time_to_srt_format(entry['start'])
        end_time = time_to_srt_format(entry['end'])
        final_entries.append(f"{i}\n{start_time} --> {end_time}\n{entry['text']}\n")
    
    return '\n'.join(final_entries)
    
    return '\n'.join(srt_entries)

def srt_to_dataframe(srt_content: str) -> pd.DataFrame:
    """
    Convert SRT content to a DataFrame with 'start', 'end', and 'text' columns.
    
    Args:
        srt_content: String containing SRT formatted subtitles
        
    Returns:
        DataFrame with columns: 'start', 'end', 'text'
    """
    import re
    from datetime import datetime, timedelta
    
    # SRT timestamp format: 00:00:20,000 --> 00:00:24,400
    timestamp_pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})'
    )
    
    subtitles = []
    current_sub = {}
    
    for line in srt_content.split('\n'):
        line = line.strip()
        
        # Skip empty lines between subtitles
        if not line and current_sub:
            if 'start' in current_sub and 'end' in current_sub and 'text' in current_sub:
                subtitles.append(current_sub)
            current_sub = {}
            continue
            
        # Check for timestamp line
        match = timestamp_pattern.match(line)
        if match:
            start_time = match.group(1).replace(',', '.')
            end_time = match.group(2).replace(',', '.')
            current_sub['start'] = start_time
            current_sub['end'] = end_time
        # If line is not empty and not a timestamp, it's part of the subtitle text
        elif line and not line.isdigit() and 'start' in current_sub:
            if 'text' in current_sub:
                current_sub['text'] += ' ' + line
            else:
                current_sub['text'] = line
    
    # Add the last subtitle if exists
    if current_sub and 'start' in current_sub and 'end' in current_sub and 'text' in current_sub:
        subtitles.append(current_sub)
    
    # Convert to DataFrame and clean up
    if subtitles:
        df = pd.DataFrame(subtitles)
        # Ensure proper column order
        df = df[['start', 'end', 'text']]
        return df
    
    return pd.DataFrame(columns=['start', 'end', 'text'])


def generate_clean_text_subtitles(df: pd.DataFrame) -> str:
    """
    Generate clean text subtitles with all punctuation removed.
    
    Args:
        df: DataFrame with 'start', 'end', and text columns
        
    Returns:
        String with clean text subtitle content (one line per subtitle)
    """
    if df is None or len(df) == 0:
        return ""
    
    # Find text column
    text_col = get_text_column(df)
    if not text_col:
        logger.error("No text column found for clean text generation")
        return ""
    
    # Import remove_punctuation here to avoid circular imports
    from .segmentation import remove_punctuation
    
    clean_lines = []
    for i in range(len(df)):
        # Get text content and remove punctuation
        text = str(df.iloc[i][text_col])
        clean_text = remove_punctuation(text)
        
        # Skip empty lines
        if clean_text.strip():
            clean_lines.append(clean_text)
    
    # Join with newlines and return
    return '\n'.join(clean_lines)


def generate_srt_from_timing_mapping(timing_file: str, translated_file: str) -> str:
    """
    Generate SRT content by directly mapping timings from cleaned_chunks.txt to translated segments.
    
    Args:
        timing_file: Path to cleaned_chunks.txt with timing information
        translated_file: Path to translation_xx_segmented.txt with translated text
        
    Returns:
        String containing SRT formatted subtitles
    """
    try:
        # Read timing information from cleaned_chunks.txt
        with open(timing_file, 'r', encoding='utf-8') as f:
            timing_lines = [line.strip() for line in f if line.strip()]
        
        # Parse timing information
        timings = []
        for line in timing_lines:
            # Extract [start - end] and text
            match = re.match(r'\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]\s*(.*)', line)
            if match:
                start, end, _ = match.groups()
                try:
                    start_time = float(start)
                    end_time = float(end)
                    
                    # Ensure valid timing
                    if start_time < 0:
                        start_time = 0.0
                    if end_time <= start_time:
                        end_time = start_time + 1.0  # Default 1 second duration
                        
                    timings.append((start_time, end_time))
                except (ValueError, TypeError):
                    # Skip invalid timing entries
                    logger.warning(f"Invalid timing format in line: {line}")
                    continue
        
        # Read translated segments
        with open(translated_file, 'r', encoding='utf-8') as f:
            translated_segments = [line.strip() for line in f if line.strip()]
        
        # Handle segment count mismatches
        if len(timings) != len(translated_segments):
            logger.warning(f"Mismatched segment counts: {len(timings)} timings vs {len(translated_segments)} translations")
            
            # If we have more timings than translations, pad with empty strings
            if len(timings) > len(translated_segments):
                translated_segments.extend([''] * (len(timings) - len(translated_segments)))
            # If we have more translations than timings, use the last timing for extra translations
            else:
                last_timing = timings[-1] if timings else (0, 0)
                timings.extend([last_timing] * (len(translated_segments) - len(timings)))
                
            logger.info(f"Adjusted counts - Timings: {len(timings)}, Translations: {len(translated_segments)}")
        
        # Generate SRT content
        srt_entries = []
        for i, ((start, end), text) in enumerate(zip(timings, translated_segments), 1):
            if not text.strip():
                continue
                
            start_time = time_to_srt_format(start)
            end_time = time_to_srt_format(end)
            srt_entries.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
        
        return '\n'.join(srt_entries)
        
    except Exception as e:
        logger.error(f"Error in generate_srt_from_timing_mapping: {str(e)}", exc_info=True)
        return ""


def generate_srt_content(df: pd.DataFrame, split_sentences: bool = True, 
                        optimize_timing: bool = True, 
                        original_df: pd.DataFrame = None,
                        remove_punctuation: bool = False) -> str:
    """
    Generate SRT subtitle content from a DataFrame with timestamps.
    
    Enhanced version that:
    1. Handles numeric tags in translated text for precise alignment
    2. Aligns translated subtitles with original timing if provided
    3. Splits segments into sentence-level subtitles using word-level timing
    4. Optimizes subtitle timing for better readability
    5. Ensures non-overlapping timing
    6. Handles dialogue with quick sentence changes
    
    Args:
        df: DataFrame with 'start', 'end', and text columns
        split_sentences: Whether to split segments into sentence-level subtitles
        optimize_timing: Whether to optimize subtitle timing
        original_df: Optional DataFrame with original timing to align with
        remove_punctuation: Whether to remove punctuation from the output
        
    Returns:
        String with SRT subtitle content
    """
    if df is None or df.empty:
        return ""
        
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Convert string timestamps to float if needed
    for col in ['start', 'end']:
        if col in df.columns and df[col].notna().any() and isinstance(df[col].iloc[0], str):
            try:
                df[col] = df[col].astype(float)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not convert {col} to float: {e}")
    
    # Ensure required columns exist
    required_columns = ['start', 'end', 'text']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' missing in DataFrame")
    
    # Check for numeric tags in the text
    has_numeric_tags = any(re.search(r'\[\d+\]', str(text)) for text in df['text'] if pd.notna(text))
    
    # If we have numeric tags and original timing, use tag-based alignment
    if has_numeric_tags and original_df is not None and not original_df.empty:
        logger.info("Numeric tags detected, using tag-based alignment")
        combined_translation = " ".join(str(text) for text in df['text'] if pd.notna(text))
        df = align_with_numeric_tags(original_df, combined_translation)
    
    # Ensure proper sorting by start time
    df = df.sort_values('start').reset_index(drop=True)
    
    # Clean text and remove any remaining tags
    def clean_text(text):
        if not isinstance(text, str):
            return ""
        # Remove any numeric tags that might remain
        text = re.sub(r'\s*\[\d+\]\s*', ' ', text).strip()
        # Remove [br] tags and replace with space
        text = re.sub(r'\s*\[br\]\s*', ' ', text, flags=re.IGNORECASE)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        if remove_punctuation:
            text = re.sub(r'[^\w\s]', '', text)
        return text
    
    df['text'] = df['text'].apply(clean_text)
    
    # Skip all timing and text processing to preserve original timing exactly
    if not df.empty:
        # Ensure we have the required columns with proper types
        df = df.copy()
        df['start'] = df['start'].astype(float)
        df['end'] = df['end'].astype(float)
        df['text'] = df['text'].astype(str).str.strip()
        
        # Sort by start time to ensure proper ordering
        df = df.sort_values('start').reset_index(drop=True)
    
    # Generate SRT content
    srt_lines = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        try:
            start_time = time_to_srt_format(float(row['start']))
            end_time = time_to_srt_format(float(row['end']))
            text = str(row['text']).strip()
            
            # Skip empty subtitles
            if not text:
                continue
                
            # Add to SRT
            srt_lines.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
        except (ValueError, KeyError) as e:
            logger.warning(f"Error generating SRT for row {i}: {e}")
            continue
    
    return '\n'.join(srt_lines)
