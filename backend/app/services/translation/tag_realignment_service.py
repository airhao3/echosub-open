"""
Tag Realignment Service for intelligent subtitle tag positioning.

This service handles the intelligent repositioning of timing tags [N] in translated text
to ensure natural sentence flow while maintaining accurate timing alignment.
"""

import logging
import re
from typing import List, Dict, Tuple, Any
# spacy is imported conditionally in methods that need it
from app.services.translation_providers.yunwu_provider import YunwuTranslationProvider

logger = logging.getLogger(__name__)

class TagRealignmentService:
    """
    Service for intelligently realigning timing tags in translated subtitles.
    
    The core idea is to:
    1. Extract tagged segments from source text
    2. Translate the complete sentence without tags for natural flow
    3. Intelligently redistribute tags based on semantic boundaries
    4. Ensure timing accuracy is maintained
    """
    
    def __init__(self, provider: YunwuTranslationProvider):
        self.provider = provider
        self.nlp_models = {}  # Cache for spacy models
        
    def _load_nlp_model(self, lang: str):
        """spaCy model loading has been removed - not used in current implementation."""
        # Set a None value to indicate fallback should be used
        self.nlp_models[lang] = None
    
    def realign_tagged_segment_group(self, 
                                   tagged_segments: List[str], 
                                   source_lang: str, 
                                   target_lang: str,
                                   **kwargs) -> List[str]:
        """
        Realign a group of consecutive tagged segments for natural translation flow.
        
        Args:
            tagged_segments: List of segments with tags, e.g., ["[7] When BMW bought...", "[8] they had...", "[9] for the 21st century."]
            source_lang: Source language code
            target_lang: Target language code
            **kwargs: Additional context for translation
            
        Returns:
            List of realigned translated segments with tags optimally positioned
        """
        try:
            # Step 1: Extract tags and combine text for natural translation
            combined_text, tag_positions = self._extract_tags_and_combine(tagged_segments)
            
            logger.info(f"[TAG_REALIGNMENT] Processing segment group: {len(tagged_segments)} segments")
            logger.info(f"[TAG_REALIGNMENT] Combined text: {combined_text}")
            logger.info(f"[TAG_REALIGNMENT] Original tag positions: {tag_positions}")
            
            if not combined_text.strip():
                return tagged_segments  # Return original if nothing to translate
            
            # Step 2: Translate the combined text naturally
            translation_result = self.provider.translate(
                combined_text,
                source_lang=source_lang,
                target_lang=target_lang,
                metadata={"type": "natural_translation", "preserve_meaning": True},
                **kwargs
            )
            
            translated_text = translation_result.get("translated_text", "").strip()
            if not translated_text:
                logger.warning("[TAG_REALIGNMENT] Translation returned empty result")
                return tagged_segments
            
            logger.info(f"[TAG_REALIGNMENT] Natural translation: {translated_text}")
            
            # Step 3: Intelligently redistribute tags
            realigned_segments = self._redistribute_tags_intelligently(
                translated_text, 
                tag_positions, 
                target_lang,
                len(tagged_segments)
            )
            
            logger.info(f"[TAG_REALIGNMENT] Realigned segments: {realigned_segments}")
            
            return realigned_segments
            
        except Exception as e:
            logger.error(f"[TAG_REALIGNMENT] Error during realignment: {e}", exc_info=True)
            # Fallback to original segments
            return tagged_segments
    
    def _extract_tags_and_combine(self, tagged_segments: List[str]) -> Tuple[str, List[int]]:
        """
        Extract tags and combine text for natural translation.
        
        Returns:
            Tuple of (combined_text, list_of_tag_numbers)
        """
        combined_parts = []
        tag_positions = []
        
        for segment in tagged_segments:
            # Extract tag and text using regex
            match = re.match(r'^\[(\d+)\]\s*(.*)', segment.strip())
            if match:
                tag_num = int(match.group(1))
                text_part = match.group(2).strip()
                
                tag_positions.append(tag_num)
                if text_part:
                    combined_parts.append(text_part)
            else:
                # No tag found, treat as regular text
                if segment.strip():
                    combined_parts.append(segment.strip())
        
        combined_text = ' '.join(combined_parts)
        return combined_text, tag_positions
    
    def _redistribute_tags_intelligently(self, 
                                       translated_text: str, 
                                       original_tags: List[int], 
                                       target_lang: str,
                                       expected_segments: int) -> List[str]:
        """
        Intelligently redistribute tags in translated text based on semantic boundaries.
        """
        try:
            # Load NLP model for target language
            self._load_nlp_model(target_lang)
            nlp = self.nlp_models[target_lang]
            
            # If spacy model is not available, use fallback
            if nlp is None:
                logger.info("[TAG_REALIGNMENT] Spacy model not available, using fallback redistribution")
                return self._fallback_tag_redistribution(translated_text, original_tags, expected_segments)
            
            # Process the translated text
            doc = nlp(translated_text)
            
            # Find optimal split points based on linguistic analysis
            split_points = self._find_optimal_split_points(doc, expected_segments)
            
            # Split the translated text at these points
            text_segments = self._split_text_at_points(translated_text, split_points)
            
            # Ensure we have the right number of segments
            text_segments = self._adjust_segment_count(text_segments, expected_segments)
            
            # Assign tags to segments
            realigned_segments = []
            for i, tag_num in enumerate(original_tags):
                if i < len(text_segments):
                    text = text_segments[i].strip()
                    if text:
                        realigned_segments.append(f"[{tag_num}] {text}")
                    else:
                        realigned_segments.append(f"[{tag_num}]")  # Empty segment
                else:
                    # More tags than text segments, create empty segment
                    realigned_segments.append(f"[{tag_num}]")
            
            return realigned_segments
            
        except Exception as e:
            logger.error(f"Error in tag redistribution: {e}")
            # Fallback: naive split by length
            return self._fallback_tag_redistribution(translated_text, original_tags, expected_segments)
    
    def _find_optimal_split_points(self, doc, expected_segments: int) -> List[int]:
        """
        Find optimal points to split the translated text based on linguistic analysis.
        
        Priority order:
        1. Sentence boundaries
        2. Clause boundaries (marked by conjunctions, punctuation)
        3. Phrase boundaries
        4. Word boundaries (as last resort)
        """
        if expected_segments <= 1:
            return []
        
        # Collect potential split points with scores
        split_candidates = []
        
        # Add sentence boundaries (highest priority)
        for sent in doc.sents:
            if sent.end < len(doc):
                split_candidates.append({
                    'position': sent.end_char,
                    'score': 100,  # Highest priority
                    'type': 'sentence'
                })
        
        # Add clause boundaries (conjunctions, punctuation)
        for token in doc:
            if token.pos_ in ['CCONJ', 'SCONJ'] or token.text in [',', ';', ':', '，', '；', '：']:
                split_candidates.append({
                    'position': token.idx + len(token.text),
                    'score': 80,
                    'type': 'clause'
                })
        
        # Add phrase boundaries
        for chunk in doc.noun_chunks:
            split_candidates.append({
                'position': chunk.end_char,
                'score': 60,
                'type': 'phrase'
            })
        
        # Sort by position
        split_candidates.sort(key=lambda x: x['position'])
        
        # Select best split points
        if not split_candidates:
            # Fallback to equal length splits
            text_len = len(doc.text)
            segment_len = text_len // expected_segments
            return [i * segment_len for i in range(1, expected_segments)]
        
        # Use a greedy approach to select split points
        selected_splits = []
        target_positions = []
        text_len = len(doc.text)
        
        # Calculate target positions for splits
        for i in range(1, expected_segments):
            target_pos = (text_len * i) // expected_segments
            target_positions.append(target_pos)
        
        # For each target position, find the best nearby split point
        for target_pos in target_positions:
            best_candidate = None
            best_distance = float('inf')
            
            for candidate in split_candidates:
                # Skip if already selected
                if candidate['position'] in selected_splits:
                    continue
                
                # Calculate distance to target position
                distance = abs(candidate['position'] - target_pos)
                
                # Prefer higher scores (sentence > clause > phrase)
                adjusted_distance = distance - (candidate['score'] / 10)
                
                if adjusted_distance < best_distance:
                    best_distance = adjusted_distance
                    best_candidate = candidate
            
            if best_candidate:
                selected_splits.append(best_candidate['position'])
        
        return sorted(selected_splits)
    
    def _split_text_at_points(self, text: str, split_points: List[int]) -> List[str]:
        """Split text at specified character positions."""
        if not split_points:
            return [text]
        
        segments = []
        start = 0
        
        for split_point in split_points:
            if split_point > start and split_point <= len(text):
                segment = text[start:split_point].strip()
                if segment:
                    segments.append(segment)
                start = split_point
        
        # Add the final segment
        final_segment = text[start:].strip()
        if final_segment:
            segments.append(final_segment)
        
        return segments
    
    def _adjust_segment_count(self, segments: List[str], expected_count: int) -> List[str]:
        """Adjust the number of segments to match expected count."""
        if len(segments) == expected_count:
            return segments
        
        if len(segments) < expected_count:
            # Too few segments - split the longest ones
            while len(segments) < expected_count:
                # Find the longest segment
                longest_idx = max(range(len(segments)), key=lambda i: len(segments[i]))
                longest_segment = segments[longest_idx]
                
                # Split it roughly in half
                mid_point = len(longest_segment) // 2
                # Find a good split point near the middle (prefer spaces)
                split_pos = mid_point
                for offset in range(min(20, mid_point)):  # Look within 20 chars
                    if mid_point + offset < len(longest_segment) and longest_segment[mid_point + offset] == ' ':
                        split_pos = mid_point + offset
                        break
                    if mid_point - offset >= 0 and longest_segment[mid_point - offset] == ' ':
                        split_pos = mid_point - offset
                        break
                
                # Split the segment
                first_part = longest_segment[:split_pos].strip()
                second_part = longest_segment[split_pos:].strip()
                
                segments[longest_idx:longest_idx+1] = [first_part, second_part]
        
        elif len(segments) > expected_count:
            # Too many segments - merge the shortest ones
            while len(segments) > expected_count:
                # Find two adjacent segments with minimum combined length
                min_combined_len = float('inf')
                merge_idx = 0
                
                for i in range(len(segments) - 1):
                    combined_len = len(segments[i]) + len(segments[i + 1])
                    if combined_len < min_combined_len:
                        min_combined_len = combined_len
                        merge_idx = i
                
                # Merge the segments
                merged_segment = f"{segments[merge_idx]} {segments[merge_idx + 1]}".strip()
                segments[merge_idx:merge_idx+2] = [merged_segment]
        
        return segments
    
    def _fallback_tag_redistribution(self, translated_text: str, original_tags: List[int], expected_segments: int) -> List[str]:
        """
        Fallback method for tag redistribution using simple length-based splitting.
        """
        if expected_segments <= 1:
            return [f"[{original_tags[0]}] {translated_text}"] if original_tags else [translated_text]
        
        # Simple length-based split
        text_length = len(translated_text)
        segment_length = text_length // expected_segments
        
        segments = []
        start = 0
        
        for i in range(expected_segments - 1):
            end = start + segment_length
            # Try to find a word boundary near the end point
            while end < text_length and translated_text[end] != ' ':
                end += 1
            
            segment_text = translated_text[start:end].strip()
            segments.append(segment_text)
            start = end
        
        # Add the final segment
        final_segment = translated_text[start:].strip()
        segments.append(final_segment)
        
        # Assign tags
        result = []
        for i, tag_num in enumerate(original_tags):
            if i < len(segments):
                text = segments[i]
                if text:
                    result.append(f"[{tag_num}] {text}")
                else:
                    result.append(f"[{tag_num}]")
            else:
                result.append(f"[{tag_num}]")
        
        return result
    
    def should_apply_realignment(self, tagged_segments: List[str]) -> bool:
        """
        Determine if a group of segments would benefit from tag realignment.
        
        Criteria:
        1. Multiple consecutive tagged segments (2+)
        2. Segments appear to be part of the same sentence/thought
        3. Current tag positions create unnatural breaks
        """
        if len(tagged_segments) < 2:
            return False
        
        # Extract text content
        text_parts = []
        for segment in tagged_segments:
            match = re.match(r'^\[(\d+)\]\s*(.*)', segment.strip())
            if match:
                text_part = match.group(2).strip()
                text_parts.append(text_part)
        
        if not text_parts:
            return False
        
        # Check if segments form a coherent sentence/thought
        combined_text = ' '.join(text_parts)
        
        # Simple heuristics for sentence coherence
        # 1. First segment doesn't end with sentence-ending punctuation
        first_text = text_parts[0].strip()
        if first_text and first_text[-1] in '.!?。！？':
            return False  # First segment is complete, no need to realign
        
        # 2. Combined text forms a more complete thought
        if len(combined_text.split()) >= 6:  # Reasonable sentence length
            return True
        
        # 3. Check for sentence continuation indicators
        sentence_continuations = ['and', 'but', 'or', 'for', 'so', 'yet', 'nor', 'they', 'it', 'to']
        for text_part in text_parts[1:]:
            first_words = text_part.lower().split()[:2]
            if any(word in sentence_continuations for word in first_words):
                return True
        
        return False