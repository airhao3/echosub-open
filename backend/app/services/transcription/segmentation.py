"""
Transcription Segmentation and Alignment Module

This module provides intelligent segmentation of transcription text with semantic awareness
and alignment of timestamps. It's designed to process transcription results into readable
segments while maintaining accurate timing information.
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Union
import numpy as np
from pathlib import Path

# Ensure json module is available in all scopes
json = json

from app.utils.file_path_manager import FilePathManager, FileType

# Try to import logger, fallback to a simple logger if not available
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

@dataclass
class Timestamp:
    """Represents a timestamp with start and end times."""
    start: float
    end: float
    text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Timestamp':
        """Create from dictionary."""
        return cls(
            start=data["start"],
            end=data["end"],
            text=data.get("text", "")
        )

@dataclass
class AlignedSegment:
    """Represents a segment with aligned timestamps."""
    text: str
    start: float
    end: float
    words: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "words": self.words
        }

@dataclass
class SplitCandidate:
    """Represents a potential split point in the text with its score and reason."""
    position: int
    score: int
    reason: str

class TranscriptionSegmenter:
    """
    Handles segmentation of transcription text and alignment of timestamps.
    
    This class provides functionality to:
    1. Split transcription text into meaningful segments
    2. Align timestamps from the original transcription with the segmented text
    3. Save and load segmentation results
    """
    # Phrasal verbs that should be kept together
    PHRASAL_VERBS = [
        'pick up', 'put down', 'turn on', 'turn off', 'look after', 'give up', 
        'break down', 'run out', 'figure out', 'bring up', 'come across', 
        'get over', 'look forward to', 'run into', 'put off', 'take off', 
        'bring about', 'carry out', 'look into'
    ]
    
    # Common idioms that should be kept together
    IDIOMS = [
        'by the way', 'on the other hand', 'as a matter of fact', 'to tell the truth', 
        'believe it or not', 'last but not least', 'in other words', 'for example', 
        'such as', 'so that'
    ]
    
    # Common abbreviations that contain periods but shouldn't be sentence boundaries
    ABBREVIATIONS = [
        'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'vs.', 'etc.', 'i.e.', 'e.g.', 
        'a.m.', 'p.m.', 'u.s.', 'u.k.'
    ]
    
    # Coordinating conjunctions that can start an independent clause
    COORDINATING_CONJUNCTIONS = ['and', 'but', 'or', 'nor', 'for', 'yet', 'so']
    
    # Subordinating conjunctions that introduce dependent clauses
    SUBORDINATING_CONJUNCTIONS = [
        'although', 'because', 'since', 'while', 'when', 'where', 'if', 'unless', 
        'until', 'after', 'before', 'as', 'though', 'whereas'
    ]
    
    # Common prepositions
    PREPOSITIONS = [
        'of', 'in', 'on', 'at', 'with', 'from', 'by', 'about', 'to', 'for', 'than',
        'through', 'over', 'under', 'against'
    ]
    
    # Words that shouldn't appear at the start of a line
    DETERMINERS_AND_ADJECTIVES = [
        'a', 'an', 'the', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'another',
        'any', 'some', 'every', 'each', 'no', 'what', 'which', 'whose',
        'high', 'low', 'big', 'small', 'good', 'bad', 'great', 'new', 'old', 'more', 'less'
    ]

    def split_transcription(self, text: str, max_length: int, flexibility: float = 0.2, recursion_depth: int = 0) -> List[Tuple[str, int]]:
        """
        Core segmentation method that returns a list of (text, split_score) tuples.
        
        Args:
            text: The input text to be segmented
            max_length: Maximum desired length for each segment
            flexibility: Allowed percentage of length flexibility (default: 0.2)
            recursion_depth: Current depth of recursion (used internally)
            
        Returns:
            List of tuples containing (segment_text, split_score)
        """
        flexible_max_length = int(max_length * (1 + flexibility))
        
        # Base case: if text is already short enough, return it as is
        if len(text) <= flexible_max_length:
            return [(text.strip(), 100)]  # Single segment is considered perfect

        # Prevent infinite recursion
        if recursion_depth > 10:
            return self._force_split_with_score(text, max_length)

        # Find all potential split candidates and select the best one in range
        candidates = self._find_split_candidates(text)
        min_split_pos = int(max_length * 0.4)  # Don't split too close to the start
        best_candidate = self._find_best_split_in_range(candidates, min_split_pos, flexible_max_length)

        if best_candidate:
            # Recursively split the remaining text
            part1 = text[:best_candidate.position].strip()
            part2 = text[best_candidate.position:].strip()
            remaining_segments = self.split_transcription(part2, max_length, flexibility, recursion_depth + 1)
            return [(part1, best_candidate.score)] + remaining_segments
        else:
            # If no good split point found, force a split
            return self._force_split_with_score(text, max_length)

    def _force_split_with_score(self, text: str, max_length: int) -> List[Tuple[str, int]]:
        """Force a split and assign a penalty score of -1 to each forced split point."""
        segments = self._force_split(text, max_length)
        if not segments:
            return []
        # All but the last segment are forced splits
        return [(seg, -1) for seg in segments[:-1]] + [(segments[-1], 100)]

    def _find_best_split_in_range(self, candidates: List[SplitCandidate], min_pos: int, max_pos: int) -> Optional[SplitCandidate]:
        """Find the best split candidate within the specified position range."""
        valid_candidates = [c for c in candidates if min_pos <= c.position <= max_pos]
        return max(valid_candidates, key=lambda c: c.score) if valid_candidates else None

    def _force_split(self, text: str, max_length: int) -> List[str]:
        """Force split text at word boundaries to respect max_length."""
        segments = []
        remaining_text = text.strip()
        
        while len(remaining_text) > max_length:
            split_pos = remaining_text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            segment = remaining_text[:split_pos].strip()
            if segment:
                segments.append(segment)
            remaining_text = remaining_text[split_pos:].strip()
            
        if remaining_text:
            segments.append(remaining_text)
            
        return segments

    def process_transcription_lines(self, lines: List[str], max_length: int, flexibility: float) -> List[Tuple[str, int]]:
        """Process multiple lines of transcription text with segmentation."""
        if not lines:
            return []
            
        merged_segments = self._merge_short_lines(lines, max_length)
        final_segments = []
        
        for segment in merged_segments:
            split_tuples = self.split_transcription(segment, max_length, flexibility)
            final_segments.extend(split_tuples)
            
        return [t for t in final_segments if t[0]]

    def _merge_short_lines(self, lines: List[str], max_length: int) -> List[str]:
        """Merge consecutive short lines when appropriate."""
        if not lines:
            return []
            
        merged = []
        current = ""
        
        for line in lines:
            if not current:
                current = line
            else:
                potential = f"{current} {line}"
                if len(potential) < max_length * 1.5 and self._should_merge(current, line):
                    current = potential
                else:
                    merged.append(current)
                    current = line
                    
        if current:
            merged.append(current)
            
        return merged

    def _should_merge(self, line1: str, line2: str) -> bool:
        """Determine if two lines should be merged."""
        line1, line2 = line1.strip(), line2.strip()
        if not line1 or not line2:
            return False
            
        # Existing merge conditions
        if line1.endswith((',', ';', ':')):
            return True
            
        last_word = line1.split()[-1].lower()
        if (last_word in self.COORDINATING_CONJUNCTIONS or 
            last_word in self.PREPOSITIONS):
            return True
            
        if line2[0].islower():
            return True
        
        # Smart name pattern merging - check if line1 looks like a name initial/abbreviation
        # that should connect with a following name
        if self._should_merge_name_pattern(line1, line2):
            return True
            
        return not line1.endswith(('.', '!', '?'))
    
    def _should_merge_name_pattern(self, line1: str, line2: str) -> bool:
        """
        Check if line1 appears to be a name initial/abbreviation that should merge with line2.
        
        Patterns to merge:
        - "J.J." + "Watt..." -> merge
        - "T.J." + "Smith..." -> merge  
        - "Dr." + "Johnson..." -> merge
        - "Mr." + "Brown..." -> merge
        - Single letters ending in period + capitalized name -> merge
        """
        # Check if line1 is very short (likely an initial or title)
        if len(line1) > 10:  # If line1 is too long, unlikely to be just an initial
            return False
        
        # Check if line2 starts with a capitalized word (likely a surname)
        first_word_line2 = line2.split()[0] if line2.split() else ""
        if not first_word_line2 or not first_word_line2[0].isupper():
            return False
        
        # Pattern 1: Double initials like "J.J.", "T.J.", "R.J."
        if re.match(r'^[A-Z]\.[A-Z]\.$', line1):
            return self._looks_like_surname_context(line2)
        
        # Pattern 2: Single initials like "J.", "T.", "R."
        if re.match(r'^[A-Z]\.$', line1):
            return self._looks_like_surname_context(line2)
        
        # Pattern 3: Common titles like "Dr.", "Mr.", "Mrs.", "Ms.", "Prof."
        line1_lower = line1.lower()
        if line1_lower in ['dr.', 'mr.', 'mrs.', 'ms.', 'prof.', 'jr.', 'sr.']:
            return True
        
        # Pattern 4: Short abbreviations that might be part of names
        if len(line1) <= 4 and line1.endswith('.') and line1[:-1].isalpha():
            # Check if the next line looks like it continues a name
            return self._looks_like_surname_context(line2)
        
        return False
    
    def _looks_like_surname_context(self, text: str) -> bool:
        """
        Check if text looks like it starts with a surname and continues in a way
        that suggests it's part of a person's name context.
        """
        if not text:
            return False
        
        words = text.split()
        if not words:
            return False
        
        first_word = words[0]
        
        # Must start with capital letter
        if not first_word[0].isupper():
            return False
        
        # Common surname patterns
        surname_endings = ['son', 'sen', 'ton', 'man', 'berg', 'stein', 'field', 
                          'wood', 'ford', 'land', 'hall', 'well', 'worth', 'ley']
        if any(first_word.lower().endswith(ending) for ending in surname_endings):
            return True
        
        # Check if followed by contextual words suggesting it's a person
        if len(words) > 1:
            second_word = words[1].lower()
            # Action verbs often follow names
            person_context_words = ['was', 'is', 'had', 'has', 'said', 'told', 'went', 'came',
                                   'played', 'works', 'worked', 'will', 'would', 'could',
                                   'wasn\'t', 'isn\'t', 'hadn\'t', 'hasn\'t', 'didn\'t', 'won\'t']
            if second_word in person_context_words:
                return True
        
        # If it's a capitalized word, it's likely a name
        return True

    def _find_split_candidates(self, text: str) -> List[SplitCandidate]:
        """Find all potential split points in the text."""
        candidates = []
        
        for match in re.finditer(r'[.!?,,;: ]', text):
            pos = match.start()
            if not (0 < pos < len(text) - 1):
                continue
                
            char = match.group(0)
            score = 0
            reason = ""
            
            if char in '.!?':
                if not self._is_abbreviation(text, pos):
                    score, reason = 100, "sentence"
            elif char == ',':
                score, reason = 95, "comma"  # High priority for comma splits
            elif char == ';':
                score, reason = 90, "semicolon"
            elif char == ':':
                if not self._is_time(text, pos):
                    score, reason = 85, "colon"
            elif char == ' ':
                next_word = re.match(r'\w+', text[pos+1:])
                if next_word:
                    word = next_word.group(0).lower()
                    if word in self.COORDINATING_CONJUNCTIONS:
                        score, reason = 80, f"conj_{word}"
                    elif word in self.SUBORDINATING_CONJUNCTIONS:
                        score, reason = 75, f"subconj_{word}"
                    elif word in self.PREPOSITIONS:
                        score, reason = 65, f"prep_{word}"
                    else:
                        score, reason = 10, "word"
            
            if score > 0:
                prev_word = re.search(r'\w+\Z', text[:pos])
                if prev_word and prev_word.group(0).lower() in self.DETERMINERS_AND_ADJECTIVES:
                    score = int(score * 0.3)
                    reason += "_penalty"
                
                if not self._in_protected(text, pos):
                    candidates.append(SplitCandidate(pos + 1, score, reason))
        
        return sorted(candidates, key=lambda c: c.position)

    def _is_abbreviation(self, text: str, pos: int) -> bool:
        """Check if a period is part of an abbreviation or name pattern."""
        # Check for numeric patterns (e.g., "1.5")
        if text[pos-1].isdigit():
            next_pos = pos + 1
            while next_pos < len(text) and text[next_pos].isspace():
                next_pos += 1
            if next_pos < len(text) and text[next_pos].isdigit():
                return True
        
        # Check against known abbreviations list
        prefix = text[:pos+1].lower()
        if any(prefix.endswith(abbr) and 
              (len(prefix) == len(abbr) or prefix[-len(abbr)-1].isspace())
              for abbr in self.ABBREVIATIONS):
            return True
        
        # Smart name/initial pattern recognition
        return self._is_name_initial_pattern(text, pos)
    
    def _is_name_initial_pattern(self, text: str, pos: int) -> bool:
        """
        Intelligent detection of name initials and abbreviation patterns.
        
        Patterns detected:
        - Single letter initials: A. B. C.
        - Double letter initials: J.J. T.J. etc.
        - Professional suffixes: Jr. Sr. III.
        - Academic/title abbreviations
        """
        # Get context around the period
        start = max(0, pos - 10)
        end = min(len(text), pos + 20)
        context = text[start:end]
        period_pos_in_context = pos - start
        
        # Check if this is a single letter + period pattern (like "J.")
        if (period_pos_in_context > 0 and 
            context[period_pos_in_context - 1].isalpha() and 
            context[period_pos_in_context - 1].isupper()):
            
            # Check if it's preceded by whitespace, start of text, or another period (for double initials)
            valid_preceding = (
                period_pos_in_context == 1 or  # Start of text
                context[period_pos_in_context - 2].isspace() or  # Preceded by space
                (period_pos_in_context >= 3 and  # Double initial pattern: "J.J."
                 context[period_pos_in_context - 2] == '.' and
                 context[period_pos_in_context - 3].isupper())
            )
            
            if valid_preceding:
                # Look ahead to see what follows
                after_period = period_pos_in_context + 1
                while after_period < len(context) and context[after_period].isspace():
                    after_period += 1
                
                if after_period < len(context):
                    next_char = context[after_period]
                    
                    # Pattern: "J. Watt" - initial followed by surname
                    if (next_char.isupper() and 
                        self._looks_like_surname(context[after_period:])):
                        return True
                    
                    # Pattern: "J.J." - double initial (check if we're at the second period)
                    if (period_pos_in_context >= 3 and
                        context[period_pos_in_context - 2] == '.' and
                        context[period_pos_in_context - 3].isupper()):
                        return True
        
        # Check for common name suffix patterns
        word_before_period = self._get_word_before_position(text, pos)
        if word_before_period:
            word_lower = word_before_period.lower()
            # Professional/familial suffixes
            if word_lower in ['jr', 'sr', 'iii', 'iv', 'ii']:
                return True
            
            # Single uppercase letters (initials)
            if len(word_before_period) == 1 and word_before_period.isupper():
                return True
        
        return False
    
    def _looks_like_surname(self, text_after: str) -> bool:
        """Check if the following text looks like a surname."""
        # Extract the first word after the period
        match = re.match(r'([A-Za-z]+)', text_after)
        if not match:
            return False
        
        word = match.group(1)
        
        # Surname indicators:
        # 1. Capitalized word
        # 2. Common surname patterns
        # 3. Followed by context suggesting it's a person's name
        if word[0].isupper():
            # Look for additional context clues
            remaining_text = text_after[len(word):].strip()
            
            # If followed by words like "said", "was", "is", etc., likely a surname
            name_context_words = ['said', 'was', 'is', 'has', 'had', 'will', 'would', 
                                'played', 'works', 'worked', 'went', 'came', 'told']
            
            first_word_after = remaining_text.split()[0].lower() if remaining_text.split() else ""
            if first_word_after in name_context_words:
                return True
            
            # Common surname endings
            surname_endings = ['son', 'sen', 'ton', 'man', 'berg', 'stein', 'field']
            if any(word.lower().endswith(ending) for ending in surname_endings):
                return True
            
            return True  # Capitalized word is likely a surname
        
        return False
    
    def _get_word_before_position(self, text: str, pos: int) -> Optional[str]:
        """Extract the word immediately before the given position."""
        if pos <= 0:
            return None
        
        # Find the start of the word before the position
        end_pos = pos - 1
        while end_pos >= 0 and text[end_pos].isspace():
            end_pos -= 1
        
        if end_pos < 0:
            return None
        
        start_pos = end_pos
        while start_pos >= 0 and not text[start_pos].isspace():
            start_pos -= 1
        
        return text[start_pos + 1:end_pos + 1] if start_pos < end_pos else None

    def _in_protected(self, text: str, pos: int) -> bool:
        """Check if position is within a protected phrase."""
        text_lower = text.lower()
        for phrase in self.IDIOMS + self.PHRASAL_VERBS:
            for match in re.finditer(re.escape(phrase), text_lower):
                if match.start() < pos < match.end():
                    return True
        return False

    def _is_time(self, text: str, pos: int) -> bool:
        """Check if colon is part of a time format."""
        return (pos > 0 and pos < len(text) - 1 and 
                text[pos-1].isdigit() and text[pos+1].isdigit())

    def evaluate_segmentation(self, segments: List[Tuple[str, int]], min_len: int, max_len: int) -> float:
        """Evaluate the quality of a segmentation."""
        if not segments:
            return 0.0
            
        # Check for fatal flaws
        for seg, _ in segments:
            words = seg.split()
            if not words:
                continue
                
            # Penalize single-letter lines (except 'a', 'i')
            if len(words) == 1 and len(words[0]) == 1 and words[0].lower() not in ['a', 'i']:
                return 1.0 / (segments.count(seg) + 1)
                
            # Penalize lines starting with lowercase function words
            first_word = words[0].lower()
            if first_word in ['is', 'am', 'are', 'was', 'were', 'of', 'at', 'in', 'on', 'to', 'it']:
                return 1.0 / (segments.count(seg) + 1)
        
        # Start with a base score
        score = 50.0
        
        # Add points for good splits
        for seg, split_score in segments[:-1]:
            if split_score == -1:  # Forced split
                score -= 15
            else:
                score += (split_score / 10.0)
        
        # Add points for good lengths
        lengths = [len(seg) for seg, _ in segments]
        for l in lengths:
            if min_len <= l <= max_len:
                score += 2
            elif l < min_len / 2:
                score -= 5
        
        # Penalize length variability
        if len(lengths) > 1:
            score -= np.std(lengths) * 0.5
        
        return max(0, score)
    
    def align_segments_with_timestamps(self, 
                                    segments: List[Tuple[str, int]], 
                                    word_timestamps: List[Dict[str, Any]]) -> List[AlignedSegment]:
        """
        Align segmented text with word-level timestamps using a robust, fuzzy matching algorithm.
        """
        from difflib import SequenceMatcher

        aligned_segments = []
        
        # Validate word_timestamps before processing
        if not word_timestamps or not all('word' in word_data for word_data in word_timestamps):
            logger.error("Word timestamps are missing or invalid.")
            return []

        original_words = [word_data['word'].strip() for word_data in word_timestamps]
        current_search_start_index = 0

        for segment_text, _ in segments:
            if not segment_text.strip():
                continue

            segment_words = segment_text.split()
            if not segment_words:
                continue

            # Use SequenceMatcher to find the best match for the segment in the original text
            matcher = SequenceMatcher(None, original_words[current_search_start_index:], segment_words, autojunk=False)
            match = matcher.find_longest_match(0, len(original_words) - current_search_start_index, 0, len(segment_words))

            if match.size > 0:
                start_index = current_search_start_index + match.a
                end_index = start_index + match.size -1

                # Get the timestamps from the original word_timestamps list
                start_time = word_timestamps[start_index].get('start', 0.0)
                
                # Handle missing 'end' field gracefully
                if 'end' in word_timestamps[end_index]:
                    end_time = word_timestamps[end_index]['end']
                else:
                    # Calculate end time from start + duration, or use next word's start
                    if end_index + 1 < len(word_timestamps) and 'start' in word_timestamps[end_index + 1]:
                        end_time = word_timestamps[end_index + 1]['start']
                    elif 'start' in word_timestamps[end_index]:
                        # Estimate duration (assume ~0.3 seconds per word if no duration info)
                        word_duration = 0.3
                        end_time = word_timestamps[end_index]['start'] + word_duration
                    else:
                        end_time = start_time + 0.3  # Fallback duration
                matched_words_data = word_timestamps[start_index : end_index + 1]

                aligned_segment = AlignedSegment(
                    text=segment_text,
                    start=start_time,
                    end=end_time,
                    words=matched_words_data
                )
                aligned_segments.append(aligned_segment)

                # Update the search start index for the next segment to avoid re-matching
                current_search_start_index = end_index + 1
            else:
                logger.warning(f"Could not align segment: '{segment_text}'")

        return aligned_segments
    
    def process_transcription_file(self, 
                                 context: 'JobContext', # Use JobContext for path management
                                 video_path: str = None,  # Video path for dynamic length calculation
                                 max_length: int = 80,
                                 flexibility: float = 0.2) -> Dict[str, Any]:
        """
        Process a transcription file, performing segmentation and timestamp alignment.
        
        Args:
            context: The job context for resolving file paths.
            video_path: Path to video file for dynamic subtitle length calculation
            max_length: Maximum segment length in characters (fallback if video_path fails)
            flexibility: Allowed flexibility in segment length (0-1)
            
        Returns:
            Dictionary with processing results and paths to output files
        """
        # Get the file manager instance
        file_manager = FilePathManager()
        
        # Dynamic subtitle length calculation based on video orientation
        if video_path:
            max_length = self._get_optimal_subtitle_length(video_path, max_length)
            print(f"Using dynamic subtitle length: {max_length} characters based on video orientation")

        # Get input file paths using the file manager
        txt_path_str = file_manager.get_file_path(context, FileType.TRANSCRIPTION_TXT)
        json_path_str = file_manager.get_file_path(context, FileType.TRANSCRIPTION_JSON)

        # Read input files
        try:
            # Read text file
            txt_path = Path(txt_path_str)
            if not txt_path.exists():
                raise FileNotFoundError(f"Text file not found: {txt_path}")
                
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            if not lines:
                raise ValueError(f"Text file is empty: {txt_path}")
            
            # Read JSON file
            json_path = Path(json_path_str)
            if not json_path.exists():
                raise FileNotFoundError(f"JSON file not found: {json_path}")
                
            with open(json_path, 'r', encoding='utf-8') as f:
                transcription_data = json.load(f)
            
            word_timestamps = []
            if isinstance(transcription_data, list):
                # Case 1: Direct list of segments with words
                logger.info("Processing transcription data as list of segments")
                for segment in transcription_data:
                    if isinstance(segment, dict) and 'words' in segment:
                        word_timestamps.extend(segment['words'])
                logger.info(f"Loaded {len(word_timestamps)} word timestamps from list of segments format")
                
                # Validate and fix word timestamp data
                word_timestamps = self._validate_and_fix_word_timestamps(word_timestamps)
            elif isinstance(transcription_data, dict):
                # Case 2: Dictionary with word_timestamps key
                if 'word_timestamps' in transcription_data:
                    word_timestamps = transcription_data['word_timestamps']
                    logger.info(f"Loaded {len(word_timestamps)} word timestamps from dictionary with word_timestamps key")
                    word_timestamps = self._validate_and_fix_word_timestamps(word_timestamps)
                # Case 3: Dictionary with segments containing words
                elif 'segments' in transcription_data:
                    for segment in transcription_data['segments']:
                        if 'words' in segment:
                            word_timestamps.extend(segment['words'])
                    logger.info(f"Loaded {len(word_timestamps)} word timestamps from dictionary with segments key")
                    word_timestamps = self._validate_and_fix_word_timestamps(word_timestamps)
            
            if not word_timestamps:
                logger.warning(f"No word timestamps found in {json_path}. Available keys: {list(transcription_data.keys()) if isinstance(transcription_data, dict) else 'N/A'}")
                # Fallback: Try to extract words from the text if available (less accurate timestamps)
                if isinstance(transcription_data, dict) and 'text' in transcription_data:
                    logger.info("Attempting to extract words from text content as fallback")
                    text_content_fallback = transcription_data['text']
                    word_timestamps = [{
                        'word': word,
                        'start': 0.0, # Placeholder
                        'end': 0.0,   # Placeholder
                        'score': 0.0  # Placeholder
                    } for word in text_content_fallback.split()]
                    logger.info(f"Extracted {len(word_timestamps)} words from text content as fallback")


        except Exception as e:
            error_msg = f"Error reading input files: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        
        # Perform segmentation and alignment
        try:
            segments = self.process_transcription_lines(lines, max_length, flexibility)
            aligned_segments = self.align_segments_with_timestamps(segments, word_timestamps)
        except Exception as e:
            error_msg = f"Error during segmentation: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        
        # Prepare output data
        output_data = {
            'segments': [segment.to_dict() for segment in aligned_segments],
            'metadata': {
                'original_txt': str(txt_path),
                'original_json': str(json_path),
                'segmentation_params': {
                    'max_length': max_length,
                    'flexibility': flexibility
                }
            }
        }
        
        # Get the output paths for both JSON and TXT files using the file manager
        output_base_path = file_manager.get_file_path(context, FileType.SEGMENTED_TRANSCRIPT)
        output_json_path = Path(output_base_path.replace(".txt", ".json"))
        output_txt_path = Path(output_base_path)

        # Save results
        try:
            # Ensure the directory exists
            output_json_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save JSON file
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            # Save TXT file with only segment text
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                for segment in aligned_segments:
                    f.write(f"{segment.text}\n")
                
            logger.info(f"Segmentation complete. Results saved to {output_json_path} and {output_txt_path}")
            
            return {
                'success': True,
                'output_json': str(output_json_path),
                'output_txt': str(output_txt_path),
                'segment_count': len(aligned_segments)
            }
            
        except Exception as e:
            error_msg = f"Error saving segmentation results to {output_json_path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def _get_optimal_subtitle_length(self, video_path: str, fallback_length: int = 80) -> int:
        """
        Determine optimal subtitle length based on video dimensions and orientation.
        
        Args:
            video_path: Path to the video file
            fallback_length: Default length to use if detection fails
            
        Returns:
            Optimal character length for subtitles
        """
        try:
            from app.services.video_service import VideoService
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Get video metadata using VideoService
            metadata = VideoService.get_video_metadata(video_path)
            
            if not metadata:
                logger.warning(f"Could not get video metadata for {video_path}, using fallback length: {fallback_length}")
                return fallback_length
            
            width = metadata.get('width', 1920)
            height = metadata.get('height', 1080)
            
            if width <= 0 or height <= 0:
                logger.warning(f"Invalid video dimensions ({width}x{height}), using fallback length: {fallback_length}")
                return fallback_length
            
            # Calculate aspect ratio
            aspect_ratio = width / height
            
            # Determine optimal subtitle length based on video orientation
            if aspect_ratio < 0.8:  # Portrait video (like TikTok, Instagram Stories)
                optimal_length = 55  # Increased from 30 to reduce excessive fragmentation
                logger.info(f"Portrait video detected ({width}x{height}, ratio={aspect_ratio:.2f}), using {optimal_length} characters")
            elif aspect_ratio < 1.2:  # Square-ish video
                optimal_length = 65  # Increased from 50 for better content cohesion
                logger.info(f"Square video detected ({width}x{height}, ratio={aspect_ratio:.2f}), using {optimal_length} characters")
            else:  # Landscape video (traditional format)
                optimal_length = 85  # Slightly increased from 80 for better flow
                logger.info(f"Landscape video detected ({width}x{height}, ratio={aspect_ratio:.2f}), using {optimal_length} characters")
                
            return optimal_length
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not determine video orientation for {video_path}: {str(e)}, using fallback length: {fallback_length}")
            return fallback_length
    
    def _validate_and_fix_word_timestamps(self, word_timestamps: List[Dict]) -> List[Dict]:
        """
        Validate and fix word timestamp data to ensure all required fields exist.
        
        Args:
            word_timestamps: List of word timestamp dictionaries
            
        Returns:
            Fixed list of word timestamps with consistent 'start' and 'end' fields
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not word_timestamps:
            return word_timestamps
        
        # Sample first few items to understand the data structure
        sample_size = min(5, len(word_timestamps))
        logger.info(f"Validating word timestamps structure. Sample of {sample_size} items:")
        for i in range(sample_size):
            logger.info(f"  Word {i}: {word_timestamps[i]}")
        
        fixed_timestamps = []
        for i, word_data in enumerate(word_timestamps):
            if not isinstance(word_data, dict):
                logger.warning(f"Skipping non-dict word data at index {i}: {word_data}")
                continue
                
            # Create a copy of the word data
            fixed_word = word_data.copy()
            
            # Ensure 'start' field exists
            if 'start' not in fixed_word:
                if i > 0 and 'end' in fixed_timestamps[-1]:
                    # Use previous word's end time as start
                    fixed_word['start'] = fixed_timestamps[-1]['end']
                else:
                    # Estimate based on position (assume 0.3 seconds per word)
                    fixed_word['start'] = i * 0.3
                logger.warning(f"Added missing 'start' field for word {i}: {fixed_word['start']}")
            
            # Ensure 'end' field exists
            if 'end' not in fixed_word:
                # Try to calculate end time
                if i + 1 < len(word_timestamps) and 'start' in word_timestamps[i + 1]:
                    # Use next word's start time as this word's end time
                    fixed_word['end'] = word_timestamps[i + 1]['start']
                else:
                    # Estimate duration (assume ~0.3 seconds per word)
                    fixed_word['end'] = fixed_word['start'] + 0.3
                logger.warning(f"Added missing 'end' field for word {i}: {fixed_word['end']}")
            
            # Ensure 'word' field exists for matching
            if 'word' not in fixed_word and 'text' in fixed_word:
                fixed_word['word'] = fixed_word['text']
            elif 'word' not in fixed_word:
                fixed_word['word'] = f"word_{i}"  # Fallback word identifier
            
            fixed_timestamps.append(fixed_word)
        
        logger.info(f"Fixed {len(fixed_timestamps)} word timestamps")
        return fixed_timestamps
