"""
Enhanced translation service with context awareness and quality assessment
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .context_manager import TranslationContext
from .quality_assessment import TranslationQualityAssessor, QualityScores

logger = logging.getLogger(__name__)

class EnhancedTranslator:
    """
    Enhanced translation service with context awareness, terminology management,
    and quality assessment capabilities.
    """
    
    def __init__(self, base_translation_service):
        """
        Initialize the enhanced translator.
        
        Args:
            base_translation_service: The underlying translation service to use
        """
        self.base_service = base_translation_service
        self.context = TranslationContext()
        self.quality_assessor = TranslationQualityAssessor()
        self.terminology: Dict = {}
        logger.info("EnhancedTranslator initialized")
    
    def translate_with_context(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        next_segment: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Translate text with context awareness and quality assessment.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            next_segment: Optional next segment for context
            metadata: Additional metadata for the translation
            
        Returns:
            Dictionary containing translation and quality information
        """
        logger.info(f"Starting context-aware translation: {source_lang} -> {target_lang}")
        logger.debug(f"Input text length: {len(text)} characters")
        
        # Update context with current and next segment
        self.context.update_context(text, next_segment)
        
        try:
            # Build enhanced prompt with context
            prompt = self._build_enhanced_prompt(text, source_lang, target_lang)
            
            # Call the base translation service
            logger.debug("Calling base translation service...")
            start_time = datetime.utcnow()
            
            translation_result = self.base_service.translate_text(
                prompt,
                source_lang=source_lang,
                target_lang=target_lang,
                metadata=metadata or {}
            )
            
            translation_time = (datetime.utcnow() - start_time).total_seconds()
            logger.debug(f"Base translation completed in {translation_time:.2f}s")
            
            # Extract translated text from result
            translated_text = translation_result.get('translated_text', '')
            
            # Clean up the translation (remove any prompt artifacts)
            cleaned_translation = self._clean_translation(translated_text)
            
            # Assess translation quality
            quality_result = self.quality_assessor.assess_quality(
                source=text,
                translation=cleaned_translation,
                terminology=self.terminology,
                context=self.context.get_context_prompt()
            )
            
            # Add to conversation history
            self.context.add_to_history(
                source=text,
                translation=cleaned_translation,
                metadata={
                    'quality': quality_result,
                    'source_lang': source_lang,
                    'target_lang': target_lang,
                    'translation_time_seconds': translation_time
                }
            )
            
            # Prepare result
            metadata_dict = {
                'context_used': self.context.get_context_prompt(),
                'processing_time_seconds': translation_time,
                'terminology_used': bool(self.terminology.get('terms'))
            }
            
            # Add any additional metadata if provided
            if metadata and isinstance(metadata, dict):
                metadata_dict.update(metadata)
                
            result = {
                'translated_text': cleaned_translation,
                'quality': quality_result,
                'metadata': metadata_dict
            }
            
            logger.info("Context-aware translation completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in context-aware translation: {str(e)}", exc_info=True)
            raise
    
    def load_terminology(self, terminology: Dict) -> None:
        """
        Load terminology for consistent translation.
        
        Args:
            terminology: Dictionary containing terminology data
        """
        if not terminology or not isinstance(terminology, dict):
            logger.warning("Invalid terminology format provided")
            return
            
        self.terminology = terminology
        self.context.terminology = terminology
        
        term_count = len(terminology.get('terms', []))
        logger.info(f"Loaded {term_count} terms into terminology database")
    
    def clear_context(self) -> None:
        """Clear the translation context and history."""
        self.context.clear()
        logger.info("Translation context cleared")
    
    def _build_enhanced_prompt(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """
        Build an enhanced prompt for translation with context and terminology.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Formatted prompt string
        """
        context = self.context.get_context_prompt()
        
        prompt_parts = [
            f"Translate the following text from {source_lang} to {target_lang}.",
            "",
            "CONTEXT:",
            context,
            "",
            "TEXT TO TRANSLATE:",
            text,
            "",
            f"TRANSLATION ({target_lang}):"
        ]
        
        return "\n".join(part for part in prompt_parts if part)
    
    @staticmethod
    def _clean_translation(translation: str) -> str:
        """
        Clean up the translated text by removing any prompt artifacts.
        
        Args:
            translation: Raw translated text
            
        Returns:
            Cleaned translation
        """
        if not translation:
            return ""
            
        # Remove any trailing prompt-like text
        for marker in ["CONTEXT:", "TEXT TO TRANSLATE:", "TRANSLATION:"]:
            if marker in translation:
                translation = translation.split(marker)[0].strip()
        
        return translation.strip()
    
    def batch_translate(
        self,
        segments: List[Dict[str, Any]],
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Translate a batch of text segments with context awareness.
        
        Args:
            segments: List of segment dictionaries with 'text' and optional 'id' keys
            source_lang: Source language code
            target_lang: Target language code
            metadata: Additional metadata for the batch
            
        Returns:
            Dictionary containing translated segments and batch metrics
        """
        logger.info(f"Starting batch translation of {len(segments)} segments")
        start_time = datetime.utcnow()
        
        results = []
        quality_scores = []
        
        try:
            for i, segment in enumerate(segments):
                segment_id = segment.get('id', str(i))
                text = segment.get('text', '')
                next_segment = segments[i+1]['text'] if i+1 < len(segments) else None
                
                logger.debug(f"Translating segment {i+1}/{len(segments)} (ID: {segment_id})")
                
                # Translate with context
                result = self.translate_with_context(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    next_segment=next_segment,
                    metadata={
                        'segment_id': segment_id,
                        'batch_position': i,
                        **(metadata or {})
                    }
                )
                
                # Store result
                results.append({
                    'id': segment_id,
                    'source': text,
                    'translation': result['translated_text'],
                    'quality': result['quality'],
                    'metadata': result['metadata']
                })
                
                # Track quality metrics
                if 'scores' in result['quality']:
                    quality_scores.append(result['quality']['scores']['overall'])
            
            # Calculate batch statistics
            total_time = (datetime.utcnow() - start_time).total_seconds()
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            logger.info(
                f"Batch translation completed in {total_time:.2f}s. "
                f"Average quality: {avg_quality:.2f}"
            )
            
            return {
                'results': results,
                'batch_metrics': {
                    'total_segments': len(segments),
                    'successful_segments': len(results),
                    'average_quality': avg_quality,
                    'processing_time_seconds': total_time,
                    'segments_per_second': len(segments) / total_time if total_time > 0 else 0
                },
                'metadata': metadata or {}
            }
            
        except Exception as e:
            logger.error(f"Error in batch translation: {str(e)}", exc_info=True)
            raise
