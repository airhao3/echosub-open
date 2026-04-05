#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Translation Result Adjuster
Post-translation optimization and quality enhancement system
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AdjustmentType(Enum):
    """Types of translation adjustments"""
    LENGTH_OPTIMIZATION = "length_optimization"
    READABILITY_IMPROVEMENT = "readability_improvement"
    CONSISTENCY_ENFORCEMENT = "consistency_enforcement"
    CULTURAL_ADAPTATION = "cultural_adaptation"
    TIMING_SYNCHRONIZATION = "timing_synchronization"
    QUALITY_ENHANCEMENT = "quality_enhancement"

@dataclass
class AdjustmentRule:
    """Rule for translation adjustment"""
    rule_type: AdjustmentType
    priority: int  # 1-10, higher is more important
    condition: str  # Description of when to apply
    action: str    # Description of what to do

@dataclass
class TranslationSegment:
    """Single translation segment with metadata"""
    original_text: str
    translated_text: str
    start_time: float
    end_time: float
    speaker_id: Optional[str] = None
    confidence: float = 1.0
    adjustments_applied: List[str] = None

    def __post_init__(self):
        if self.adjustments_applied is None:
            self.adjustments_applied = []

class TranslationResultAdjuster:
    """
    Comprehensive translation result adjustment and optimization system
    """
    
    def __init__(self):
        """Initialize the result adjuster with rules and patterns"""
        self.adjustment_rules = self._initialize_adjustment_rules()
        self.common_issues = self._initialize_common_issues()
        self.cultural_adaptations = self._initialize_cultural_adaptations()
        self.quality_thresholds = {
            'min_readability': 0.6,
            'max_wps': 3.5,  # words per second
            'min_display_time': 1.0,  # minimum seconds on screen
            'max_line_length': {'portrait': 55, 'landscape': 85, 'square': 65}
        }
    
    def _initialize_adjustment_rules(self) -> List[AdjustmentRule]:
        """Initialize standard adjustment rules"""
        return [
            # Length optimization rules
            AdjustmentRule(
                rule_type=AdjustmentType.LENGTH_OPTIMIZATION,
                priority=9,
                condition="Translation exceeds optimal character limit for video format",
                action="Compress while preserving core meaning"
            ),
            AdjustmentRule(
                rule_type=AdjustmentType.TIMING_SYNCHRONIZATION,
                priority=8,
                condition="Reading speed exceeds comfortable rate",
                action="Adjust text density or split segments"
            ),
            
            # Readability improvement rules
            AdjustmentRule(
                rule_type=AdjustmentType.READABILITY_IMPROVEMENT,
                priority=7,
                condition="Complex sentence structure or vocabulary",
                action="Simplify while maintaining accuracy"
            ),
            
            # Consistency enforcement rules
            AdjustmentRule(
                rule_type=AdjustmentType.CONSISTENCY_ENFORCEMENT,
                priority=6,
                condition="Inconsistent terminology across segments",
                action="Apply consistent terminology mapping"
            ),
            
            # Cultural adaptation rules
            AdjustmentRule(
                rule_type=AdjustmentType.CULTURAL_ADAPTATION,
                priority=5,
                condition="Cultural references need localization",
                action="Adapt or explain cultural elements"
            ),
            
            # Quality enhancement rules
            AdjustmentRule(
                rule_type=AdjustmentType.QUALITY_ENHANCEMENT,
                priority=4,
                condition="Translation quality below threshold",
                action="Enhance natural flow and accuracy"
            )
        ]
    
    def _initialize_common_issues(self) -> Dict[str, Dict[str, Any]]:
        """Initialize common translation issues and fixes"""
        return {
            'repeated_words': {
                'pattern': r'\b(\w+)\s+\1\b',
                'fix': r'\1',
                'description': 'Remove repeated words'
            },
            'excessive_punctuation': {
                'pattern': r'[!]{2,}',
                'fix': '!',
                'description': 'Normalize excessive exclamation marks'
            },
            'multiple_spaces': {
                'pattern': r'\s{2,}',
                'fix': ' ',
                'description': 'Normalize multiple spaces'
            },
            'trailing_punctuation': {
                'pattern': r'([,.;:])\s*$',
                'fix': '',
                'description': 'Remove trailing punctuation for subtitles'
            },
            'orphaned_articles': {
                'pattern': r'\b(a|an|the)\s*$',
                'fix': '',
                'description': 'Remove orphaned articles at line end'
            }
        }
    
    def _initialize_cultural_adaptations(self) -> Dict[str, Dict[str, str]]:
        """Initialize cultural adaptation mappings"""
        return {
            'zh': {  # Chinese adaptations
                'measurements': {
                    r'\b(\d+\.?\d*)\s*feet\b': r'\1英尺',
                    r'\b(\d+\.?\d*)\s*inches\b': r'\1英寸',
                    r'\b(\d+\.?\d*)\s*miles\b': r'\1英里',
                    r'\b(\d+\.?\d*)\s*pounds\b': r'\1磅'
                },
                'currency': {
                    r'\$(\d+\.?\d*)': r'\1美元',
                    r'(\d+\.?\d*)\s*dollars': r'\1美元'
                }
            }
        }
    
    def adjust_translation_results(
        self,
        segments: List[TranslationSegment],
        target_lang: str,
        video_format: Dict[str, Any],
        optimization_level: int = 3
    ) -> List[TranslationSegment]:
        """
        Adjust translation results for optimal quality
        
        Args:
            segments: List of translation segments to adjust
            target_lang: Target language code
            video_format: Video format information (aspect ratio, etc.)
            optimization_level: 1-5, higher means more aggressive optimization
            
        Returns:
            List of adjusted translation segments
        """
        logger.info(f"Starting translation adjustment for {len(segments)} segments, level {optimization_level}")
        
        adjusted_segments = []
        terminology_map = self._extract_terminology_consistency(segments)
        
        for i, segment in enumerate(segments):
            adjusted_segment = self._adjust_single_segment(
                segment=segment,
                segment_index=i,
                total_segments=len(segments),
                target_lang=target_lang,
                video_format=video_format,
                optimization_level=optimization_level,
                terminology_map=terminology_map
            )
            adjusted_segments.append(adjusted_segment)
        
        # Cross-segment adjustments
        adjusted_segments = self._apply_cross_segment_adjustments(
            adjusted_segments, target_lang, video_format
        )
        
        # Generate adjustment report
        self._generate_adjustment_report(segments, adjusted_segments)
        
        return adjusted_segments
    
    def _adjust_single_segment(
        self,
        segment: TranslationSegment,
        segment_index: int,
        total_segments: int,
        target_lang: str,
        video_format: Dict[str, Any],
        optimization_level: int,
        terminology_map: Dict[str, str]
    ) -> TranslationSegment:
        """Adjust a single translation segment"""
        
        adjusted_segment = TranslationSegment(
            original_text=segment.original_text,
            translated_text=segment.translated_text,
            start_time=segment.start_time,
            end_time=segment.end_time,
            speaker_id=segment.speaker_id,
            confidence=segment.confidence,
            adjustments_applied=segment.adjustments_applied.copy()
        )
        
        # Apply adjustments in priority order
        for rule in sorted(self.adjustment_rules, key=lambda x: x.priority, reverse=True):
            if optimization_level >= rule.priority // 2:  # Apply based on optimization level
                adjusted_segment = self._apply_adjustment_rule(
                    adjusted_segment, rule, target_lang, video_format, terminology_map
                )
        
        return adjusted_segment
    
    def _apply_adjustment_rule(
        self,
        segment: TranslationSegment,
        rule: AdjustmentRule,
        target_lang: str,
        video_format: Dict[str, Any],
        terminology_map: Dict[str, str]
    ) -> TranslationSegment:
        """Apply a specific adjustment rule to a segment"""
        
        original_text = segment.translated_text
        
        if rule.rule_type == AdjustmentType.LENGTH_OPTIMIZATION:
            segment.translated_text = self._optimize_length(
                segment, video_format
            )
            
        elif rule.rule_type == AdjustmentType.TIMING_SYNCHRONIZATION:
            segment.translated_text = self._synchronize_timing(
                segment
            )
            
        elif rule.rule_type == AdjustmentType.READABILITY_IMPROVEMENT:
            segment.translated_text = self._improve_readability(
                segment.translated_text, target_lang
            )
            
        elif rule.rule_type == AdjustmentType.CONSISTENCY_ENFORCEMENT:
            segment.translated_text = self._enforce_consistency(
                segment.translated_text, terminology_map
            )
            
        elif rule.rule_type == AdjustmentType.CULTURAL_ADAPTATION:
            segment.translated_text = self._adapt_culturally(
                segment.translated_text, target_lang
            )
            
        elif rule.rule_type == AdjustmentType.QUALITY_ENHANCEMENT:
            segment.translated_text = self._enhance_quality(
                segment.translated_text, target_lang
            )
        
        # Record if adjustment was made
        if segment.translated_text != original_text:
            segment.adjustments_applied.append(f"{rule.rule_type.value}")
            logger.debug(f"Applied {rule.rule_type.value} to segment at {segment.start_time}s")
        
        return segment
    
    def _optimize_length(
        self, segment: TranslationSegment, video_format: Dict[str, Any]
    ) -> str:
        """Optimize translation length based on video format"""
        
        aspect_ratio = video_format.get('aspect_ratio', 1.78)
        
        # Determine max characters based on format
        if aspect_ratio < 0.8:  # Portrait
            max_chars = self.quality_thresholds['max_line_length']['portrait']
        elif aspect_ratio > 1.5:  # Landscape
            max_chars = self.quality_thresholds['max_line_length']['landscape']
        else:  # Square
            max_chars = self.quality_thresholds['max_line_length']['square']
        
        text = segment.translated_text
        
        if len(text) <= max_chars:
            return text
        
        # Try to compress while preserving meaning
        compressed = self._compress_text_intelligently(text, max_chars)
        
        return compressed
    
    def _compress_text_intelligently(self, text: str, max_chars: int) -> str:
        """Compress text while preserving core meaning"""
        
        if len(text) <= max_chars:
            return text
        
        # Strategy 1: Remove redundant words
        compressed = self._remove_redundant_words(text)
        if len(compressed) <= max_chars:
            return compressed
        
        # Strategy 2: Shorten phrases
        compressed = self._shorten_common_phrases(compressed)
        if len(compressed) <= max_chars:
            return compressed
        
        # Strategy 3: Simplify complex sentences
        compressed = self._simplify_sentences(compressed)
        if len(compressed) <= max_chars:
            return compressed
        
        # Strategy 4: Truncate with ellipsis (last resort)
        if len(text) > max_chars - 3:
            return text[:max_chars-3] + "..."
        
        return text
    
    def _remove_redundant_words(self, text: str) -> str:
        """Remove redundant or filler words"""
        redundant_patterns = [
            r'\b(really|actually|basically|literally|just|simply|quite|rather|very|extremely)\s+',
            r'\b(I think|I believe|I guess|I suppose)\s+',
            r'\b(you know|you see|well)\s*,?\s*'
        ]
        
        result = text
        for pattern in redundant_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def _shorten_common_phrases(self, text: str) -> str:
        """Shorten common phrases and expressions"""
        shortenings = {
            r'\bin order to\b': 'to',
            r'\bdue to the fact that\b': 'because',
            r'\bat the present time\b': 'now',
            r'\bin the event that\b': 'if',
            r'\bfor the reason that\b': 'because',
            r'\bin spite of the fact that\b': 'although',
            r'\bit is important to note that\b': '',
            r'\bit should be mentioned that\b': ''
        }
        
        result = text
        for long_phrase, short_phrase in shortenings.items():
            result = re.sub(long_phrase, short_phrase, result, flags=re.IGNORECASE)
        
        return result.strip()
    
    def _simplify_sentences(self, text: str) -> str:
        """Simplify complex sentence structures"""
        # Split long sentences at appropriate points
        sentences = re.split(r'[.!?]+', text)
        simplified_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If sentence is too long, try to split at conjunctions
            if len(sentence) > 60:
                # Split at coordinating conjunctions
                parts = re.split(r'\s+(and|but|or|so|yet)\s+', sentence)
                if len(parts) > 1:
                    # Take the most important part (usually first)
                    simplified_sentences.append(parts[0].strip())
                else:
                    simplified_sentences.append(sentence)
            else:
                simplified_sentences.append(sentence)
        
        return '. '.join(simplified_sentences) if simplified_sentences else text
    
    def _synchronize_timing(self, segment: TranslationSegment) -> str:
        """Adjust text for optimal timing synchronization"""
        
        duration = segment.end_time - segment.start_time
        words = segment.translated_text.split()
        current_wps = len(words) / duration if duration > 0 else 0
        
        max_wps = self.quality_thresholds['max_wps']
        
        if current_wps <= max_wps:
            return segment.translated_text
        
        # Need to reduce word density
        target_words = int(duration * max_wps)
        
        if target_words < len(words):
            # Compress to fit timing
            compressed = self._compress_text_intelligently(
                segment.translated_text, 
                target_words * 6  # Approximate characters per word
            )
            return compressed
        
        return segment.translated_text
    
    def _improve_readability(self, text: str, target_lang: str) -> str:
        """Improve text readability"""
        
        # Apply common readability fixes
        improved = text
        
        for issue_name, issue_info in self.common_issues.items():
            pattern = issue_info['pattern']
            replacement = issue_info['fix']
            improved = re.sub(pattern, replacement, improved)
        
        # Language-specific readability improvements
        if target_lang.startswith('zh'):
            improved = self._improve_chinese_readability(improved)
        elif target_lang.startswith('en'):
            improved = self._improve_english_readability(improved)
        
        return improved.strip()
    
    def _improve_chinese_readability(self, text: str) -> str:
        """Chinese-specific readability improvements"""
        # Remove unnecessary spaces in Chinese text
        improved = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)
        
        # Fix punctuation spacing
        improved = re.sub(r'\s*([，。！？；：])\s*', r'\1', improved)
        
        return improved
    
    def _improve_english_readability(self, text: str) -> str:
        """English-specific readability improvements"""
        # Ensure proper spacing after punctuation
        improved = re.sub(r'([.!?])\s*', r'\1 ', text)
        
        # Fix contractions
        improved = re.sub(r'\s+(\'\w+)', r'\1', improved)
        
        return improved.strip()
    
    def _enforce_consistency(self, text: str, terminology_map: Dict[str, str]) -> str:
        """Enforce terminology consistency"""
        
        consistent_text = text
        
        for source_term, preferred_translation in terminology_map.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(source_term) + r'\b'
            consistent_text = re.sub(
                pattern, preferred_translation, consistent_text, flags=re.IGNORECASE
            )
        
        return consistent_text
    
    def _adapt_culturally(self, text: str, target_lang: str) -> str:
        """Apply cultural adaptations"""
        
        if target_lang not in self.cultural_adaptations:
            return text
        
        adapted_text = text
        adaptations = self.cultural_adaptations[target_lang]
        
        for category, patterns in adaptations.items():
            for pattern, replacement in patterns.items():
                adapted_text = re.sub(pattern, replacement, adapted_text)
        
        return adapted_text
    
    def _enhance_quality(self, text: str, target_lang: str) -> str:
        """General quality enhancements"""
        
        enhanced = text
        
        # Fix capitalization issues
        enhanced = self._fix_capitalization(enhanced)
        
        # Improve punctuation
        enhanced = self._improve_punctuation(enhanced)
        
        # Remove artifacts
        enhanced = self._remove_translation_artifacts(enhanced)
        
        return enhanced
    
    def _fix_capitalization(self, text: str) -> str:
        """Fix common capitalization issues"""
        # Capitalize first letter of sentences
        sentences = re.split(r'([.!?]+\s*)', text)
        fixed_sentences = []
        
        for sentence in sentences:
            if sentence.strip() and not re.match(r'^[.!?\s]+$', sentence):
                sentence = sentence[0].upper() + sentence[1:] if sentence else sentence
            fixed_sentences.append(sentence)
        
        return ''.join(fixed_sentences)
    
    def _improve_punctuation(self, text: str) -> str:
        """Improve punctuation usage"""
        # Ensure proper spacing around punctuation
        improved = re.sub(r'\s*([,;:])\s*', r'\1 ', text)
        improved = re.sub(r'\s*([.!?])\s*', r'\1 ', improved)
        
        # Fix quotation marks
        improved = re.sub(r'\s*"\s*', '"', improved)
        
        return improved.strip()
    
    def _remove_translation_artifacts(self, text: str) -> str:
        """Remove common translation artifacts"""
        artifacts = [
            r'\[TRANSLATION\]',
            r'\[ORIGINAL\]',
            r'\[NOTE:.*?\]',
            r'\(Translation:.*?\)',
            r'\*.*?\*',  # Remove asterisk notes
        ]
        
        clean_text = text
        for artifact in artifacts:
            clean_text = re.sub(artifact, '', clean_text, flags=re.IGNORECASE)
        
        return clean_text.strip()
    
    def _extract_terminology_consistency(
        self, segments: List[TranslationSegment]
    ) -> Dict[str, str]:
        """Extract consistent terminology mapping from all segments"""
        
        # Simple frequency-based approach
        term_variants = {}
        
        # This is a simplified approach - in practice, you'd want more sophisticated
        # terminology extraction and consistency checking
        
        return {}  # Placeholder for now
    
    def _apply_cross_segment_adjustments(
        self,
        segments: List[TranslationSegment],
        target_lang: str,
        video_format: Dict[str, Any]
    ) -> List[TranslationSegment]:
        """Apply adjustments that require cross-segment analysis"""
        
        # Smooth transitions between segments
        for i in range(1, len(segments)):
            segments[i] = self._smooth_transition(segments[i-1], segments[i])
        
        # Ensure consistent speaker voice
        segments = self._ensure_speaker_consistency(segments, target_lang)
        
        return segments
    
    def _smooth_transition(
        self,
        prev_segment: TranslationSegment,
        current_segment: TranslationSegment
    ) -> TranslationSegment:
        """Smooth transitions between consecutive segments"""
        
        # Check for abrupt topic changes or inconsistent tone
        # This is a placeholder for more sophisticated transition smoothing
        
        return current_segment
    
    def _ensure_speaker_consistency(
        self, segments: List[TranslationSegment], target_lang: str
    ) -> List[TranslationSegment]:
        """Ensure consistent translation style per speaker"""
        
        speaker_styles = {}
        
        # Group segments by speaker
        for segment in segments:
            if segment.speaker_id:
                if segment.speaker_id not in speaker_styles:
                    speaker_styles[segment.speaker_id] = []
                speaker_styles[segment.speaker_id].append(segment)
        
        # Apply consistent style per speaker (placeholder)
        return segments
    
    def _generate_adjustment_report(
        self,
        original_segments: List[TranslationSegment],
        adjusted_segments: List[TranslationSegment]
    ) -> Dict[str, Any]:
        """Generate a report of adjustments made"""
        
        total_adjustments = sum(
            len(seg.adjustments_applied) for seg in adjusted_segments
        )
        
        adjustment_types = {}
        for segment in adjusted_segments:
            for adjustment in segment.adjustments_applied:
                adjustment_types[adjustment] = adjustment_types.get(adjustment, 0) + 1
        
        # Calculate improvement metrics
        avg_length_before = sum(len(seg.translated_text) for seg in original_segments) / len(original_segments)
        avg_length_after = sum(len(seg.translated_text) for seg in adjusted_segments) / len(adjusted_segments)
        
        report = {
            'total_segments': len(original_segments),
            'segments_adjusted': sum(1 for seg in adjusted_segments if seg.adjustments_applied),
            'total_adjustments': total_adjustments,
            'adjustment_breakdown': adjustment_types,
            'length_optimization': {
                'avg_length_before': avg_length_before,
                'avg_length_after': avg_length_after,
                'compression_ratio': avg_length_after / avg_length_before if avg_length_before > 0 else 1.0
            }
        }
        
        logger.info(f"Translation adjustment report: {report}")
        return report