import os
import time
import logging
import pandas as pd
import json
import re
import warnings
from typing import List, Dict, Any, Optional, Tuple, Union

from .alignment import adjust_subtitle_timing
from .utils import calc_text_width, calc_char_width

logger = logging.getLogger(__name__)

def split_at_punctuation(text: str) -> List[str]:
    """
    Split text at sentence-ending punctuation marks.
    
    Args:
        text: Text to split
        
    Returns:
        List of text segments split at punctuation
    """
    logger.debug(f"split_at_punctuation() called with text: {text[:100]}{'...' if len(text) > 100 else ''}")
    start_time = time.time()
    
    if not text or not text.strip():
        logger.debug("split_at_punctuation(): Empty input text")
        return []
        
    # Define sentence-ending punctuation
    sentence_enders = r'([.!?。！？;；：:…]\s*)'
    logger.debug(f"Using sentence enders: {sentence_enders}")
    
    # Split at sentence-enders but keep them
    segments = re.split(f'({sentence_enders})', text)
    logger.debug(f"Initial split into {len(segments)} segments")
    
    # Recombine punctuation with preceding text
    result = []
    i = 0
    while i < len(segments):
        if i + 1 < len(segments) and re.match(sentence_enders, segments[i+1]):
            # Combine text with following punctuation
            combined = segments[i] + segments[i+1]
            result.append(combined.strip())
            i += 2
        else:
            if segments[i].strip():
                result.append(segments[i].strip())
            i += 1
    
    duration = time.time() - start_time
    logger.debug(f"split_at_punctuation() completed in {duration:.4f}s. Split into {len(result)} segments")
    if len(result) > 0:
        logger.debug(f"First segment: {result[0][:100]}{'...' if len(result[0]) > 100 else ''}")
        if len(result) > 1:
            logger.debug(f"Last segment: {result[-1][:100]}{'...' if len(result[-1]) > 100 else ''}")
    
    return result

def split_long_segments(segments: List[str], max_length: int = 25) -> List[str]:
    """
    Further split segments that exceed max_length at natural break points.
    Uses a more aggressive splitting strategy to create shorter, more readable segments.
    
    Args:
        segments: List of text segments
        max_length: Maximum allowed segment length (reduced from default 40 to 25)
        
    Returns:
        List of segments with long ones split further
    """
    logger.debug(f"split_long_segments() called with {len(segments)} segments, max_length={max_length}")
    start_time = time.time()
    
    result = []
    split_count = 0
    
    for i, segment in enumerate(segments):
        if len(segment) <= max_length:
            result.append(segment)
            continue
            
        logger.debug(f"Segment {i+1} is too long ({len(segment)} > {max_length}): {segment[:50]}...")
        
        # More aggressive split points - include more conjunctions and punctuation
        # English split points
        english_splits = [',', ';', ' and ', ' or ', ' but ', ' yet ', ' for ', ' nor ', ' so ', ' that ', ' which ']
        
        # Chinese split points - expanded list
        chinese_punctuation = ['，', '；', '：', '。', '！', '？', '、', '—', '…', '（', '）', '『', '』', '「', '」', '《', '》']
        
        # More comprehensive list of Chinese conjunctions and particles
        chinese_conjunctions = [
            # Coordinating conjunctions
            ' 和 ', ' 与 ', ' 跟 ', ' 同 ', ' 以及 ', ' 并 ', ' 而 ', ' 而且 ', ' 并且 ', ' 或者 ', ' 还是 ', ' 不是 ', ' 就是 ', 
            ' 要么 ', ' 既 ', ' 又 ', ' 也 ', ' 还 ', ' 而且 ', ' 并且 ', ' 甚至 ', ' 何况 ', ' 况且 ', ' 于是 ', ' 然后 ', ' 接着 ',
            # Subordinating conjunctions
            ' 因为 ', ' 由于 ', ' 既然 ', ' 如果 ', ' 要是 ', ' 即使 ', ' 虽然 ', ' 尽管 ', ' 固然 ', ' 宁可 ', ' 宁愿 ', ' 与其 ', ' 不如 ', 
            ' 不是 ', ' 就是 ', ' 是 ', ' 还是 ', ' 要么 ', ' 首先 ', ' 其次 ', ' 再次 ', ' 最后 ', ' 总之 ', ' 总而言之 ',
            # Common particles that can be split after
            ' 的 ', ' 地 ', ' 得 ', ' 了 ', ' 着 ', ' 过 ', ' 啊 ', ' 吧 ', ' 呢 ', ' 吗 ', ' 啦 ', ' 呀 ', ' 嘛 ', ' 哇 ', ' 哪 ',
            # More conjunctions and connectors
            ' 因此 ', ' 所以 ', ' 于是 ', ' 然后 ', ' 接着 ', ' 从而 ', ' 以致 ', ' 以便 ', ' 以免 ', ' 除非 ', ' 除了 ', ' 不但 ', ' 不仅 ',
            ' 不管 ', ' 无论 ', ' 不论 ', ' 为了 ', ' 由于 ', ' 因为 ', ' 既然 ', ' 如果 ', ' 要是 ', ' 即使 ', ' 虽然 ', ' 尽管 ', ' 固然 ',
            ' 宁可 ', ' 宁愿 ', ' 与其 ', ' 不如 ', ' 不是 ', ' 就是 ', ' 是 ', ' 还是 ', ' 要么 ', ' 首先 ', ' 其次 ', ' 再次 ', ' 最后 ',
            ' 总之 ', ' 总而言之 ', ' 例如 ', ' 比如 ', ' 比如说 ', ' 正如 ', ' 正如...一样 ', ' 像...一样 ', ' 像...这样 ', ' 像...那样 ',
            ' 一方面...一方面... ', ' 一来...二来... ', ' 一则...二则... ', ' 首先...其次... ', ' 首先...然后... ', ' 先...然后... ',
            ' 先...再... ', ' 先...接着... ', ' 先...随后... ', ' 先...最后... ', ' 开始...后来... ', ' 起先...后来... ',
            ' 起先...然后... ', ' 起先...接着... ', ' 起先...随后... ', ' 起先...最后... ',
            # More common patterns
            ' 的时候 ', ' 的时候，', ' 的时候。', ' 的时候！', ' 的时候？', ' 的时候；', ' 的时候：',
            ' 的时候，', ' 的时候。', ' 的时候！', ' 的时候？', ' 的时候；', ' 的时候：'
        ]
        
        # Combine all split points and remove duplicates while preserving order
        split_points = list(dict.fromkeys(english_splits + chinese_punctuation + chinese_conjunctions))
        
        # Find the best split point
        best_pos = -1
        best_point = None
        for point in split_points:
            pos = segment.rfind(point, 0, max_length)
            if pos > best_pos:
                best_pos = pos + len(point) if point.strip() else pos
                best_point = point
        
        if best_pos > 0:
            # Split at the best position found
            first_part = segment[:best_pos].strip()
            remaining = segment[best_pos:].strip()
            logger.debug(f"  Splitting at '{best_point}' (pos {best_pos}), lengths: {len(first_part)} + {len(remaining)}")
            
            result.append(first_part)
            if remaining:
                split_count += 1
                # Recursively split remaining text
                remaining_segments = split_long_segments([remaining], max_length)
                result.extend(remaining_segments)
        else:
            # No good split point found, just split at max_length
            first_part = segment[:max_length].strip()
            remaining = segment[max_length:].strip()
            logger.debug(f"  No good split point found, forcing split at position {max_length}")
            
            result.append(first_part)
            if remaining:
                split_count += 1
                # Recursively split remaining text
                remaining_segments = split_long_segments([remaining], max_length)
                result.extend(remaining_segments)
    
    duration = time.time() - start_time
    logger.debug(f"split_long_segments() completed in {duration:.4f}s. Split {split_count} segments. "
                f"Input: {len(segments)} segments, Output: {len(result)} segments")
    
    if split_count > 0:
        logger.debug("Sample of split segments:")
        for i, seg in enumerate(result):
            if i >= 3 and i < len(result) - 3:
                if i == 3:
                    logger.debug(f"  ... and {len(result)-6} more segments ...")
                continue
            logger.debug(f"  {i+1:3d}. {seg[:80]}{'...' if len(seg) > 80 else ''}")
    
    return result

def split_text_into_lines(text: str, max_length: int = 20) -> List[str]:
    """
    Split text into multiple lines for better subtitle presentation
    Simple implementation that doesn't add additional punctuation
    
    Args:
        text: Text to split
        max_length: Maximum line length in characters
        
    Returns:
        List of split lines
    """
    if not text:
        return []
    
    # If text already contains line breaks, respect them
    if '\n' in text:
        return [line for line in text.split('\n') if line.strip()]
    
    # Detect language type to use appropriate strategy
    is_cjk = any('\u4e00' <= char <= '\u9fff' for char in text)
    
    if is_cjk:
        # For CJK languages, split at suitable points
        return _split_cjk_text(text, max_length)
    else:
        # For western languages, split by words
        return _split_western_text(text, max_length)


def _split_cjk_text(text: str, max_length: int) -> List[str]:
    """
    Split CJK (Chinese, Japanese, Korean) text into lines
    
    Args:
        text: CJK text to split
        max_length: Maximum line length
        
    Returns:
        List of lines
    """
    # Define split points in priority order
    # Primary: Period, exclamation, question mark, semicolon, colon
    primary_breaks = ['。', '！', '？', '；', '：']
    # Secondary: Comma, enumeration comma, space
    secondary_breaks = ['，', '、', ' ']
    
    # If text is short enough, return as is
    if len(text) <= max_length:
        return [text]
    
    # Try to split at primary break points first
    lines = []
    current_line = ""
    
    for char in text:
        current_line += char
        
        # If current line is long enough and ends with a primary break, split
        if len(current_line) >= max_length / 2 and char in primary_breaks:
            lines.append(current_line)
            current_line = ""
    
    # Add any remaining text
    if current_line:
        lines.append(current_line)
    
    # If we didn't get good splitting from primary breaks, try secondary breaks
    if len(lines) == 1 and len(lines[0]) > max_length:
        lines = []
        current_line = ""
        
        for char in text:
            current_line += char
            
            # If current line is long enough and ends with any break, split
            if len(current_line) >= max_length / 2 and (char in primary_breaks or char in secondary_breaks):
                lines.append(current_line)
                current_line = ""
        
        # Add any remaining text
        if current_line:
            lines.append(current_line)
    
    # If still no good splitting, force split at max_length
    if len(lines) == 1 and len(lines[0]) > max_length:
        lines = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    return lines


def _split_western_text(text: str, max_length: int) -> List[str]:
    """
    Split western text into lines by words
    
    Args:
        text: Western text to split
        max_length: Maximum line length
        
    Returns:
        List of lines
    """
    words = text.split(' ')
    lines = []
    current_line = ""
    
    for word in words:
        # Check if adding this word would exceed the limit
        test_line = current_line + (" " if current_line else "") + word
        
        if len(test_line) <= max_length:
            current_line = test_line
        else:
            # If current line has content, add it to lines
            if current_line:
                lines.append(current_line)
            
            # Start a new line with this word
            # If the word itself is longer than max_length, it needs to be split
            if len(word) > max_length:
                # Split the long word into chunks
                word_chunks = [word[i:i+max_length] for i in range(0, len(word), max_length)]
                # Add all but the last chunk to lines
                lines.extend(word_chunks[:-1])
                # Start the new line with the last chunk
                current_line = word_chunks[-1]
            else:
                current_line = word
    
    # Add the last line if it has content
    if current_line:
        lines.append(current_line)
    
    return lines


def smart_sentence_segmentation(text: str, df_words: pd.DataFrame = None, is_vertical_video: bool = False) -> List[str]:
    """
    Intelligent sentence segmentation considering punctuation, speech pauses and natural language structure.
    Prefers more frequent splitting at natural break points for better readability.
    
    Args:
        text: Text to segment
        df_words: Optional word-level DataFrame for analyzing speech pauses
        is_vertical_video: Whether this is for a vertical video (requiring stricter width limits)
        
    Returns:
        List of segmented sentences
    """
    logger.info(f"[SEGMENTATION] Starting segmentation. Video type: {'Vertical' if is_vertical_video else 'Horizontal'}")
    logger.info(f"[SEGMENTATION] Input length: {len(text)} characters")
    logger.debug(f"[SEGMENTATION] Input sample: {text[:100]}{'...' if len(text) > 100 else ''}")
    logger.debug(f"[SEGMENTATION] Has word timing data: {df_words is not None and len(df_words) > 1}")
    
    start_time = time.time()
    
    if not text or not text.strip():
        logger.warning("[SEGMENTATION] Empty input text, returning empty string")
        return [""]
        
    text = text.strip()
    logger.debug(f"[SEGMENTATION] Processing text: {text[:50]}...")
    
    # Define break points that should trigger a split
    # These are more aggressive for splitting, especially for Chinese text
    sentence_enders = {'。', '！', '？', '；', '\n', '……', '……', '...', '……'}
    
    # Common breaks that should split segments
    common_breaks = {
        # Chinese punctuation
        '，', '、', '：', '——', '…', '—', '…', '...', '……',
        # English punctuation (for mixed content)
        ',', ';', ':', '-', '–', '—', '...', '…'
    }
    
    # Chinese conjunctions that can start a new segment
    chinese_conjunctions = {
        # Coordinating conjunctions
        '而且', '并且', '或者', '还是', '可是', '不过', '然而', '因此', '所以', '因为', 
        '由于', '既然', '如果', '要是', '即使', '虽然', '尽管', '不管', '无论', '为了',
        '以便', '以免', '免得', '除非', '除了', '不但', '不仅', '甚至', '就是', '不论',
        '既', '又', '也', '还', '何况', '况且', '于是', '然后', '接着', '从而',
        '以致', '固然', '宁可', '宁愿', '与其', '不如', '不是', '就是', '是', '还是',
        '要么', '首先', '其次', '再次', '最后', '总之', '总而言之',
        # Additional conjunctions
        '然后', '接着', '随后', '后来', '接下来', '与此同时', '与此同时，', '另外', '另外，',
        '此外', '此外，', '相反', '相反，', '例如', '例如，', '比如', '比如，', '比如说', '比如说，'
    }
    
    # Punctuation that should be attached to the previous segment
    attach_to_prev = {',', '，', '.', '。', '!', '！', '?', '？', ';', '；', ':', '：', '、', '…', '...', '……'}
    
    # Initialize segments list
    segments = []
    current_segment = ""
    
    # Combine all break points for checking
    all_breaks = sentence_enders.union(common_breaks)
    
    # First, split by sentence enders to get potential sentences
    temp_segments = []
    current = ""
    
    logger.debug(f"[SEGMENTATION] Splitting text at sentence enders: {sentence_enders}")
    
    i = 0
    while i < len(text):
        char = text[i]
        current += char
        
        # Check for sentence enders
        if char in sentence_enders:
            # Check for multi-character enders like '...' or '……'
            if char in {'.', '…'} and i + 1 < len(text) and text[i+1] in {'.', '…'}:
                # Handle multi-character ellipsis
                current += text[i+1]
                if i + 2 < len(text) and text[i+2] in {'.', '…'}:
                    current += text[i+2]
                    i += 2
                else:
                    i += 1
            
            # Add the current segment and reset
            if current.strip():
                logger.debug(f"[SEGMENTATION] Found sentence ender at position {i}, segment length: {len(current)}")
                temp_segments.append(current.strip())
                current = ""
        
        i += 1
    
    # Add the last segment if not empty
    if current.strip():
        logger.debug(f"[SEGMENTATION] Adding final segment, length: {len(current)}")
        temp_segments.append(current.strip())
    
    # Now split segments further at common breaks (like commas)
    logger.info(f"[SEGMENTATION] Initial split into {len(temp_segments)} segments")
    
    # Process each segment to split at common breaks
    final_segments = []
    for seg in temp_segments:
        # Skip empty segments
        if not seg.strip():
            continue
            
        # Split at common breaks (like commas)
        sub_segments = []
        current_sub = ""
        
        for i, char in enumerate(seg):
            current_sub += char
            
            # Check if this character is a common break that should split the segment
            if char in common_breaks:
                # Don't split if it's part of an ellipsis
                if char in {'.', '…'} and i + 1 < len(seg) and seg[i+1] in {'.', '…'}:
                    continue
                    
                # Add the current sub-segment and reset
                if current_sub.strip():
                    sub_segments.append(current_sub.strip())
                    current_sub = ""
        
        # Add the last sub-segment if not empty
        if current_sub.strip():
            sub_segments.append(current_sub.strip())
        
        # If we didn't split, just add the original segment
        if not sub_segments:
            final_segments.append(seg)
        else:
            final_segments.extend(sub_segments)
    
    # Clean up any empty segments and update temp_segments
    temp_segments = [s for s in final_segments if s.strip()]
    logger.info(f"[SEGMENTATION] After splitting at common breaks: {len(temp_segments)} segments")
    if logger.isEnabledFor(logging.DEBUG):
        for i, seg in enumerate(temp_segments[:5]):  # Log first 5 segments for debugging
            logger.debug(f"[SEGMENTATION]   Segment {i+1}: {seg[:50]}{'...' if len(seg) > 50 else ''}")
        if len(temp_segments) > 5:
            logger.debug(f"[SEGMENTATION]   ... and {len(temp_segments) - 5} more segments")
    
    # Now process each segment to split at conjunctions and length limits
    logger.info("[SEGMENTATION] Starting conjunction-based splitting")
    for seg_idx, segment in enumerate(temp_segments, 1):
        if not segment:
            logger.debug(f"[SEGMENTATION] Segment {seg_idx}: Empty, skipping")
            continue
            
        seg_len = len(segment)
        # Check if the segment is already within length limits
        if seg_len <= 20:
            logger.debug(f"[SEGMENTATION] Segment {seg_idx}: Length {seg_len} <= 20, keeping as is")
            segments.append(segment)
            continue
            
        logger.debug(f"[SEGMENTATION] Processing segment {seg_idx}: Length {seg_len}, content: {segment[:50]}...")
        
        # Otherwise, try to split at conjunctions
        current_subseg = ""
        i = 0
        split_count = 0
        
        while i < len(segment):
            found_conj = False
            # Look for the longest possible conjunction match
            for length in range(4, 0, -1):  # Check for 4-char to 1-char conjunctions
                if i + length > len(segment):
                    continue
                    
                candidate = segment[i:i+length]
                if candidate in chinese_conjunctions or candidate in common_breaks:
                    logger.debug(f"[SEGMENTATION]   Found conjunction/break: '{candidate}' at position {i}")
                    if current_subseg:
                        segments.append(current_subseg)
                        logger.debug(f"[SEGMENTATION]   Added subsegment (len={len(current_subseg)}): {current_subseg[:30]}...")
                        current_subseg = ""
                        split_count += 1
                    
                    current_subseg = candidate
                    i += length
                    found_conj = True
                    break
            
            if not found_conj:
                current_subseg += segment[i]
                i += 1
                
                # Check if we've reached the length limit
                if len(current_subseg) >= 20:
                    # Try to find a natural break point in the last few characters
                    split_pos = len(current_subseg)
                    for j in range(len(current_subseg)-1, max(0, len(current_subseg)-5), -1):
                        if current_subseg[j] in common_breaks or current_subseg[j] in sentence_enders:
                            split_pos = j + 1
                            logger.debug(f"[SEGMENTATION]   Found natural break at position {j}, char: '{current_subseg[j]}'")
                            break
                    
                    if split_pos < len(current_subseg):
                        segments.append(current_subseg[:split_pos].strip())
                        logger.debug(f"[SEGMENTATION]   Split long segment at position {split_pos}")
                        current_subseg = current_subseg[split_pos:].strip()
                        split_count += 1
                    else:
                        segments.append(current_subseg)
                        logger.debug(f"[SEGMENTATION]   Forced split at max length (20)")
                        current_subseg = ""
                        split_count += 1
        
        if current_subseg.strip():
            logger.debug(f"[SEGMENTATION]   Adding final subsegment (len={len(current_subseg)})")
            segments.append(current_subseg.strip())
            
        logger.info(f"[SEGMENTATION] Segment {seg_idx}: Split into {split_count + 1} parts")
    
    # Filter out any empty segments
    segments = [s for s in segments if s.strip()]
    logger.info(f"[SEGMENTATION] After initial segmentation: {len(segments)} segments")
    
    # Log segment statistics before punctuation cleaning
    if segments:
        avg_len = sum(len(s) for s in segments) / len(segments)
        max_len = max(len(s) for s in segments)
        min_len = min(len(s) for s in segments)
        logger.info(
            f"[SEGMENTATION] Pre-clean stats - Segments: {len(segments)}, "
            f"Avg: {avg_len:.1f} chars, Min: {min_len}, Max: {max_len}"
        )
    
    # Clean up segments to ensure proper punctuation handling
    if segments:
        logger.debug("[SEGMENTATION] Cleaning up segments for proper punctuation")
        cleaned_segments = []
        
        # First pass: Clean up each segment individually
        for i, seg in enumerate(segments):
            seg = seg.strip()
            if not seg:
                continue
                
            # Remove any leading or trailing whitespace and punctuation
            seg = seg.strip()
            
            # Remove leading punctuation
            while seg and seg[0] in attach_to_prev:
                logger.debug(f"[SEGMENTATION]   Removing leading punctuation '{seg[0]}' from segment")
                seg = seg[1:].lstrip()
            
            # Remove trailing punctuation (except sentence enders)
            while seg and seg[-1] in {',', '，', ';', '；', ':', '：', '、'}:
                logger.debug(f"[SEGMENTATION]   Removing trailing punctuation '{seg[-1]}' from segment")
                seg = seg[:-1].rstrip()
            
            if seg:
                cleaned_segments.append(seg)
        
        # Second pass: Handle segments that should be attached to previous ones
        final_segments = []
        i = 0
        while i < len(cleaned_segments):
            current = cleaned_segments[i]
            
            # If this is very short and the next segment starts with a conjunction, combine them
            if (i < len(cleaned_segments) - 1 and 
                len(current) <= 10 and 
                any(cleaned_segments[i+1].startswith(conj) for conj in chinese_conjunctions)):
                combined = f"{current} {cleaned_segments[i+1]}"
                logger.debug(f"[SEGMENTATION]   Combined short segment with conjunction: '{combined}'")
                final_segments.append(combined)
                i += 2  # Skip the next segment as we've combined it
            else:
                final_segments.append(current)
                i += 1
        
        segments = [s for s in final_segments if s.strip()]
        logger.info(
            f"[SEGMENTATION] After cleaning punctuation: {len(segments)} segments, "
            f"{punctuation_attached} punctuations attached, {len(cleaned_segments) - len(segments)} segments removed"
        )
        
        # Log detailed segment information in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[SEGMENTATION] Final segments after punctuation cleaning:")
            for i, seg in enumerate(segments[:10]):  # Limit to first 10 segments in debug
                logger.debug(f"[SEGMENTATION]   {i+1:2d}. [{len(seg):2d} chars] {seg[:50]}{'...' if len(seg) > 50 else ''}")
            if len(segments) > 10:
                logger.debug(f"[SEGMENTATION]   ... and {len(segments) - 10} more segments")
    
    # Then split any remaining long segments with character limits
    max_segment_length = 15 if is_vertical_video else 30
    logger.info(f"[SEGMENTATION] Applying max segment length: {max_segment_length} chars")
    
    # Check for segments that need splitting
    long_segments = [(i, seg) for i, seg in enumerate(segments) if len(seg) > max_segment_length]
    
    if long_segments:
        logger.info(f"[SEGMENTATION] Found {len(long_segments)} segments exceeding max length, splitting...")
        for idx, seg in long_segments[:5]:  # Log first 5 long segments
            logger.debug(f"[SEGMENTATION]   Segment {idx+1}: {len(seg)} chars - '{seg[:30]}...'")
        if len(long_segments) > 5:
            logger.debug(f"[SEGMENTATION]   ... and {len(long_segments) - 5} more long segments")
            
        segments = split_long_segments(segments, max_length=max_segment_length)
        logger.info(f"[SEGMENTATION] After splitting long segments: {len(segments)} segments")
    else:
        logger.debug("[SEGMENTATION] No segments exceed max length, skipping split")
    
    # Log segment statistics
    if segments:
        avg_len = sum(len(s) for s in segments) / len(segments)
        max_len = max(len(s) for s in segments)
        min_len = min(len(s) for s in segments)
        logger.info(
            f"[SEGMENTATION] Segment stats - Count: {len(segments)}, "
            f"Avg length: {avg_len:.1f}, Min: {min_len}, Max: {max_len}"
        )
    
    # If we have word-level timing data, we can do more sophisticated segmentation
    if df_words is not None and len(df_words) > 1:
        logger.info(f"[SEGMENTATION] Word-level timing data available: {len(df_words)} words")
        # TODO: Implement more sophisticated segmentation using word timing data
    else:
        logger.debug("[SEGMENTATION] No word-level timing data available")
    
    # For vertical videos, use dedicated formatting function with stricter width limits
    if is_vertical_video:
        logger.info("[SEGMENTATION] Processing for vertical video with strict width limits")
        from .formatting import format_subtitle_for_vertical_video
        combined_text = " ".join(segments)
        logger.debug(f"[SEGMENTATION] Formatting combined text (length: {len(combined_text)}) for vertical video")
        
        start_video_format = time.time()
        segments = format_subtitle_for_vertical_video(combined_text, max_line_width=15)
        video_format_time = time.time() - start_video_format
        
        logger.info(
            f"[SEGMENTATION] Vertical video formatting completed in {video_format_time:.2f}s. "
            f"Final segment count: {len(segments)}"
        )
    
    # Calculate and log processing time
    duration = time.time() - start_time
    logger.info(
        f"[SEGMENTATION] Segmentation completed in {duration:.2f}s. "
        f"Final segment count: {len(segments)}"
    )
    
    # Log sample of final output
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("[SEGMENTATION] Final segmented output:")
        for i, seg in enumerate(segments[:5]):  # Show first 5 segments in debug
            logger.debug(f"[SEGMENTATION]   {i+1:2d}. [{len(seg):2d} chars] {seg}")
        if len(segments) > 5:
            logger.debug(f"[SEGMENTATION]   ... and {len(segments) - 5} more segments")
    
    return segments

def split_translation_by_original(original_text: str, translated_text: str) -> List[str]:
    """
    DEPRECATED: This function is deprecated as it can lead to semantic incompleteness.
    Use smart sentence segmentation instead for better results.
    
    Args:
        original_text: Original subtitle text (unused)
        translated_text: Translated subtitle text
        
    Returns:
        List containing the translated text as a single item to preserve semantics
    """
    import warnings
    warnings.warn(
        "split_translation_by_original is deprecated as it can cause semantic "
        "incompleteness. Use smart sentence segmentation instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return [translated_text] if translated_text else [""]


def process_subtitle_data(df: pd.DataFrame, job_dir: str = None) -> pd.DataFrame:
    """
    Process subtitle data, applying segmentation and formatting
    
    Args:
        df: DataFrame containing subtitle data
        job_dir: Optional job directory for saving intermediate results
        
    Returns:
        Processed DataFrame with optimized subtitles (timing is preserved as original)
    """
    # Apply subtitle segmentation optimization only
    df = optimize_subtitle_segmentation(df)
    
    # Save intermediate results if job_dir is provided
    if job_dir:
        processed_file = os.path.join(job_dir, "log", "processed_subtitles.xlsx")
        os.makedirs(os.path.dirname(processed_file), exist_ok=True)
        df.to_excel(processed_file, index=False)
        logger.info(f"Saved processed subtitles to {processed_file}")
    
    return df


def remove_punctuation(text: str) -> str:
    """
    Remove all punctuation from the input text.
    
    Args:
        text: Input text that may contain punctuation
        
    Returns:
        Text with all punctuation removed
    """
    if not text or not isinstance(text, str):
        return text
        
    # Define punctuation marks to remove (both Chinese and English)
    punctuation_marks = {
        # English punctuation
        '!', '"', '#', '$', '%', '&', '\'', '(', ')', '*', '+', ',', '-', '.', 
        '/', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '_', '`', 
        '{', '|', '}', '~',
        # Chinese punctuation
        '，', '。', '、', '：', '；', '？', '！', '“', '”', '‘', '’', '（', '）', '【', '】',
        '『', '』', '「', '」', '《', '》', '…', '—', '·', '～', '‖', '∶', '＂', '＇', '｀',
        '｜', '〃', '〝', '〞', '〓', '–', '—', '―', '‖', '‥', '…', '‰', '′', '″', '‵',
        '※', '‼', '‽', '‾', '⁇', '⁈', '⁉', '⸮', '⹁', '⺟', '⺠', '⻰', '、', '。', '〃',
        '〄', '〈', '〉', '《', '》', '「', '」', '『', '』', '【', '】', '〔', '〕', '〖', '〗',
        '〘', '〙', '〚', '〛', '〜', '〝', '〞', '〟', '〰', '〾', '〿', '–', '—', '―', '‖',
        '‗', '‘', '’', '‚', '‛', '“', '”', '„', '‟', '†', '‡', '•', '‣', '․', '‥', '…',
        '‧', '‰', '′', '″', '‴', '‵', '‶', '‷', '‸', '‹', '›', '‼', '‽', '‾', '‿', '⁀',
        '⁁', '⁂', '⁃', '⁄', '⁅', '⁆', '⁇', '⁈', '⁉', '⁊', '⁋', '⁌', '⁍', '⁎', '⁏', '⁐',
        '⁑', '⁓', '⁔', '⁕', '⁖', '⁗', '⁘', '⁙', '⁚', '⁛', '⁜', '⁝', '⁞', '⸺', '⸻', '⸼',
        '⸽', '⸾', '⸿', '⹀', '⹁', '⹃', '⹄', '⹅', '⹆', '⹇', '⹈', '⹉', '⹊', '⹋', '⹌', '⹍',
        '⹎', '⹏', '⹐', '⹑', '⹒', '⹓', '⹔', '⹕', '⹖', '⹗', '⹘', '⹙', '⹚', '⹛', '⹜', '⹝',
        '⹞', '⹟', '⹠', '⹡', '⹢', '⹣', '⹤', '⹥', '⹦', '⹧', '⹨', '⹩', '⹪', '⹫', '⹬', '⹭',
        '⹮', '⹯', '⹰', '⹱', '⹲', '⹳', '⹴', '⹵', '⹶', '⹷', '⹸', '⹹', '⹺', '⹻', '⹼', '⹽',
        '⹾', '⹿', '。', '〃', '〄', '々', '〆', '〇', '〈', '〉', '《', '》', '「', '」', '『', '』',
        '【', '】', '〒', '〓', '〔', '〕', '〖', '〗', '〘', '〙', '〚', '〛', '〜', '〝', '〞', '〟',
        '〠', '〡', '〢', '〣', '〤', '〥', '〦', '〧', '〨', '〩', '〪', '〫', '〬', '〭', '〮', '〯',
        '〰', '〱', '〲', '〳', '〴', '〵', '〶', '〷', '〸', '〹', '〺', '〻', '〼', '〽', '〾', '〿'
    }
    
    # Remove all punctuation marks
    clean_text = ''.join(char for char in text if char not in punctuation_marks)
    
    # Remove extra spaces that might be left after removing punctuation
    clean_text = ' '.join(clean_text.split())
    
    return clean_text


def save_references_for_llm(job_dir: str, subtitle_data: Dict) -> str:
    """
    Save subtitle data references for large language models
    
    Args:
        job_dir: Job directory
        subtitle_data: Subtitle data dictionary
        
    Returns:
        Path to the saved reference file
    """
    reference_dir = os.path.join(job_dir, "references")
    os.makedirs(reference_dir, exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    reference_file = os.path.join(reference_dir, f"subtitle_references_{timestamp}.json")
    
    with open(reference_file, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved subtitle references for LLM: {reference_file}")
    return reference_file
