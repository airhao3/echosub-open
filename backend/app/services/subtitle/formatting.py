"""
Subtitle formatting utilities for video processing.

This module provides functions for formatting subtitles, especially for special cases
like vertical videos. For general text segmentation, see the segmentation module.
"""
import re
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Union

from .utils import calc_text_width, calc_char_width
from .segmentation import smart_sentence_segmentation, split_at_punctuation, split_long_segments

logger = logging.getLogger(__name__)

def format_subtitle_for_vertical_video(text: str, max_width: int = 10) -> List[str]:
    """
    Optimize subtitle formatting for vertical videos to ensure each line has limited width
    and breaks naturally between words and sentences.
    
    For general text segmentation, use functions from the segmentation module.
    
    Args:
        text: Subtitle text to format
        max_width: Maximum character width per line (typically lower for vertical videos)
        
    Returns:
        List of formatted subtitle lines
    """
    if not text or not text.strip():
        return []
        
    text = text.strip()
    
    # If already contains line breaks, respect them
    if '\n' in text:
        return [line for line in text.split('\n') if line.strip()]
    
    # Check if this is Chinese (or other CJK languages)
    is_cjk = any('\u4e00' <= char <= '\u9fff' for char in text)
    
    # Define different splitting strategies
    if is_cjk:
        # For CJK languages, we can split character by character
        return _format_cjk_subtitle(text, max_width)
    else:
        # For other languages, split by words
        return _format_western_subtitle(text, max_width)


def _format_cjk_subtitle(text: str, max_width: int) -> List[str]:
    """
    Format CJK (Chinese, Japanese, Korean) subtitle text
    
    Args:
        text: Text to format
        max_width: Maximum width per line
        
    Returns:
        List of formatted lines
    """
    # Define break points in priority order
    primary_breaks = ['。', '！', '？', '；', '：', '\n']  # Period, exclamation, question, etc.
    secondary_breaks = ['，', '、', ' ']  # Comma, enumeration comma, space
    
    formatted_lines = []
    current_line = ""
    current_width = 0.0
    
    # First try to break at natural sentence endings
    for char in text:
        char_width = calc_char_width(char)
        
        # If adding this char exceeds width and we have content, add line
        if current_width + char_width > max_width and current_line:
            formatted_lines.append(current_line)
            current_line = ""
            current_width = 0.0
        
        current_line += char
        current_width += char_width
        
        # If this is a natural break point and we have enough content, add line
        if char in primary_breaks and current_width > max_width/2:
            formatted_lines.append(current_line)
            current_line = ""
            current_width = 0.0
    
    # Add any remaining content
    if current_line:
        formatted_lines.append(current_line)
    
    # If we have very few lines, we're done
    if len(formatted_lines) >= 2 or all(calc_text_width(line) <= max_width for line in formatted_lines):
        return formatted_lines
    
    # Otherwise, we may have a line that's too long - try again with secondary breaks
    result = []
    for line in formatted_lines:
        if calc_text_width(line) <= max_width:
            result.append(line)
            continue
            
        # This line is too long, process character by character again
        inner_line = ""
        inner_width = 0.0
        
        for char in line:
            char_width = calc_char_width(char)
            
            # If adding this char exceeds width and we have content, add line
            if inner_width + char_width > max_width and inner_line:
                result.append(inner_line)
                inner_line = ""
                inner_width = 0.0
            
            inner_line += char
            inner_width += char_width
            
            # If this is a secondary break point and we have enough content, add line
            if char in secondary_breaks and inner_width > max_width/3:
                result.append(inner_line)
                inner_line = ""
                inner_width = 0.0
        
        # Add any remaining content
        if inner_line:
            result.append(inner_line)
    
    return result


def _format_western_subtitle(text: str, max_width: int) -> List[str]:
    """
    Format western (Latin-based) subtitle text
    
    Args:
        text: Text to format
        max_width: Maximum width per line
        
    Returns:
        List of formatted lines
    """
    words = text.split(' ')
    lines = []
    current_line = ""
    current_width = 0.0
    
    for word in words:
        word_with_space = word + ' '
        word_width = calc_text_width(word_with_space)
        
        if current_width + word_width <= max_width:
            current_line += word_with_space
            current_width += word_width
        else:
            # If current line has content, add it to lines
            if current_line:
                lines.append(current_line.strip())
            
            # If the word itself is longer than max_width, we need to split it
            if word_width > max_width:
                # Split the long word
                remaining_word = word
                while remaining_word and calc_text_width(remaining_word) > max_width:
                    # Take the maximum characters that fit
                    sub_word = ""
                    sub_width = 0.0
                    for char in remaining_word:
                        char_width = calc_char_width(char)
                        if sub_width + char_width <= max_width:
                            sub_word += char
                            sub_width += char_width
                        else:
                            break
                    
                    lines.append(sub_word)
                    remaining_word = remaining_word[len(sub_word):]
                
                # Add any remaining word parts
                if remaining_word:
                    current_line = remaining_word + ' '
                    current_width = calc_text_width(current_line)
                else:
                    current_line = ""
                    current_width = 0.0
            else:
                # Start a new line with this word
                current_line = word_with_space
                current_width = word_width
    
    # Add any remaining content
    if current_line:
        lines.append(current_line.strip())
    
    return lines


def smart_sentence_segmentation(text: str, df_words: pd.DataFrame = None, is_vertical_video: bool = False) -> List[str]:
    """
    Wrapper around the segmentation.smart_sentence_segmentation function.
    This function is kept for backward compatibility.
    
    Args:
        text: Text to segment
        df_words: Optional word-level DataFrame for analyzing speech pauses
        is_vertical_video: Whether this is for a vertical video
        
    Returns:
        List of segmented sentences
    """
    try:
        from .segmentation import smart_sentence_segmentation as segment_text
        return segment_text(text, df_words, is_vertical_video)
    except Exception as e:
        logger.error(f"Smart segmentation error: {str(e)}")
        # Fallback to simple splitting method
        return [text]


def optimize_subtitle_segmentation(df: pd.DataFrame, detect_vertical=True) -> pd.DataFrame:
    """
    Optimize subtitle segmentation for better readability and synchronization accuracy.
    Handles special formatting for vertical videos to ensure subtitles stay within screen width.
    
    Args:
        df: DataFrame containing subtitle data
        detect_vertical: Whether to detect vertical videos automatically
        
    Returns:
        Optimized DataFrame with properly segmented subtitles
    """
    logger.info(f"Optimizing subtitle segmentation for {len(df)} subtitles")
    
    # Make a copy to avoid modifying the original
    result_df = df.copy()
    
    # Identify the text column
    text_column_candidates = ['text', 'translation', 'content']
    text_col = None
    for col in text_column_candidates:
        if col in result_df.columns:
            text_col = col
            break
    
    if not text_col:
        logger.warning("No suitable text column found for segmentation")
        return result_df
    
    # Check if this is a vertical video
    is_vertical_video = False
    if detect_vertical:
        # Get video dimensions from metadata if available
        if 'video_width' in result_df.columns and 'video_height' in result_df.columns:
            try:
                # Use the dimensions from the first row that has them
                for i, row in result_df.iterrows():
                    if pd.notna(row.get('video_width')) and pd.notna(row.get('video_height')):
                        video_width = float(row['video_width'])
                        video_height = float(row['video_height'])
                        
                        # If height is greater than width, it's a vertical video
                        if video_height > video_width:
                            video_aspect_ratio = video_height / video_width
                            is_vertical_video = True
                            logger.info(f"Detected vertical video with aspect ratio {video_aspect_ratio:.2f}")
                        break
            except (TypeError, ValueError) as e:
                logger.warning(f"Error detecting video dimensions: {str(e)}")
    
    # Set character limits: 15 for vertical videos, 30 for horizontal videos
    max_chars_per_line = 15 if is_vertical_video else 30
    logger.info(f"Using max {max_chars_per_line} characters per subtitle line (vertical: {is_vertical_video})")
    
    # Optimize each subtitle segment
    for i, row in result_df.iterrows():
        text = row[text_col]
        if not pd.notna(text) or not text.strip():
            continue
            
        # Get duration
        duration = row['end'] - row['start']
        
        # Check if formatting is needed using character width calculation
        is_long_content = False
        text_width = calc_text_width(text)
        width_threshold = max_chars_per_line * (1.5 if is_vertical_video else 2.5)
        
        if text_width > width_threshold:
            is_long_content = True
            logger.debug(f"Long content detected: width {text_width:.1f} > threshold {width_threshold:.1f}")
            
        # Check if any line in multiline text is too long
        if '\n' in text:
            for line in text.split('\n'):
                line_width = calc_text_width(line)
                if line_width > (max_chars_per_line * (1.0 if is_vertical_video else 1.5)):
                    is_long_content = True
                    logger.debug(f"Long line detected: width {line_width:.1f} in multiline text")
                    break
        
        if is_long_content:
            # Vertical videos need stricter formatting
            if is_vertical_video:
                # Use the special vertical video formatting function
                formatted_lines = format_subtitle_for_vertical_video(text, max_width=max_chars_per_line)
                
                # Process results
                if len(formatted_lines) <= 2:
                    # Simple case: two lines or fewer
                    result_df.at[i, text_col] = '\n'.join(formatted_lines)
                else:
                    # Complex case: need to create multiple subtitle entries
                    # First subtitle contains only the first two lines
                    result_df.at[i, text_col] = '\n'.join(formatted_lines[:2])
                    
                    # Create additional subtitle entries
                    segment_duration = duration / ((len(formatted_lines) + 1) // 2)  # Average time per two lines
                    
                    # Create new subtitle entries, max two lines each
                    new_entries = []
                    for j in range(2, len(formatted_lines), 2):
                        sub_lines = formatted_lines[j:min(j+2, len(formatted_lines))]
                        start_time = row['start'] + ((j//2) * segment_duration)
                        end_time = min(row['end'], start_time + segment_duration)
                        
                        # Ensure minimum duration
                        if end_time - start_time < 1.0:
                            end_time = start_time + 1.0
                        
                        new_entry = row.copy()
                        new_entry[text_col] = '\n'.join(sub_lines)
                        new_entry['start'] = start_time
                        new_entry['end'] = end_time
                        new_entries.append(new_entry)
                    
                    # Adjust the end time of the original subtitle
                    if new_entries:
                        result_df.at[i, 'end'] = new_entries[0]['start']
                    
                    # Add new subtitle entries
                    for entry in new_entries:
                        result_df = pd.concat([result_df, pd.DataFrame([entry])], ignore_index=True)
            else:
                # Use smart segmentation for regular videos
                segments = smart_sentence_segmentation(text, is_vertical_video=is_vertical_video)
                
                # If multiple segments found, format appropriately
                if len(segments) > 1:
                    # Subtitles typically have two lines maximum
                    if len(segments) <= 2:
                        result_df.at[i, text_col] = '\n'.join(segments)
                    else:
                        # Need to split into multiple subtitle records
                        result_df.at[i, text_col] = '\n'.join(segments[:2])
                        
                        # Create new subtitle records
                        segment_duration = duration / len(segments)
                        
                        new_entries = []
                        for j in range(2, len(segments), 2):
                            sub_segments = segments[j:min(j+2, len(segments))]
                            start_time = row['start'] + (j * segment_duration)
                            end_time = min(row['end'], start_time + (len(sub_segments) * segment_duration))
                            
                            # Ensure minimum duration
                            if end_time - start_time < 1.0:
                                end_time = start_time + 1.0
                            
                            new_entry = row.copy()
                            new_entry[text_col] = '\n'.join(sub_segments)
                            new_entry['start'] = start_time
                            new_entry['end'] = end_time
                            new_entries.append(new_entry)
                        
                        # Adjust end time of original subtitle
                        if new_entries:
                            result_df.at[i, 'end'] = new_entries[0]['start']
                        
                        # Add new subtitle entries
                        for entry in new_entries:
                            result_df = pd.concat([result_df, pd.DataFrame([entry])], ignore_index=True)
    
    # Sort by start time
    result_df = result_df.sort_values('start').reset_index(drop=True)
    
    # Fix potential time overlap issues
    for i in range(1, len(result_df)):
        if result_df.iloc[i]['start'] < result_df.iloc[i-1]['end']:
            # If current subtitle starts before previous one ends
            result_df.loc[result_df.index[i], 'start'] = result_df.iloc[i-1]['end'] + 0.05
            
            # Ensure subtitle has reasonable duration
            if result_df.iloc[i]['end'] < result_df.iloc[i]['start'] + 1.0:
                result_df.loc[result_df.index[i], 'end'] = result_df.iloc[i]['start'] + 1.0
    
    return result_df
