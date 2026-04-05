"""
Quality assessment for translations to ensure high-quality output
"""
from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass
from statistics import mean

logger = logging.getLogger(__name__)

@dataclass
class QualityScores:
    """Stores quality assessment scores"""
    terminology_consistency: float = 0.0
    fluency: float = 0.0
    accuracy: float = 0.0
    style_match: float = 0.0
    overall: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert scores to dictionary"""
        return {
            'terminology_consistency': self.terminology_consistency,
            'fluency': self.fluency,
            'accuracy': self.accuracy,
            'style_match': self.style_match,
            'overall': self.overall
        }

class TranslationQualityAssessor:
    """Assesses translation quality using various metrics"""
    
    def __init__(self):
        self.metrics = {
            'terminology_consistency': 0.0,
            'fluency': 0.0,
            'accuracy': 0.0,
            'style_match': 0.0
        }
    
    def assess_quality(
        self, 
        source: str, 
        translation: str, 
        terminology: Optional[Dict] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assess the quality of a translation
        
        Args:
            source: Source text
            translation: Translated text
            terminology: Dictionary of terms and their translations
            context: Additional context for assessment
            
        Returns:
            Dictionary containing quality scores and feedback
        """
        logger.info("Assessing translation quality...")
        
        # Initialize scores
        scores = QualityScores()
        
        # Calculate individual metrics
        scores.terminology_consistency = self._check_terminology(translation, terminology or {})
        scores.fluency = self._check_fluency(translation)
        scores.accuracy = self._check_accuracy(source, translation)
        scores.style_match = self._check_style(source, translation)
        
        # Calculate overall score (weighted average)
        weights = {
            'terminology_consistency': 0.3,
            'fluency': 0.3,
            'accuracy': 0.3,
            'style_match': 0.1
        }
        
        score_values = [
            scores.terminology_consistency * weights['terminology_consistency'],
            scores.fluency * weights['fluency'],
            scores.accuracy * weights['accuracy'],
            scores.style_match * weights['style_match']
        ]
        
        scores.overall = sum(score for score in score_values if score is not None) / len(score_values)
        
        # Generate feedback
        feedback = self._generate_feedback(scores)
        
        logger.info(f"Quality assessment complete. Overall score: {scores.overall:.2f}")
        
        return {
            'scores': scores.to_dict(),
            'feedback': feedback,
            'needs_review': scores.overall < 0.7  # Flag for human review if score is low
        }
        
    def _check_terminology(self, text: str, terminology: Dict) -> float:
        """Check if terminology is used consistently"""
        if not terminology or 'terms' not in terminology or not terminology['terms']:
            return 1.0  # No terminology to check
            
        terms = terminology['terms']
        if not isinstance(terms, list):
            logger.warning(f"Expected terms to be a list, got {type(terms)}")
            return 0.0
            
        total_terms = len(terms)
        if total_terms == 0:
            return 1.0
            
        matching_terms = 0
        
        for term in terms:
            if not isinstance(term, dict):
                logger.warning(f"Skipping invalid term: {term}")
                continue
                
            source_term = term.get('source', '').lower()
            target_term = term.get('target', '').lower()
            
            if not source_term or not target_term:
                continue
                
            # Check if either source or target term appears in the text
            if source_term in text.lower() or target_term in text.lower():
                matching_terms += 1
        
        score = matching_terms / total_terms if total_terms > 0 else 1.0
        logger.debug(f"Terminology consistency: {score:.2f} ({matching_terms}/{total_terms} terms matched)")
        return score
        
    def _check_fluency(self, text: str) -> float:
        """Check the fluency of the translation"""
        # Basic checks for common fluency issues
        fluency_issues = 0
        
        # Check for repeated words
        words = text.split()
        for i in range(len(words) - 1):
            if words[i].lower() == words[i+1].lower():
                fluency_issues += 1
        
        # Normalize to a score between 0 and 1
        # More issues = lower score
        max_issues = max(1, len(words) // 10)  # Allow 1 issue per 10 words
        score = max(0, 1 - (fluency_issues / max_issues))
        
        logger.debug(f"Fluency score: {score:.2f} (found {fluency_issues} potential issues)")
        return score
        
    def _check_accuracy(self, source: str, translation: str) -> float:
        """Basic accuracy check comparing source and translation"""
        # This is a simple implementation - in production, you'd want to use more sophisticated methods
        # like BLEU, ROUGE, or a fine-tuned model
        
        # Simple length ratio check
        src_len = len(source.split())
        tgt_len = len(translation.split())
        
        if src_len == 0 or tgt_len == 0:
            return 0.0
            
        length_ratio = min(src_len, tgt_len) / max(src_len, tgt_len)
        
        # Basic word overlap (case insensitive)
        src_words = set(word.lower() for word in source.split())
        tgt_words = set(word.lower() for word in translation.split())
        
        if not src_words or not tgt_words:
            return 0.0
            
        overlap = len(src_words & tgt_words)
        word_overlap = overlap / max(len(src_words), 1)
        
        # Combine metrics
        score = (length_ratio * 0.3) + (word_overlap * 0.7)
        logger.debug(f"Accuracy score: {score:.2f} (length_ratio={length_ratio:.2f}, word_overlap={word_overlap:.2f})")
        return score
        
    def _check_style(self, source: str, translation: str) -> float:
        """Basic style matching between source and translation"""
        # This is a placeholder - in production, you'd want to use style transfer metrics
        # or a fine-tuned model to assess style consistency
        
        # Simple checks for formality markers
        formal_markers = ['please', 'kindly', 'would you', 'could you']
        informal_markers = ['hey', 'yo', 'gonna', 'wanna']
        
        src_formal = any(marker in source.lower() for marker in formal_markers)
        src_informal = any(marker in source.lower() for marker in informal_markers)
        
        tgt_formal = any(marker in translation.lower() for marker in formal_markers)
        tgt_informal = any(marker in translation.lower() for marker in informal_markers)
        
        # Style mismatch if formality doesn't match
        if (src_formal and tgt_informal) or (src_informal and tgt_formal):
            logger.debug("Style mismatch detected (formality)")
            return 0.5
            
        return 0.9  # Default high score if no style issues detected
        
    def _generate_feedback(self, scores: QualityScores) -> List[str]:
        """Generate human-readable feedback based on scores"""
        feedback = []
        
        if scores.terminology_consistency < 0.7:
            feedback.append("Terminology consistency could be improved. Consider using consistent terms throughout the translation.")
            
        if scores.fluency < 0.8:
            feedback.append("Translation fluency could be improved. Consider rephrasing for better natural flow.")
            
        if scores.accuracy < 0.8:
            feedback.append("Translation accuracy could be improved. Please verify the meaning matches the source.")
            
        if scores.style_match < 0.7:
            feedback.append("Style consistency could be improved. Ensure the tone matches the source text.")
            
        if not feedback:
            feedback.append("Translation quality is good. No major issues detected.")
            
        return feedback
