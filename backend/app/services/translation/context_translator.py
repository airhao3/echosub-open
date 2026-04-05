#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Contextual Translator
Provides enhanced translation with context awareness, terminology handling, and error recovery
"""

import time
import traceback
import logging
import functools
import re
from typing import Dict, Optional, List, Tuple, Any

from .utils import normalize_language_code, get_language_name, truncate_with_meaning

logger = logging.getLogger(__name__)

class ContextualTranslator:
    """
    Handles enhanced translation with context awareness and error recovery
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the ContextualTranslator
        
        Args:
            config: Configuration dictionary with provider settings
        """
        self.config = config or {}
        self.include_previous_context = True
        self.include_next_context = True
        self.provider = None
        self._initialize_provider()

    
    def _build_contextual_prompt(self, text: str, source_lang: str, target_lang: str,
                               terminology: dict = None, previous_text: str = None,
                               next_text: str = None, metadata: dict = None,
                               style: str = None, max_length: int = 0,
                               is_refinement_pass: bool = False) -> str:
        """
        Build an optimized, concise Netflix-standard translation prompt.
        Focuses on core requirements with minimal complexity for better LLM performance.
        """
        source_lang_name = get_language_name(source_lang) or source_lang
        target_lang_name = get_language_name(target_lang) or target_lang
        
        # Get content type for dynamic prompt optimization
        content_type = self._get_content_type_from_metadata(metadata)
        
        # Build streamlined prompt based on content type
        if is_refinement_pass:
            return self._build_refinement_prompt(text, source_lang_name, target_lang_name, metadata)
        else:
            return self._build_translation_prompt(
                text, source_lang_name, target_lang_name, 
                terminology, previous_text, next_text, 
                metadata, content_type, max_length
            )

    def _build_translation_prompt(self, text: str, source_lang_name: str, target_lang_name: str,
                                terminology: dict, previous_text: str, next_text: str,
                                metadata: dict, content_type: str, max_length: int) -> str:
        """Build optimized translation prompt with content-type specific guidance."""
        
        # Core Netflix translation directive
        core_directive = f"""Translate this {source_lang_name} text to professional {target_lang_name} subtitles following Netflix standards.

SOURCE: "{text}"
"""

        # Content-specific guidance (much shorter than before)
        content_guidance = self._get_content_specific_guidance(content_type, target_lang_name)
        
        # Enhanced context awareness for common errors
        context_hints = self._get_context_translation_hints(text, content_type)
        
        # Critical rules (simplified)
        critical_rules = """CRITICAL RULES:
• Preserve ALL [N] tags in exact positions
• Keep natural, conversational tone
• Maintain original meaning and emotion
• Use proper names and terms accurately
• Pay attention to context for ambiguous words"""

        # Context if available
        context_section = ""
        if previous_text or next_text:
            context_section = "\nCONTEXT:\n"
            if previous_text:
                context_section += f"Previous: \"{previous_text[:100]}...\"\n"
            if next_text:
                context_section += f"Next: \"{next_text[:100]}...\"\n"

        # Priority terminology (only high priority, max 5 terms)
        terminology_section = ""
        if terminology and terminology.get('terms'):
            high_priority_terms = [t for t in terminology['terms'][:5] 
                                 if t.get('priority') == 'high' and t.get('src') and t.get('tgt')]
            if high_priority_terms:
                terminology_section = "\nKEY TERMS:\n"
                for term in high_priority_terms:
                    terminology_section += f"• {term['src']} → {term['tgt']}\n"

        # Final instruction
        final_instruction = f"\nRespond with ONLY the {target_lang_name} translation:"

        return core_directive + content_guidance + critical_rules + context_hints + context_section + terminology_section + final_instruction

    def _build_refinement_prompt(self, text: str, source_lang_name: str, target_lang_name: str, metadata: dict) -> str:
        """Build streamlined refinement prompt."""
        original_source = metadata.get('original_source_text', '') if metadata else ''
        
        return f"""Polish this {target_lang_name} translation to Netflix professional standards.

ORIGINAL: "{original_source}"
TO POLISH: "{text}"

Make it more natural and fluent while preserving:
• All [N] tags in exact positions
• Original meaning and tone
• Professional subtitle quality

Respond with ONLY the polished translation:"""

    def _get_content_type_from_metadata(self, metadata: dict) -> str:
        """Extract content type from metadata for prompt optimization."""
        if not metadata:
            return "general"
        
        summary = metadata.get('summary')
        if isinstance(summary, dict):
            return summary.get('content_type', 'general')
        elif isinstance(summary, str):
            # Try to parse if it's a JSON string
            try:
                import json
                summary_data = json.loads(summary)
                return summary_data.get('content_type', 'general')
            except:
                return "general"
        
        return "general"

    def _get_content_specific_guidance(self, content_type: str, target_lang: str) -> str:
        """Get concise, content-specific translation guidance."""
        
        # Content-specific adaptations
        guidance_map = {
            "interview": "Conversational tone, preserve speaker personality, simplify filler words.\n",
            "sports": "Keep energy and excitement, use accurate sports terminology.\n", 
            "documentary": "Factual tone, explain complex terms when needed.\n",
            "educational": "Clear and accessible, maintain teaching clarity.\n",
            "entertainment": "Preserve humor and personality, adapt cultural jokes.\n",
            "news": "Professional, neutral tone with accurate reporting style.\n",
            "tutorial": "Clear instructions, actionable language.\n",
            "presentation": "Professional business tone, persuasive impact.\n"
        }
        
        base_guidance = guidance_map.get(content_type, "Natural, professional tone suitable for general audiences.\n")
        
        # Language-specific additions
        if target_lang.lower() in ['chinese', 'zh']:
            base_guidance += "• Remove unnecessary spaces between Chinese characters\n"
            base_guidance += "• Use appropriate Chinese punctuation\n"
        
        return base_guidance

    def _get_context_translation_hints(self, text: str, content_type: str) -> str:
        """Generate context-aware translation hints for common problematic words."""
        hints = []
        text_lower = text.lower()
        
        # Common translation error patterns
        error_patterns = {
            # Technology/Communication context
            r'\bmessage\b|\bmessages\b': "• 'message' = 消息/留言 (not 信息 in most contexts)",
            r'\bmethod\b|\bmethods\b': "• 'method' in technology = 方法; in voicemail = 消息",
            r'\bvoicemail\b': "• 'voicemail message' = 语音留言/语音消息",
            
            # Business context  
            r'\bclose\b.*\bdeal\b|\bclose\b.*\bone\b': "• 'close a deal' = 完成交易/成交 (not 关闭)",
            r'\bsale\b|\bsales\b': "• 'sale' = 销售/销售业绩/交易",
            r'\boutside\b|\boutsiders\b': "• 'outsiders' = 外人/外部人员 (not 外面的人)",
            
            # Office/workplace context
            r'\bemployee\b|\bemployees\b': "• 'employees' = 员工 (formal workplace term)",
            r'\bsensitive information\b': "• 'sensitive information' = 敏感信息/机密信息",
            
            # Common conversation words
            r'\bcut it out\b': "• 'cut it out' = 别闹了/停下 (casual, not literal cutting)",
            r'\bhats off\b': "• 'hats off to you' = 向你致敬/佩服你 (idiomatic)",
            
            # Time expressions
            r'\bwaiting for\b': "• 'waiting for me' = 等着我/留给我",
        }
        
        # Check for patterns and add relevant hints
        import re
        for pattern, hint in error_patterns.items():
            if re.search(pattern, text_lower):
                hints.append(hint)
        
        # Content-type specific hints
        if content_type == "entertainment" and "jim" in text_lower:
            hints.append("• This appears to be comedy dialogue - maintain humor and character voice")
        
        if content_type in ["business", "interview"] and any(word in text_lower for word in ["sale", "deal", "client"]):
            hints.append("• Business context: use professional terminology")
        
        if hints:
            return "\n\nCONTEXT HINTS:\n" + "\n".join(hints) + "\n"
        
        return ""

    def _initialize_provider(self):
        """
        Initializes the translation provider, falling back to global settings and handling legacy names.
        
        Sets self.provider with the initialized provider instance.
        """
        from app.core.config import settings  # Import global settings

        try:
            # Prioritize provider from instance config, falling back to global settings.
            provider_name = self.config.get("provider") or settings.TRANSLATION_PROVIDER

            # Handle legacy provider name 'defaqman' as an alias for 'yunwu'
            if provider_name == 'defaqman':
                logger.warning("Provider 'defaqman' is deprecated. Treating as 'yunwu'. Please update configuration.")
                provider_name = 'yunwu'

            logger.info(f"ContextualTranslator initializing provider: {provider_name}")

            if provider_name == "yunwu":
                from app.services.translation_providers.yunwu_provider import YunwuTranslationProvider
                # Construct config for Yunwu from global settings to ensure correctness
                yunwu_config = {
                    "api_key": settings.YUNWU_API_KEY,
                    "base_url": settings.YUNWU_BASE_URL,
                    "model": settings.YUNWU_MODEL,
                    "temperature": settings.YUNWU_TEMPERATURE,
                    "max_tokens": settings.YUNWU_MAX_TOKENS,
                    "timeout": settings.YUNWU_TIMEOUT,
                    "api_version": settings.YUNWU_API_VERSION,
                    "organization": settings.YUNWU_ORGANIZATION,
                }
                self.provider = YunwuTranslationProvider(yunwu_config)
                logger.info("Successfully initialized Yunwu translation provider")
                return
                
            elif provider_name == "translator":
                from app.services.translation_providers.yunwu_provider import YunwuTranslationProvider
                # Construct config for Translator from global settings
                translator_config = {
                    "api_key": settings.TRANSLATOR_API_KEY,
                    "base_url": settings.TRANSLATOR_BASE_URL,
                    "model": settings.TRANSLATOR_MODEL,
                    "temperature": settings.TRANSLATOR_TEMPERATURE,
                    "max_tokens": settings.TRANSLATOR_MAX_TOKENS,
                    "timeout": settings.TRANSLATOR_TIMEOUT,
                }
                self.provider = YunwuTranslationProvider(translator_config)
                logger.info("Successfully initialized Translator translation provider")
                return

            # Add other providers here, e.g.:
            # elif provider_name == "openai":
            #     from app.services.translation_providers.openai_provider import OpenAITranslationProvider
            #     # Construct config from global settings for OpenAI as well
            #     self.provider = OpenAITranslationProvider(...)
            #     return

            # If we get here, the provider is not supported
            error_msg = f"Unsupported translation provider after fallback and aliasing: {provider_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to initialize translation provider: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Set provider to None to make it clear initialization failed
            self.provider = None
            raise RuntimeError(error_msg) from e
        
    def translate_with_context(self, text: str, source_lang: str, target_lang: str, 
                             terminology: Dict = None, previous_text: str = None, 
                             next_text: str = None, metadata: Dict = None, 
                             style: str = None, max_length: int = 0, 
                             retry_count: int = 3, is_refinement_pass: bool = False) -> Dict:
        """
        Enhanced translate function with context awareness, style control, and retry logic
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            terminology: Dictionary of terms to use consistently
            previous_text: Previous segment for context
            next_text: Next segment for context
            metadata: Additional metadata for context
            style: Translation style/register (e.g., 'formal', 'casual')
            max_length: Maximum length for the translation (0 = no limit)
            retry_count: Number of retry attempts on failure
            is_refinement_pass: Whether this is a refinement pass
            
        Returns:
            Dictionary containing translation and metadata
        """
        # Log detailed input information
        logger.info("\n" + "="*80)
        logger.info("TRANSLATION REQUEST")
        logger.info("="*80)
        logger.info(f"Source Language: {source_lang}")
        logger.info(f"Target Language: {target_lang}")
        logger.info(f"Is Refinement: {is_refinement_pass}")
        logger.info(f"Style: {style}")
        
        if previous_text:
            logger.info("\nPREVIOUS CONTEXT:")
            logger.info(previous_text)
            
        logger.info("\nTEXT TO TRANSLATE:")
        logger.info(f'"{text}"')
        
        if next_text:
            logger.info("\nNEXT CONTEXT:")
            logger.info(next_text)
            
        if terminology and 'terms' in terminology and terminology['terms']:
            logger.info("\nTERMINOLOGY:")
            for term in terminology['terms']:
                logger.info(f"- {term.get('source')} -> {term.get('target')}")
                
        logger.info("="*80 + "\n")
        logger.info("=== CONTEXT-AWARE TRANSLATION STARTED ===")
        logger.info(f"Translating from {source_lang} to {target_lang}, style: {style}, max_length: {max_length}")
        logger.info(f"Text preview: '{text[:50]}...'" if len(text) > 50 else f"Full text: '{text}'")
        
        # Validate and normalize language codes
        target_lang = normalize_language_code(target_lang) or 'zh'
        source_lang = normalize_language_code(source_lang) or 'en'
        
        # Initialize result structure
        result = {
            "source_text": text,
            "target_text": "",
            "source_lang": source_lang,
            "target_lang": target_lang,
            "translation_status": "pending",
            "needs_review": False,
            "terminology_matches": {},
            "retry_count": 0,
            "versions": {
                "initial": "",
                "with_context": "",
                "with_terminology": "",
                "final": ""
            }
        }
        
        if not text or not text.strip():
            logger.warning("Empty text provided for translation")
            result["target_text"] = ""
            result["translation_status"] = "skipped_empty"
            return result
            
        # Get translation provider (now internal to ContextualTranslator)
        provider = self.provider
        if not provider:
            logger.error("Translation provider not initialized in ContextualTranslator. Cannot proceed.")
            result["translation_status"] = "error_provider_not_initialized"
            return result

        # Prepare previous_text and next_text for the prompt
        # Use direct arguments if provided, otherwise try to extract from metadata
        final_previous_text = previous_text
        final_next_text = next_text

        if metadata:
            if final_previous_text is None and "previous_segments" in metadata and metadata["previous_segments"]:
                # Use the last segment from the list of previous_segments
                if isinstance(metadata["previous_segments"], list) and len(metadata["previous_segments"]) > 0:
                    final_previous_text = metadata["previous_segments"][-1]
        
            if final_next_text is None and "next_segments" in metadata and metadata["next_segments"]:
                # Use the first segment from the list of next_segments
                if isinstance(metadata["next_segments"], list) and len(metadata["next_segments"]) > 0:
                    final_next_text = metadata["next_segments"][0]
    
        # Build contextual prompt
        prompt = self._build_contextual_prompt(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            terminology=terminology,
            previous_text=final_previous_text, # Use the determined previous text
            next_text=final_next_text,     # Use the determined next text
            metadata=metadata,
            style=style,
            max_length=max_length,
            is_refinement_pass=is_refinement_pass
        )
        
        # Try translation with retries
        success = False
        error_messages = []
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Translation attempt {attempt+1}/{retry_count}")
                
                # Get translation from provider
                logger.debug(f"ContextualTranslator.translate_with_context - Attempt {{attempt+1}} - Input to LLM provider:\nText: '{{text[:100]}}...'\nPrompt:\n{{prompt}}")
                response_data = provider.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    context=prompt
                )
                translated_text = response_data.get("translated_text", "")
                logger.debug(f"ContextualTranslator.translate_with_context - Attempt {{attempt+1}} - Raw output from LLM provider: '{{response_data}}'")
                
                logger.info(f"[CONTEXT_TRANSLATOR] Text from provider: '{translated_text}'")
                
                # Log the raw response
                logger.info("\n" + "="*80)
                logger.info("RAW TRANSLATION RESPONSE")
                logger.info("="*80)
                logger.info(translated_text)
                logger.info("="*80 + "\n")
                
                # Verify translation quality
                if not translated_text or len(translated_text.strip()) == 0:
                    error_messages.append(f"Attempt {attempt+1}: Empty result")
                    continue
                    
                # Clean up any metadata markers in the translation result
                cleaned_text = self._clean_translation_metadata(translated_text, target_lang)
                
                logger.info(f"[CONTEXT_TRANSLATOR] Text after cleaning: '{cleaned_text}'")
                
                # Log after cleaning
                logger.info("\n" + "="*80)
                logger.info("AFTER CLEANING")
                logger.info("="*80)
                logger.info(cleaned_text)
                logger.info("="*80 + "\n")
                
                # Store initial version
                result["versions"]["initial"] = cleaned_text
                
                # Netflix-streamlined processing: Terminology + Basic post-processing only
                if terminology and terminology.get('terms'):
                    logger.info(f"[NETFLIX_TRANSLATE] Processing {len(terminology['terms'])} terminology terms")
                    cleaned_text, term_stats = self._apply_enhanced_terminology_consistency(
                        translated_text=cleaned_text,
                        source_text=text,
                        terminology=terminology,
                        metadata=metadata
                    )
                    result["terminology_matches"] = term_stats
                    logger.info(f"[NETFLIX_TRANSLATE] Terminology results - Applied: {term_stats['applied']}, Critical Misses: {term_stats.get('high_priority_missed', 0)}")
                
                # Apply essential language-specific post-processing only
                if target_lang == 'zh':
                    cleaned_text = self._post_process_chinese_translation(cleaned_text)
                    # Add simplified/traditional consistency check
                    cleaned_text = self._ensure_chinese_consistency(cleaned_text)
                
                # Netflix Quality Control: Validate translation quality
                quality_score, quality_issues = self._assess_translation_quality(
                    source_text=text,
                    translated_text=cleaned_text,
                    terminology_stats=result.get("terminology_matches", {}),
                    content_type=self._get_content_type_from_metadata(metadata)
                )
                
                result["quality_score"] = quality_score
                result["quality_issues"] = quality_issues
                
                # Apply length limits if specified
                if max_length > 0 and len(cleaned_text) > max_length:
                    cleaned_text = truncate_with_meaning(cleaned_text, max_length, target_lang)
                    result["needs_review"] = True
                
                # Mark for review if quality is below Netflix standards
                if quality_score < 0.8:  # Netflix quality threshold
                    result["needs_review"] = True
                    logger.warning(f"[NETFLIX_QC] Translation quality below threshold: {quality_score:.2f}")
                    
                logger.info(f"[NETFLIX_QC] Translation quality: {quality_score:.2f}, Issues: {len(quality_issues)}")
                logger.info(f"[NETFLIX_TRANSLATE] Final translation: '{cleaned_text}'")
                
                # Set final result
                result["target_text"] = cleaned_text
                result["versions"]["final"] = cleaned_text
                result["translation_status"] = "success"
                result["retry_count"] = attempt + 1
                
                success = True
                break
                
            except Exception as e:
                error_msg = f"Translation error on attempt {attempt+1}: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                error_messages.append(error_msg)
                
                # Wait before retry (exponential backoff)
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s, etc.
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        # If all retries failed
        if not success:
            logger.warning(f"All {retry_count} translation attempts failed")
            
            # Try a basic fallback translation before giving up
            fallback_translation = self._attempt_basic_translation(text, source_lang, target_lang)
            
            if fallback_translation and fallback_translation.strip() and fallback_translation != text:
                logger.info(f"Using fallback basic translation: {fallback_translation}")
                result["target_text"] = fallback_translation
                result["translation_status"] = "fallback_basic"
                result["needs_review"] = True
            else:
                logger.error(f"Even fallback translation failed for text: '{text}'")
                # Only return original text if it's the same language as target
                if self._is_same_language_family(source_lang, target_lang):
                    result["target_text"] = text
                else:
                    # For cross-language failures, provide a clear indication
                    result["target_text"] = f"[Translation Error: {text}]"
                result["translation_status"] = "failed"
                result["needs_review"] = True
            
            result["errors"] = error_messages
        
        logger.info(f"Translation completed with status: {result['translation_status']}")
        return result
    
    def _attempt_basic_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Attempt a basic, simple translation as fallback when advanced translation fails.
        
        This method uses minimal prompts and basic translation without context,
        semantic optimization, or advanced features.
        """
        try:
            logger.info(f"[FALLBACK] Attempting basic translation for: '{text}'")
            
            # Use only the basic provider without advanced features
            basic_prompt = f"""Translate the following {source_lang} text to {target_lang}. 
Provide only the translation, no explanations.

Text: {text}

Translation:"""
            
            # Call the provider directly with minimal configuration
            response = self.provider.translate(
                text=basic_prompt,
                source_lang=source_lang,
                target_lang=target_lang,
                temperature=0.1,  # Low temperature for consistency
                max_tokens=200    # Limited tokens for safety
            )
            
            if response and response.strip():
                # Clean up the response
                cleaned_response = response.strip()
                
                # Remove common artifacts from basic translation
                if cleaned_response.startswith(("Translation:", "翻译:", "译文:")):
                    cleaned_response = cleaned_response.split(":", 1)[1].strip()
                
                logger.info(f"[FALLBACK] Basic translation successful: '{cleaned_response}'")
                return cleaned_response
            
        except Exception as e:
            logger.error(f"[FALLBACK] Basic translation failed: {e}")
        
        return None
    
    def _is_same_language_family(self, lang1: str, lang2: str) -> bool:
        """
        Check if two languages are from the same family to determine
        if returning original text makes sense.
        """
        # Language family mappings
        chinese_variants = {'zh', 'zh-cn', 'zh-tw', 'zh-hk', 'chinese', 'mandarin', 'cantonese'}
        english_variants = {'en', 'en-us', 'en-gb', 'english'}
        spanish_variants = {'es', 'es-es', 'es-mx', 'spanish', 'castellano'}
        
        lang1_lower = lang1.lower()
        lang2_lower = lang2.lower()
        
        # Check if both languages are in the same family
        for family in [chinese_variants, english_variants, spanish_variants]:
            if lang1_lower in family and lang2_lower in family:
                return True
        
        return lang1_lower == lang2_lower

    def _apply_terminology_consistency(self, translated_text: str, source_text: str, terminology: Dict) -> Tuple[str, Dict]:
        """
        Ensures terminology is consistently applied in the translation
        
        Args:
            translated_text: The translated text to check
            source_text: The original source text
            terminology: Dictionary of terminology mappings
            
        Returns:
            Tuple of (corrected_text, terminology_stats)
        """
        if not terminology or not translated_text or not source_text:
            return translated_text, {"applied": 0, "missed": 0, "terms": {}}
            
        logger.info("Applying terminology consistency check...")
        
        # Initialize statistics
        stats = {
            "applied": 0,
            "missed": 0,
            "terms": {}
        }
        
        corrected_text = translated_text
        
        # Group terminology by domain if available
        domains = {}
        # Check if terminology is flat (term: translation_string) or structured (term: {details})
        is_flat_terminology = all(isinstance(v, str) for v in terminology.values())

        if is_flat_terminology:
            # Ungrouped, flat terminology
            if "ungrouped" not in domains:
                domains["ungrouped"] = []
            for term, translation_text in terminology.items():
                domains["ungrouped"].append((term, translation_text))
        elif 'terms' in terminology and isinstance(terminology['terms'], list):
            # Structured terminology list under 'terms' key
            for term_entry in terminology['terms']:
                term_domain = term_entry.get('domain', 'ungrouped')
                src_term = term_entry.get('src')
                tgt_details = term_entry.get('tgt') # Can be string or dict
                tgt_text = ''
                if isinstance(tgt_details, dict):
                    tgt_text = tgt_details.get('translation', '')
                elif isinstance(tgt_details, str):
                    tgt_text = tgt_details
                
                if src_term and tgt_text:
                    if term_domain not in domains:
                        domains[term_domain] = []
                    domains[term_domain].append((src_term, tgt_text))
        else: # Try to handle other potential structures or log a warning
            logger.warning("Terminology structure not fully recognized for prompt building. Attempting generic processing.")
            if "ungrouped" not in domains:
                domains["ungrouped"] = []
            for term, translation_details in terminology.items(): # Fallback attempt
                if isinstance(translation_details, str):
                    domains["ungrouped"].append((term, translation_details))
                elif isinstance(translation_details, dict) and 'translation' in translation_details:
                    domains["ungrouped"].append((term, translation_details['translation']))

        # Apply terminology to the translated text
        for domain_name, terms_list in domains.items():
            for src_term, tgt_text in terms_list:
                # Skip empty terms
                if not src_term or not tgt_text:
                    continue
                    
                # Create a case-insensitive regex pattern
                pattern = re.compile(re.escape(src_term), re.IGNORECASE)
                
                # Track if we found and replaced this term
                found = False
                
                # Replace all occurrences in the translated text
                def replace_match(match):
                    nonlocal found, stats
                    found = True
                    matched_text = match.group(0)
                    # Preserve the original case
                    if matched_text[0].isupper():
                        return tgt_text[0].upper() + tgt_text[1:]
                    return tgt_text
                
                # Apply the replacement
                new_text, count = pattern.subn(replace_match, corrected_text)
                
                if count > 0:
                    corrected_text = new_text
                    stats["applied"] += count
                    stats["terms"][src_term] = stats["terms"].get(src_term, 0) + count
                    logger.debug(f"Applied terminology: '{src_term}' -> '{tgt_text}' ({count} times)")
                else:
                    stats["missed"] += 1
                    logger.debug(f"Terminology not found in text: '{src_term}'")
        
        logger.info(f"Terminology application complete - Applied: {stats['applied']}, Missed: {stats['missed']}")
        return corrected_text, stats
            
    def _clean_translation_metadata(self, text: str, target_lang: str) -> str:
        """
        Cleans the raw translated text from the provider, removing any
        extraneous metadata, instructions, or conversational fluff.
        
        Args:
            text: The raw text from the translation provider.
            target_lang: The target language.
            
        Returns:
            The cleaned translation.
        """
        if not text:
            return ""

        cleaned_text = text.strip()
        
        # First detect if this appears to be an AI system message rather than a translation
        ai_system_patterns = [
            r"I notice that .+appears to be",
            r"I'm being shown what appears to be",
            r"I'd be happy to help you with",
            r"This looks like it might have been accidentally",
            r"Hello! I'm .+an AI assistant",
            r"I am Claude",
            r"I am an AI",
            r"您好！很高兴见到您",
            r"我是.+AI",
            r"我可以帮您"
        ]
        
        for pattern in ai_system_patterns:
            if re.search(pattern, cleaned_text, re.IGNORECASE | re.DOTALL):
                logger.warning(f"Detected AI system message in translation output: '{cleaned_text[:50]}...'")
                return "" # Return empty string to trigger fallback to source
        
        # Check for long messages typical of system responses that would not be translations
        if len(cleaned_text.split()) > 50 and ('\n\n' in cleaned_text or 'I am' in cleaned_text or 'I can' in cleaned_text):
            lines = cleaned_text.split('\n')
            if len(lines) > 3:  # More than 3 lines is suspicious for a translation
                logger.warning(f"Rejecting suspiciously long translation that appears to be a system message: '{cleaned_text[:50]}...'")
                return ""

        # Patterns to remove common LLM conversational prefixes
        prefixes_to_remove = [
            "translation:", "translated text:", "here is the translation:",
            f"the {get_language_name(target_lang)} translation is:",
            f"in {get_language_name(target_lang)}:",
            f"{get_language_name(target_lang)}:",
            "sure, here is the translation:",
            "certainly, the translation is:",
            "here's the translation:",
            "here is your translation:",
            "i'll translate this to",
            "translating to",
            "translating this",
            "the translation is:"
        ]
        
        # Case-insensitive removal of prefixes
        text_lower = cleaned_text.lower()
        for prefix in prefixes_to_remove:
            if text_lower.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].lstrip(' :')
                break

        # Extract content from quotes if they wrap the entire string
        if (cleaned_text.startswith(('"', '"')) and cleaned_text.endswith(('"', '"'))) or \
           (cleaned_text.startswith("'") and cleaned_text.endswith("'")):
            cleaned_text = cleaned_text[1:-1]
        
        # Remove any trailing or leading AI assistant language
        ai_suffix_patterns = [
            r"Is there anything else you'd like me to help you with\?.*$",
            r"Let me know if you need any other assistance.*$",
            r"I hope this helps.*$",
            r"^As an AI assistant, I",
            r"^I'm an AI language model"
        ]
        
        for pattern in ai_suffix_patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
        
        # Clean up any multiple line breaks or excessive whitespace
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
        
        return cleaned_text.strip()
        
    def _process_terminology(self, terminology: Dict) -> List[Dict]:
        """
        Process and organize terminology from the standard format.
        
        Expected format:
        {
            "terms": [
                {
                    "src": str,           # Source term (required)
                    "tgt": str,           # Target translation (required)
                    "category": str,      # Term category (e.g., 'proper_noun', 'technical')
                    "domain": str,        # Domain context (e.g., 'legal', 'medical')
                    "definition": str,    # Term definition
                    "priority": str        # 'high' or 'normal'
                }
            ],
            "domain": str,               # Default domain for all terms
            "source_language": str,      # Source language code
            "target_language": str       # Target language code
        }
        
        Args:
            terminology: Terminology dictionary in the expected format
                
        Returns:
            List of processed term dictionaries with standardized structure:
            [{
                "source": str,     # Source term
                "target": str,     # Target translation
                "domain": str,     # Domain context
                "category": str,   # Term category
                "priority": str,   # 'high' or 'normal'
                "definition": str  # Term definition
            }]
            
        Raises:
            ValueError: If the terminology format is invalid
        """
        if not terminology or not isinstance(terminology, dict):
            logger.warning("Empty or invalid terminology provided")
            return []
            
        if "terms" not in terminology or not isinstance(terminology["terms"], list):
            logger.warning("Invalid terminology format: 'terms' list is missing or invalid")
            return []
            
        processed_terms = []
        default_domain = terminology.get('domain')
        
        for term in terminology["terms"]:
            if not isinstance(term, dict):
                logger.warning(f"Skipping invalid term entry: {term}")
                continue
                
            if "src" not in term or "tgt" not in term:
                logger.warning(f"Skipping term missing required fields (src/tgt): {term}")
                continue
                
            # Get domain from term or default to root domain
            domain = term.get('domain') or default_domain
            if not domain:
                logger.warning(f"No domain specified for term: {term['src']}")
                domain = "general"
                
            # Determine priority
            category = term.get('category', '')
            priority = term.get('priority')
            if not priority:
                priority = "high" if category == "proper_noun" else "normal"
                
            processed_terms.append({
                "source": term["src"],
                "target": term["tgt"],
                "domain": domain,
                "category": category,
                "priority": priority,
                "definition": term.get("definition", "")
            })
        
        return processed_terms

    def _post_process_chinese_translation(self, text: str) -> str:
        """
        Post-process Chinese translation to ensure better readability and segmentation
        
        Args:
            text: Chinese translated text
            
        Returns:
            Post-processed Chinese text
        """
        if not text:
            return text
            
        logger.info("\n" + "="*80)
        logger.info("CHINESE POST-PROCESSING - INPUT")
        logger.info("="*80)
        logger.info(text)
            
        # Remove unnecessary spaces between Chinese characters
        # This is a common issue with LLM translations
        import re
        
        # Keep spaces in Latin character sequences, remove between Chinese characters
        result = ""
        in_latin = False
        
        for char in text:
            if re.match(r'[\u4e00-\u9fff，。！？；：""''\\(\\)（）【】『』「」]', char):
                # Chinese character or punctuation
                if in_latin:
                    in_latin = False
                result += char
            elif re.match(r'[a-zA-Z0-9]', char):
                # Latin character or number
                in_latin = True
                result += char
            elif char == ' ':
                # Space
                if in_latin:
                    result += char
            else:
                # Other character
                result += char
        
        # Additional cleanup for common issues
        result = re.sub(r'\s+([，。！？；：])', r'\1', result)  # Remove space before Chinese punctuation
        result = re.sub(r'([a-zA-Z])\s+([\u4e00-\u9fff])', r'\1 \2', result)  # Ensure space between Latin and Chinese
        result = re.sub(r'([\u4e00-\u9fff])\s+([a-zA-Z])', r'\1 \2', result)  # Ensure space between Chinese and Latin
        
        logger.info("\nCHINESE POST-PROCESSING - OUTPUT")
        logger.info("="*80)
        logger.info(result)
        logger.info("="*80 + "\n")
                
        return result
    
    def _build_enhanced_context_section(self, metadata: Dict, style: str = None) -> List[str]:
        """
        Build enhanced context section for Netflix subtitle translation standards.
        
        Args:
            metadata: Metadata dictionary containing enhanced summary information
            style: Optional style override
            
        Returns:
            List of formatted context information strings
        """
        if not metadata:
            return []
        
        context_parts = []
        
        # Video title and type
        if 'title' in metadata and metadata['title']:
            context_parts.append(f"- Video Title: {metadata['title']}")
        
        # Enhanced summary analysis for Netflix standards
        if 'summary' in metadata and isinstance(metadata['summary'], dict):
            summary_data = metadata['summary']
            
            # Content overview for context
            if 'content_overview' in summary_data:
                context_parts.append(f"- Content Summary: {summary_data['content_overview']}")
            
            # Netflix subtitle adaptation guidance
            content_type = summary_data.get('content_type', 'other')
            domain_context = summary_data.get('domain_context', 'other')
            expertise_level = summary_data.get('expertise_level', 'general')
            emotional_undertone = summary_data.get('emotional_undertone', 'neutral')
            
            context_parts.append(f"- Content Type: {content_type.title()} (adapt tone accordingly)")
            context_parts.append(f"- Subject Domain: {domain_context.title()}")
            context_parts.append(f"- Target Audience Level: {expertise_level.title()}")
            
            # Netflix-specific translation guidance
            netflix_guidance = self._get_netflix_translation_guidance(content_type, domain_context, expertise_level)
            if netflix_guidance:
                context_parts.append(f"- Netflix Translation Approach: {netflix_guidance}")
            
            # Proper names and references that need special attention
            key_entities = summary_data.get('key_entities', [])
            if key_entities and isinstance(key_entities, list):
                entities_text = ", ".join(key_entities[:8])  # Limit to avoid prompt bloat
                context_parts.append(f"- Key Names/References to Handle Carefully: {entities_text}")
            
            # Tone and style guidance for emotional context
            if emotional_undertone and emotional_undertone != 'neutral':
                context_parts.append(f"- Emotional Tone: {emotional_undertone.title()} (preserve this feeling in translation)")
            
            # Key concepts for consistency
            if 'key_concepts' in summary_data and summary_data['key_concepts']:
                concepts = ', '.join(summary_data['key_concepts'][:5])  # Top 5 concepts
                context_parts.append(f"- Key Concepts: {concepts}")
        
        return context_parts
    
    def _get_netflix_translation_guidance(self, content_type: str, domain: str, expertise_level: str) -> str:
        """
        Provide Netflix-specific translation guidance based on content characteristics.
        """
        guidance_parts = []
        
        # Content type specific guidance
        if content_type == 'interview':
            guidance_parts.append("Maintain conversational flow, simplify excessive filler words")
        elif content_type == 'sports':
            guidance_parts.append("Use sports terminology accurately, keep energy and excitement")
        elif content_type == 'documentary':
            guidance_parts.append("Balance accuracy with accessibility, explain complex terms when needed")
        elif content_type == 'entertainment':
            guidance_parts.append("Prioritize humor and personality, adapt cultural jokes appropriately")
        
        # Domain specific guidance
        if domain == 'sports':
            guidance_parts.append("Accurately translate player names, team names, and sports terminology")
        elif domain == 'technology':
            guidance_parts.append("Balance technical precision with general audience understanding")
        elif domain == 'politics':
            guidance_parts.append("Maintain neutrality, translate names and positions accurately")
        
        # Expertise level guidance
        if expertise_level == 'beginner':
            guidance_parts.append("Simplify technical terms, add context for specialized references")
        elif expertise_level == 'expert':
            guidance_parts.append("Maintain technical precision, preserve professional terminology")
        
        return "; ".join(guidance_parts) if guidance_parts else "Standard Netflix quality translation"
    
    def _apply_semantic_optimization_with_tag_realignment(
        self, 
        initial_translation: str, 
        source_text: str, 
        source_lang: str, 
        target_lang: str,
        metadata: Dict = None,
        terminology: Dict = None,
        previous_text: str = None,
        next_text: str = None
    ) -> Tuple[str, Dict]:
        """
        Apply semantic optimization with intelligent tag realignment.
        
        This method first performs standard semantic optimization, then applies
        intelligent tag realignment if the conditions are met.
        """
        # First, apply standard semantic optimization
        optimized_text, optimization_stats = self._apply_semantic_optimization(
            initial_translation=initial_translation,
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            metadata=metadata,
            terminology=terminology,
            previous_text=previous_text,
            next_text=next_text
        )
        
        # Check if tag realignment should be applied
        if self._should_apply_tag_realignment(initial_translation, optimized_text, metadata):
            try:
                logger.info("[TAG_REALIGNMENT] Applying intelligent tag realignment to optimized translation")
                
                # Get the tag realignment service from the parent service
                tag_service = self.service.tag_realignment_service
                
                # Apply tag realignment to the optimized text
                realigned_text = self._apply_tag_realignment_to_optimized_text(
                    optimized_text=optimized_text,
                    original_tagged_text=initial_translation,
                    source_text=source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    tag_service=tag_service,
                    metadata=metadata
                )
                
                # Update optimization stats
                if realigned_text != optimized_text:
                    optimization_stats["tag_realignment_applied"] = True
                    optimization_stats["realigned_text"] = realigned_text
                    logger.info(f"[TAG_REALIGNMENT] Successfully applied tag realignment")
                    logger.debug(f"[TAG_REALIGNMENT] Before: {optimized_text}")
                    logger.debug(f"[TAG_REALIGNMENT] After: {realigned_text}")
                    return realigned_text, optimization_stats
                else:
                    optimization_stats["tag_realignment_applied"] = False
                    optimization_stats["tag_realignment_reason"] = "No changes needed"
                    
            except Exception as e:
                logger.warning(f"[TAG_REALIGNMENT] Tag realignment failed, using optimized text: {e}")
                optimization_stats["tag_realignment_applied"] = False
                optimization_stats["tag_realignment_error"] = str(e)
        else:
            optimization_stats["tag_realignment_applied"] = False
            optimization_stats["tag_realignment_reason"] = "Conditions not met"
        
        return optimized_text, optimization_stats
    
    def _should_apply_tag_realignment(self, initial_translation: str, optimized_text: str, metadata: Dict = None) -> bool:
        """
        Determine if tag realignment should be applied based on content characteristics.
        """
        # Check if tag realignment is globally enabled
        from app.core.config import settings
        if not settings.ENABLE_TAG_REALIGNMENT:
            return False
        
        # Check if the text contains numbered tags
        import re
        tag_pattern = r'\[\d+\]'
        
        initial_tags = re.findall(tag_pattern, initial_translation)
        optimized_tags = re.findall(tag_pattern, optimized_text)
        
        # Only apply if:
        # 1. Both versions have tags
        # 2. Multiple tags exist (2+)
        # 3. Tags are preserved in optimization
        if not initial_tags or not optimized_tags or len(initial_tags) < 2:
            return False
            
        # Check if optimization preserved all tags
        if set(initial_tags) != set(optimized_tags):
            logger.warning(f"[TAG_REALIGNMENT] Tag mismatch between initial and optimized: {initial_tags} vs {optimized_tags}")
            return False
        
        # Check metadata for content type that benefits from realignment
        if metadata and isinstance(metadata, dict):
            summary = metadata.get('summary', {})
            if isinstance(summary, dict):
                content_type = summary.get('content_type', '').lower()
                # Apply realignment for content types that typically have longer sentences
                if content_type in ['interview', 'documentary', 'presentation', 'discussion']:
                    return True
        
        # Default: apply if multiple tags exist
        return len(initial_tags) >= 2
    
    def _apply_tag_realignment_to_optimized_text(
        self, 
        optimized_text: str, 
        original_tagged_text: str,
        source_text: str,
        source_lang: str,
        target_lang: str,
        tag_service,
        metadata: Dict = None
    ) -> str:
        """
        Apply tag realignment to optimized translation text.
        """
        import re
        
        # Extract original tags and their positions
        tag_pattern = r'\[(\d+)\]'
        original_tags = re.findall(tag_pattern, original_tagged_text)
        
        if not original_tags:
            return optimized_text
        
        # Create a pseudo-tagged segment list for the tag service
        # We'll treat the optimized text as a single segment group that needs realignment
        pseudo_segments = []
        
        # Split optimized text by existing tags to reconstruct segments
        tag_splits = re.split(r'(\[\d+\])', optimized_text)
        
        current_tag = None
        for i, part in enumerate(tag_splits):
            part = part.strip()
            if not part:
                continue
                
            tag_match = re.match(r'\[(\d+)\]', part)
            if tag_match:
                current_tag = int(tag_match.group(1))
            else:
                if current_tag is not None:
                    pseudo_segments.append(f"[{current_tag}] {part}")
                    current_tag = None
                else:
                    # Text without tag - add to last segment if exists
                    if pseudo_segments:
                        last_segment = pseudo_segments[-1]
                        pseudo_segments[-1] = f"{last_segment} {part}"
        
        # If we don't have proper segments, create them from tags
        if not pseudo_segments and original_tags:
            # Fallback: create segments by estimating positions
            text_without_tags = re.sub(r'\[\d+\]\s*', '', optimized_text).strip()
            if text_without_tags:
                # Simple approach: divide text roughly by number of tags
                words = text_without_tags.split()
                words_per_segment = max(1, len(words) // len(original_tags))
                
                for i, tag in enumerate(original_tags):
                    start_word = i * words_per_segment
                    end_word = min((i + 1) * words_per_segment, len(words)) if i < len(original_tags) - 1 else len(words)
                    
                    segment_words = words[start_word:end_word]
                    if segment_words:
                        pseudo_segments.append(f"[{tag}] {' '.join(segment_words)}")
        
        if not pseudo_segments:
            logger.warning("[TAG_REALIGNMENT] Could not create segments for realignment")
            return optimized_text
        
        # Check if realignment should be applied to this segment group
        if not tag_service.should_apply_realignment(pseudo_segments):
            return optimized_text
        
        # Apply realignment
        try:
            realigned_segments = tag_service.realign_tagged_segment_group(
                tagged_segments=pseudo_segments,
                source_lang=source_lang,
                target_lang=target_lang,
                context=metadata or {}
            )
            
            # Combine realigned segments back into single text
            if realigned_segments:
                realigned_text = ' '.join(realigned_segments)
                return realigned_text
            else:
                return optimized_text
                
        except Exception as e:
            logger.error(f"[TAG_REALIGNMENT] Error in realignment process: {e}")
            return optimized_text
        
        # Legacy metadata support
        if 'domain' in metadata and metadata['domain']:
            context_parts.append(f"- Document Domain: {metadata['domain']}")
        
        # Style information
        final_style = style or (metadata.get('summary', {}).get('tone_style', ''))
        if final_style:
            context_parts.append(f"- Tone & Style: {final_style}")
        
        return context_parts
    
    def _get_translation_strategy_guidance(self, strategy: str, content_type: str, expertise_level: str) -> str:
        """Generate specific translation strategy guidance based on scene analysis."""
        guidance_map = {
            'literal_accuracy': 'Maintain precise word-for-word accuracy, preserving exact meaning and structure',
            'cultural_adaptation': 'Adapt cultural references and idioms for target culture understanding',
            'technical_accuracy_with_accessibility': 'Use precise technical terms but ensure accessibility for the target audience',
            'creative_localization': 'Creatively adapt content to resonate with target culture while preserving core message',
            'formal_professional': 'Maintain formal, professional tone suitable for business or academic contexts',
            'casual_conversational': 'Use natural, everyday language that flows conversationally'
        }
        
        base_guidance = guidance_map.get(strategy, 'Balance accuracy with naturalness')
        
        # Add content-type specific adjustments
        if content_type == 'tutorial':
            base_guidance += '. Ensure step-by-step instructions remain clear and actionable'
        elif content_type == 'educational':
            base_guidance += '. Maintain educational clarity and concept accessibility'
        elif content_type == 'presentation':
            base_guidance += '. Keep professional presentation tone and persuasive impact'
        elif content_type == 'interview':
            base_guidance += '. Preserve conversational flow and personal expression'
        
        # Add expertise level adjustments
        if expertise_level == 'beginner':
            base_guidance += '. Simplify technical terms when possible and add clarity'
        elif expertise_level == 'expert':
            base_guidance += '. Use precise technical terminology and advanced concepts'
        
        return base_guidance
    
    def _get_cultural_adaptation_guidance(self, cultural_context: str, emotional_undertone: str) -> str:
        """Generate cultural adaptation guidance based on context analysis."""
        cultural_guidance = []
        
        # Cultural context guidance
        if cultural_context == 'western_formal':
            cultural_guidance.append('adapt for Western formal communication styles')
        elif cultural_context == 'eastern_formal':
            cultural_guidance.append('adapt for Eastern formal communication patterns')
        elif cultural_context == 'academic':
            cultural_guidance.append('maintain academic discourse conventions')
        elif cultural_context == 'business':
            cultural_guidance.append('preserve business communication protocols')
        elif cultural_context == 'youth_oriented':
            cultural_guidance.append('adapt for younger audience communication styles')
        
        # Emotional undertone guidance  
        if emotional_undertone == 'enthusiastic':
            cultural_guidance.append('preserve enthusiastic and energetic tone')
        elif emotional_undertone == 'serious':
            cultural_guidance.append('maintain serious and formal tone')
        elif emotional_undertone == 'humorous':
            cultural_guidance.append('adapt humor for target culture when appropriate')
        elif emotional_undertone == 'urgent':
            cultural_guidance.append('convey sense of urgency and immediacy')
        elif emotional_undertone == 'passionate':
            cultural_guidance.append('preserve passionate and emotional intensity')
        
        return '; '.join(cultural_guidance) if cultural_guidance else ''
    
    def _build_priority_terminology_section(self, terminology: Dict, metadata: Dict = None) -> List[str]:
        """
        Build terminology section with priority-based organization and scene-aware context.
        
        Args:
            terminology: Terminology dictionary with enhanced fields
            metadata: Optional metadata for additional context
            
        Returns:
            List of formatted terminology section strings
        """
        if not terminology or not terminology.get('terms'):
            return []
        
        # Group terms by priority
        high_priority = []
        medium_priority = []
        low_priority = []
        
        for term in terminology['terms']:
            priority = term.get('priority', 'medium').lower()
            term_info = {
                'src': term.get('src', ''),
                'tgt': term.get('tgt', ''),
                'context': term.get('context', ''),
                'category': term.get('category', ''),
                'definition': term.get('definition', '')
            }
            
            if priority == 'high':
                high_priority.append(term_info)
            elif priority == 'low':
                low_priority.append(term_info)
            else:
                medium_priority.append(term_info)
        
        sections = []
        
        # High priority terms (critical for accuracy)
        if high_priority:
            sections.append("\n=== CRITICAL TERMINOLOGY (MUST USE EXACTLY) ===")
            sections.append("These terms are essential for accurate translation:")
            for term in high_priority[:10]:  # Limit to top 10 to avoid overwhelming
                term_line = f"- {term['src']} → {term['tgt']}"
                if term['category'] and term['category'] != 'technical':
                    term_line += f" [{term['category']}]"
                if term['context'] and term['context'] != 'General usage':
                    term_line += f" (Context: {term['context'][:50]}...)" if len(term['context']) > 50 else f" (Context: {term['context']})"
                sections.append(term_line)
        
        # Medium priority terms (important for consistency)
        if medium_priority:
            sections.append("\n=== IMPORTANT TERMINOLOGY (RECOMMENDED) ===")
            sections.append("Use these terms for consistency:")
            for term in medium_priority[:8]:  # Limit to avoid prompt bloat
                sections.append(f"- {term['src']} → {term['tgt']}")
        
        # Low priority terms (optional, for reference)
        if low_priority and len(high_priority) + len(medium_priority) < 15:
            sections.append("\n=== REFERENCE TERMINOLOGY (OPTIONAL) ===")
            sections.append("Additional terms for reference:")
            for term in low_priority[:5]:  # Very limited for low priority
                sections.append(f"- {term['src']} → {term['tgt']}")
        
        # Add scene-aware terminology guidance
        if metadata and 'summary' in metadata:
            summary_data = metadata['summary']
            content_type = summary_data.get('content_type', 'other')
            domain_context = summary_data.get('domain_context', 'other')
            
            guidance = self._get_terminology_usage_guidance(content_type, domain_context)
            if guidance:
                sections.append(f"\n=== TERMINOLOGY USAGE GUIDANCE ===")
                sections.append(guidance)
        
        return sections
    
    def _get_terminology_usage_guidance(self, content_type: str, domain_context: str) -> str:
        """Generate scene-specific terminology usage guidance."""
        guidance_parts = []
        
        # Content type specific guidance
        if content_type == 'tutorial':
            guidance_parts.append("For tutorial content: Use clear, actionable terminology that helps users follow instructions")
        elif content_type == 'educational':
            guidance_parts.append("For educational content: Prioritize conceptual clarity and learning progression")
        elif content_type == 'presentation':
            guidance_parts.append("For presentations: Use professional terminology that maintains persuasive impact")
        elif content_type == 'documentary':
            guidance_parts.append("For documentary content: Maintain factual accuracy and investigative tone")
        elif content_type == 'interview':
            guidance_parts.append("For interviews: Preserve conversational authenticity while ensuring terminology accuracy")
        
        # Domain specific guidance
        if domain_context == 'technology':
            guidance_parts.append("Technology domain: Maintain technical precision while ensuring accessibility")
        elif domain_context == 'business':
            guidance_parts.append("Business domain: Use professional terminology appropriate for corporate contexts")
        elif domain_context == 'science':
            guidance_parts.append("Science domain: Preserve scientific accuracy and methodological precision")
        elif domain_context == 'medicine':
            guidance_parts.append("Medical domain: Use precise medical terminology following standard conventions")
        elif domain_context == 'education':
            guidance_parts.append("Educational domain: Balance academic accuracy with learning accessibility")
        
        return '. '.join(guidance_parts) if guidance_parts else ''
    
    def _apply_enhanced_terminology_consistency(
        self, 
        translated_text: str, 
        source_text: str, 
        terminology: Dict, 
        metadata: Dict = None
    ) -> Tuple[str, Dict]:
        """
        Netflix-optimized terminology validation and correction system.
        Focuses on critical terms with automatic correction for high-priority misses.
        """
        if not terminology or not terminology.get('terms') or not translated_text or not source_text:
            return translated_text, {"applied": 0, "missed": 0, "high_priority_applied": 0, "terms": {}}
        
        logger.info("[NETFLIX_TERMINOLOGY] Starting smart terminology validation...")
        
        stats = {
            "applied": 0,
            "missed": 0,
            "high_priority_applied": 0,
            "high_priority_missed": 0,
            "corrected": 0,
            "terms": {},
            "critical_misses": []
        }
        
        corrected_text = translated_text
        
        # Extract and prioritize critical terms
        critical_terms = self._extract_critical_terminology(terminology, source_text)
        
        if not critical_terms:
            logger.info("[NETFLIX_TERMINOLOGY] No critical terms found in source text")
            return translated_text, stats
        
        logger.info(f"[NETFLIX_TERMINOLOGY] Validating {len(critical_terms)} critical terms")
        
        # Validate and correct critical terminology
        for term in critical_terms:
            src_term = term['src']
            tgt_term = term['tgt']
            priority = term.get('priority', 'medium')
            
            # Check if correct translation is already used
            if self._is_term_correctly_used(corrected_text, tgt_term):
                stats["applied"] += 1
                if priority == 'high':
                    stats["high_priority_applied"] += 1
                stats["terms"][src_term] = stats["terms"].get(src_term, 0) + 1
                logger.debug(f"[NETFLIX_TERMINOLOGY] ✓ Correct term usage: '{src_term}' -> '{tgt_term}'")
            else:
                # Critical miss - attempt automatic correction for high priority
                if priority == 'high':
                    corrected_text, correction_made = self._attempt_terminology_correction(
                        corrected_text, src_term, tgt_term, source_text
                    )
                    
                    if correction_made:
                        stats["corrected"] += 1
                        stats["applied"] += 1 
                        stats["high_priority_applied"] += 1
                        stats["terms"][src_term] = 1
                        logger.info(f"[NETFLIX_TERMINOLOGY] ✓ Auto-corrected: '{src_term}' -> '{tgt_term}'")
                    else:
                        stats["missed"] += 1
                        stats["high_priority_missed"] += 1
                        stats["critical_misses"].append({"src": src_term, "tgt": tgt_term})
                        logger.warning(f"[NETFLIX_TERMINOLOGY] ✗ CRITICAL MISS: '{src_term}' -> '{tgt_term}'")
                else:
                    stats["missed"] += 1
                    logger.debug(f"[NETFLIX_TERMINOLOGY] - Missed term: '{src_term}' -> '{tgt_term}'")
        
        # Log summary
        logger.info(f"[NETFLIX_TERMINOLOGY] Results - Applied: {stats['applied']}, Corrected: {stats['corrected']}, Critical Misses: {stats['high_priority_missed']}")
        
        return corrected_text, stats
    
    def _extract_critical_terminology(self, terminology: Dict, source_text: str) -> List[Dict]:
        """Extract only critical terms that appear in the source text."""
        critical_terms = []
        source_text_lower = source_text.lower()
        
        for term in terminology.get('terms', []):
            if not term.get('src') or not term.get('tgt'):
                continue
            
            src_term = term['src'].strip()
            if not src_term:
                continue
                
            # Quick check if term appears in source (case-insensitive)
            if src_term.lower() in source_text_lower:
                # More precise check with word boundaries for accuracy
                import re
                pattern = r'\b' + re.escape(src_term) + r'\b'
                if re.search(pattern, source_text, re.IGNORECASE):
                    critical_terms.append({
                        'src': src_term,
                        'tgt': term['tgt'].strip(),
                        'priority': term.get('priority', 'medium'),
                        'category': term.get('category', 'general')
                    })
        
        # Sort by priority (high first)
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        critical_terms.sort(key=lambda x: priority_order.get(x['priority'], 1))
        
        return critical_terms
    
    def _is_term_correctly_used(self, text: str, target_term: str) -> bool:
        """Check if the target term is correctly used in the text."""
        import re
        
        # Clean the target term
        target_term = target_term.strip()
        if not target_term:
            return False
        
        # Create flexible pattern for term detection
        escaped_term = re.escape(target_term)
        
        # For Chinese terms, check without word boundaries
        if re.search(r'[\u4e00-\u9fff]', target_term):
            pattern = escaped_term
        else:
            pattern = r'\b' + escaped_term + r'\b'
        
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _attempt_terminology_correction(self, text: str, src_term: str, tgt_term: str, source_text: str) -> Tuple[str, bool]:
        """Attempt intelligent terminology correction for critical misses."""
        import re
        
        # Find potential incorrect translations of the source term
        # Look for variations or partial matches that could be corrected
        
        # Simple approach: look for the source term and see if it wasn't translated
        src_pattern = r'\b' + re.escape(src_term) + r'\b'
        if re.search(src_pattern, text, re.IGNORECASE):
            # Source term appears untranslated - replace it
            corrected_text = re.sub(src_pattern, tgt_term, text, flags=re.IGNORECASE)
            return corrected_text, True
        
        # Look for partial translations or similar terms that might need correction
        # This is a simplified approach - in production, this could be more sophisticated
        return text, False
    
    def _assess_translation_quality(self, source_text: str, translated_text: str, 
                                   terminology_stats: Dict, content_type: str) -> Tuple[float, List[str]]:
        """
        Netflix-standard quality assessment for translations.
        Returns quality score (0-1) and list of specific issues.
        """
        issues = []
        quality_factors = {}
        
        # 1. Basic validation
        if not translated_text or not translated_text.strip():
            return 0.0, ["Empty translation"]
        
        if translated_text == source_text:
            return 0.3, ["Identical to source - possible translation failure"]
        
        # 2. Tag preservation check
        import re
        source_tags = re.findall(r'\[(\d+)\]', source_text)
        translated_tags = re.findall(r'\[(\d+)\]', translated_text)
        
        if source_tags:
            if len(source_tags) != len(translated_tags):
                issues.append(f"Tag count mismatch: {len(source_tags)} -> {len(translated_tags)}")
                quality_factors['tag_preservation'] = 0.5
            elif set(source_tags) != set(translated_tags):
                issues.append("Tag number mismatch")
                quality_factors['tag_preservation'] = 0.7
            else:
                quality_factors['tag_preservation'] = 1.0
        else:
            quality_factors['tag_preservation'] = 1.0
        
        # 3. Terminology compliance (Netflix critical factor)
        term_score = 1.0
        if terminology_stats:
            high_priority_missed = terminology_stats.get('high_priority_missed', 0)
            high_priority_applied = terminology_stats.get('high_priority_applied', 0)
            total_critical = high_priority_missed + high_priority_applied
            
            if total_critical > 0:
                term_score = high_priority_applied / total_critical
                if high_priority_missed > 0:
                    issues.append(f"Critical terminology missed: {high_priority_missed} terms")
        
        quality_factors['terminology'] = term_score
        
        # 4. Content-type specific quality checks
        content_score = self._assess_content_specific_quality(source_text, translated_text, content_type)
        quality_factors['content_adaptation'] = content_score
        
        # 5. Basic fluency indicators
        fluency_score = self._assess_basic_fluency(translated_text, source_text)
        quality_factors['fluency'] = fluency_score
        
        # 6. Calculate overall quality score (Netflix weighted)
        weights = {
            'tag_preservation': 0.25,    # Critical for subtitle synchronization
            'terminology': 0.35,        # Most important for Netflix accuracy
            'content_adaptation': 0.25,  # Important for viewer experience
            'fluency': 0.15             # Basic requirement
        }
        
        overall_score = sum(quality_factors[factor] * weights[factor] 
                          for factor in weights.keys())
        
        # Log detailed scoring for analysis
        logger.debug(f"[NETFLIX_QC] Quality breakdown: {quality_factors}, Overall: {overall_score:.3f}")
        
        return overall_score, issues
    
    def _assess_content_specific_quality(self, source_text: str, translated_text: str, content_type: str) -> float:
        """Assess quality based on content type requirements."""
        
        # Content-specific quality indicators
        if content_type in ['sports', 'news']:
            # Check for preserved proper names and numbers
            import re
            source_numbers = re.findall(r'\b\d+\b', source_text)
            translated_numbers = re.findall(r'\b\d+\b', translated_text)
            
            if source_numbers and len(translated_numbers) != len(source_numbers):
                return 0.7  # Numbers are critical in sports/news
            
        elif content_type in ['educational', 'tutorial']:
            # Check for preserved technical terms (basic heuristic)
            source_caps = re.findall(r'\b[A-Z]{2,}\b', source_text)  # Acronyms
            if source_caps and not any(term in translated_text for term in source_caps):
                return 0.8  # Some technical preservation expected
                
        elif content_type == 'interview':
            # Check for natural conversational flow (basic length ratio)
            length_ratio = len(translated_text) / max(len(source_text), 1)
            if length_ratio > 2.0 or length_ratio < 0.3:
                return 0.7  # Unnatural expansion/contraction
        
        return 0.9  # Default good score
    
    def _assess_basic_fluency(self, translated_text: str, source_text: str) -> float:
        """Basic fluency assessment."""
        
        # Check for obvious issues
        issues = 0
        
        # 1. Repeated punctuation
        if re.search(r'[.!?]{3,}|[,;:]{2,}', translated_text):
            issues += 1
        
        # 2. Excessive spacing
        if '  ' in translated_text or translated_text != translated_text.strip():
            issues += 1
            
        # 3. Mixed language contamination (basic check)
        # Count Latin chars in Chinese text or vice versa
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', translated_text))
        latin_words = len(re.findall(r'\b[a-zA-Z]+\b', translated_text))
        
        total_chars = len(translated_text)
        if total_chars > 0:
            chinese_ratio = chinese_chars / total_chars
            if 0.2 < chinese_ratio < 0.8 and latin_words > 5:  # Mixed language suspicion
                issues += 1
        
        # 4. Very short translations for long source
        length_ratio = len(translated_text) / max(len(source_text), 1)
        if length_ratio < 0.2:  # Suspiciously short
            issues += 1
        
        # Convert issues to score
        max_issues = 4
        fluency_score = max(0.5, 1.0 - (issues / max_issues))
        
        return fluency_score
    
    def _ensure_chinese_consistency(self, text: str) -> str:
        """
        Ensure Chinese text consistency by converting to simplified Chinese.
        Addresses issues like mixed traditional/simplified characters.
        """
        # Common traditional to simplified character mapping for frequent errors
        char_map = {
            # Frequently mixed characters
            '醫': '医',  # doctor/medical
            '們': '们',  # plural marker
            '員': '员',  # member/staff
            '會': '会',  # can/meeting
            '過': '过',  # past tense marker
            '來': '来',  # come
            '時': '时',  # time
            '個': '个',  # classifier
            '這': '这',  # this
            '還': '还',  # still/yet
            '應': '应',  # should
            '為': '为',  # for/as
            '說': '说',  # say
            '開': '开',  # open
            '關': '关',  # close/about
            '問': '问',  # ask
            '見': '见',  # see
            '現': '现',  # now/current
            '實': '实',  # real
            '點': '点',  # point/o'clock
            '讓': '让',  # let/allow
            '聽': '听',  # listen/hear
            '買': '买',  # buy
            '賣': '卖',  # sell
            '錢': '钱',  # money
            '車': '车',  # car
            '業': '业',  # business
            '學': '学',  # learn/study
            '電': '电',  # electric
            '話': '话',  # talk/words
            '頭': '头',  # head
            '國': '国',  # country
            '際': '际',  # international
            '動': '动',  # move
            '進': '进',  # enter
            '門': '门',  # door
            '長': '长',  # long/chief
            '種': '种',  # kind/type
            '機': '机',  # machine
            '線': '线',  # line
            '網': '网',  # network
            '級': '级',  # level
            '極': '极',  # extreme
            '區': '区',  # area
            '歲': '岁',  # age
            '號': '号',  # number
            '術': '术',  # technique
            '視': '视',  # view
            '導': '导',  # guide
            '錄': '录',  # record
            '復': '复',  # repeat
            '據': '据',  # according to
            '標': '标',  # mark/standard
            '準': '准',  # accurate
            '確': '确',  # confirm
        }
        
        # Apply character conversion
        result = text
        for trad, simp in char_map.items():
            result = result.replace(trad, simp)
        
        # Log if conversions were made
        if result != text:
            changed_chars = [(t, s) for t, s in char_map.items() if t in text]
            logger.info(f"[CHINESE_CONSISTENCY] Converted traditional chars: {changed_chars}")
        
        return result
    
    def _create_term_patterns(self, src_term: str, priority_level: str) -> List:
        """Create regex patterns for term matching with priority-specific flexibility."""
        import re
        patterns = []
        
        # Escape the source term for regex
        escaped_term = re.escape(src_term)
        
        if priority_level == 'high':
            # High priority: stricter matching to avoid false positives
            patterns.append(re.compile(r'\b' + escaped_term + r'\b', re.IGNORECASE))
            # Also try exact case match for critical terms
            patterns.append(re.compile(r'\b' + re.escape(src_term) + r'\b'))
        else:
            # Medium/Low priority: more flexible matching
            patterns.append(re.compile(r'\b' + escaped_term + r'\b', re.IGNORECASE))
            
            # Add pattern for partial matches if term is multi-word
            if ' ' in src_term:
                words = src_term.split()
                if len(words) >= 2:
                    # Match any word order for compound terms
                    word_pattern = r'\b(?:' + '|'.join(re.escape(w) for w in words) + r')\b'
                    patterns.append(re.compile(word_pattern, re.IGNORECASE))
        
        return patterns
    
    def _apply_single_term(
        self, 
        text: str, 
        pattern, 
        tgt_text: str, 
        term_info: Dict, 
        metadata: Dict = None
    ) -> Tuple[str, int]:
        """Apply a single terminology term with context awareness."""
        import re
        
        # Find matches
        matches = list(pattern.finditer(text))
        if not matches:
            return text, 0
        
        # Determine if we should apply context-specific adjustments
        should_adjust = self._should_adjust_terminology_for_context(term_info, metadata)
        
        if should_adjust:
            # Apply context-adjusted translation
            adjusted_tgt = self._adjust_terminology_for_context(tgt_text, term_info, metadata)
        else:
            adjusted_tgt = tgt_text
        
        # Apply the replacement
        def replace_func(match):
            return adjusted_tgt
        
        new_text = pattern.sub(replace_func, text)
        replacement_count = len(matches)
        
        return new_text, replacement_count
    
    def _should_adjust_terminology_for_context(self, term_info: Dict, metadata: Dict = None) -> bool:
        """Determine if terminology should be context-adjusted."""
        if not metadata or 'summary' not in metadata:
            return False
        
        # Only adjust for certain categories and contexts
        category = term_info.get('category', '')
        priority = term_info.get('priority', 'medium')
        
        # High priority terms are generally not adjusted to maintain consistency
        if priority == 'high':
            return False
        
        # Only adjust concept and general terms, not technical or proper nouns
        adjustable_categories = ['concept', 'general', '']
        return category in adjustable_categories
    
    def _adjust_terminology_for_context(self, tgt_text: str, term_info: Dict, metadata: Dict) -> str:
        """Apply scene-aware adjustments to terminology translations."""
        if not metadata or 'summary' not in metadata:
            return tgt_text
        
        summary_data = metadata['summary']
        content_type = summary_data.get('content_type', 'other')
        expertise_level = summary_data.get('expertise_level', 'general')
        cultural_context = summary_data.get('cultural_context', 'general')
        
        # For now, return original - could be extended with specific adjustments
        # This is a placeholder for future context-specific terminology adjustments
        
        # Example future enhancements:
        # - Simplify technical terms for beginner expertise level
        # - Adapt cultural terms based on cultural_context
        # - Adjust formality based on content_type
        
        return tgt_text
    
    def _apply_semantic_optimization(
        self,
        initial_translation: str,
        source_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Dict = None,
        terminology: Dict = None,
        previous_text: str = None,
        next_text: str = None
    ) -> Tuple[str, Dict]:
        """
        Apply semantic and contextual optimization to improve translation quality beyond basic accuracy.
        
        This method analyzes the initial translation for potential improvements in:
        - Cultural adaptation and localization
        - Natural language flow and idioms
        - Context-appropriate expression choices
        - Professional terminology refinement
        
        Args:
            initial_translation: The initial translation result
            source_text: Original source text
            source_lang: Source language code
            target_lang: Target language code
            metadata: Enhanced metadata with scene information
            terminology: Terminology dictionary
            previous_text: Previous segment context
            next_text: Next segment context
            
        Returns:
            Tuple of (optimized_translation, optimization_stats)
        """
        logger.info("[SEMANTIC_OPTIMIZATION] Starting semantic and contextual optimization")
        
        # Initialize optimization statistics
        optimization_stats = {
            "optimized": False,
            "optimizations_applied": 0,
            "optimization_types": [],
            "quality_improvements": [],
            "original_length": len(initial_translation),
            "final_length": 0,
            "optimization_reason": []
        }
        
        # Skip optimization for very short texts or if no improvement opportunities
        if not initial_translation or len(initial_translation.strip()) < 10:
            logger.debug("[SEMANTIC_OPTIMIZATION] Skipping optimization for very short text")
            optimization_stats["final_length"] = len(initial_translation)
            return initial_translation, optimization_stats
        
        # Analyze optimization opportunities
        optimization_needs = self._analyze_optimization_opportunities(
            initial_translation, source_text, source_lang, target_lang, metadata, terminology
        )
        
        if not optimization_needs["needs_optimization"]:
            logger.info("[SEMANTIC_OPTIMIZATION] No significant optimization opportunities detected")
            optimization_stats["final_length"] = len(initial_translation)
            return initial_translation, optimization_stats
        
        # Extract scene information from metadata
        scene_info = self._extract_scene_context(metadata) if metadata else {}
        
        # Convert terminology to list format if needed
        terminology_list = []
        if terminology and isinstance(terminology, dict) and 'terms' in terminology:
            terminology_list = terminology['terms']
        elif isinstance(terminology, list):
            terminology_list = terminology
        
        # Build optimization prompt
        optimization_prompt = self._build_semantic_optimization_prompt(
            original_text=source_text,
            initial_translation=initial_translation,
            scene_info=scene_info,
            terminology=terminology_list
        )
        
        try:
            # Call LLM for semantic optimization
            logger.info("[SEMANTIC_OPTIMIZATION] Requesting LLM optimization")
            
            response = self.provider.translate(
                optimization_prompt,
                source_lang=target_lang,  # Set both to target language to avoid translation wrapper
                target_lang=target_lang,
                context={},
                metadata={"type": "semantic_optimization"}  # Indicate this is semantic optimization, not translation
            )
            
            optimized_text = str(response.get("translated_text", "")).strip()
            
            if not optimized_text or len(optimized_text) < 5:
                logger.warning("[SEMANTIC_OPTIMIZATION] LLM returned empty or invalid optimization")
                optimization_stats["final_length"] = len(initial_translation)
                return initial_translation, optimization_stats
            
            # Clean the optimization result
            cleaned_optimized = self._clean_optimization_response(optimized_text)
            
            # Validate optimization quality
            is_valid_optimization = self._validate_optimization_quality(
                original=source_text,
                initial=initial_translation,
                optimized=cleaned_optimized
            )
            
            if is_valid_optimization:
                # Update optimization statistics
                optimization_stats.update({
                    "optimized": True,
                    "optimizations_applied": len(optimization_needs["optimization_types"]),
                    "optimization_types": optimization_needs["optimization_types"],
                    "quality_improvements": optimization_needs["improvement_areas"],
                    "final_length": len(cleaned_optimized),
                    "optimization_reason": optimization_needs["reasons"]
                })
                
                logger.info(f"[SEMANTIC_OPTIMIZATION] Successfully optimized translation")
                logger.info(f"[SEMANTIC_OPTIMIZATION] Applied: {optimization_stats['optimization_types']}")
                logger.info(f"[SEMANTIC_OPTIMIZATION] Original: '{initial_translation}'")
                logger.info(f"[SEMANTIC_OPTIMIZATION] Optimized: '{cleaned_optimized}'")
                
                return cleaned_optimized, optimization_stats
            else:
                logger.info("[SEMANTIC_OPTIMIZATION] Optimization did not meet quality standards, keeping original")
                optimization_stats["final_length"] = len(initial_translation)
                return initial_translation, optimization_stats
                
        except Exception as e:
            logger.error(f"[SEMANTIC_OPTIMIZATION] Error during optimization: {str(e)}")
            optimization_stats["final_length"] = len(initial_translation)
            optimization_stats["error"] = str(e)
            return initial_translation, optimization_stats
    
    def _analyze_optimization_opportunities(
        self,
        initial_translation: str,
        source_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Dict = None,
        terminology: Dict = None
    ) -> Dict:
        """
        Analyze the initial translation for potential optimization opportunities.
        
        Returns:
            Dictionary containing optimization analysis results
        """
        opportunities = {
            "needs_optimization": False,
            "optimization_types": [],
            "improvement_areas": [],
            "reasons": [],
            "confidence_score": 0.0
        }
        
        # Get scene context 
        scene_info = self._extract_scene_context(metadata) if metadata else {}
        
        # Check for cultural adaptation opportunities
        if self._needs_cultural_adaptation(initial_translation, source_text, source_lang, target_lang, scene_info):
            opportunities["optimization_types"].append("cultural_adaptation")
            opportunities["improvement_areas"].append("Cultural localization")
            opportunities["reasons"].append("Detected expressions that could be more culturally appropriate")
        
        # Check for natural language flow improvements
        if self._needs_fluency_improvement(initial_translation, target_lang, scene_info):
            opportunities["optimization_types"].append("fluency_enhancement")
            opportunities["improvement_areas"].append("Natural language flow")
            opportunities["reasons"].append("Translation could be more natural and fluent")
        
        # Check for context-appropriate expression optimization
        if self._needs_context_optimization(initial_translation, source_text, scene_info):
            opportunities["optimization_types"].append("context_optimization")
            opportunities["improvement_areas"].append("Contextual appropriateness")
            opportunities["reasons"].append("More context-appropriate expressions available")
        
        # Check for professional terminology refinement
        if self._needs_terminology_refinement(initial_translation, terminology, scene_info):
            opportunities["optimization_types"].append("terminology_refinement")
            opportunities["improvement_areas"].append("Professional terminology")
            opportunities["reasons"].append("Professional terminology could be refined")
        
        # Determine if optimization is needed
        opportunities["needs_optimization"] = len(opportunities["optimization_types"]) > 0
        opportunities["confidence_score"] = min(len(opportunities["optimization_types"]) * 0.3, 1.0)
        
        return opportunities
    
    def _extract_scene_context(self, metadata: Dict) -> Dict:
        """Extract relevant scene context from metadata."""
        if not metadata or 'summary' not in metadata:
            return {"content_type": "other", "domain": "general", "expertise_level": "general"}
        
        summary = metadata['summary']
        return {
            "content_type": summary.get("content_type", "other"),
            "domain": summary.get("domain_context", "general"),
            "expertise_level": summary.get("expertise_level", "general"),
            "cultural_context": summary.get("cultural_context", "general"),
            "emotional_undertone": summary.get("emotional_undertone", "neutral"),
            "communication_purpose": summary.get("communication_purpose", "educate_and_inform")
        }
    
    def _needs_cultural_adaptation(self, translation: str, source_text: str, source_lang: str, target_lang: str, scene_info: Dict) -> bool:
        """Check if translation needs cultural adaptation."""
        # For Chinese target language, check for common adaptation opportunities
        if target_lang == 'zh':
            # Check for Western cultural concepts that could be localized
            western_concepts = ['coffee shop', 'baseball', 'thanksgiving', 'black friday', 'super bowl']
            for concept in western_concepts:
                if concept.lower() in source_text.lower():
                    return True
        
        # Check based on cultural context
        cultural_context = scene_info.get("cultural_context", "general")
        if cultural_context in ["western_formal", "eastern_formal"] and "general" in cultural_context:
            return True
        
        # Check for content types that often need cultural adaptation
        content_type = scene_info.get("content_type", "other")
        if content_type in ["promotional", "entertainment", "interview"]:
            return True
            
        return False
    
    def _needs_fluency_improvement(self, translation: str, target_lang: str, scene_info: Dict) -> bool:
        """Check if translation needs fluency improvement."""
        # Check for awkward patterns in Chinese
        if target_lang == 'zh':
            # Check for common fluency issues
            awkward_patterns = [
                r'的的',  # Repeated 的
                r'在在',  # Repeated 在
                r'[，。]{2,}',  # Multiple punctuation
                r'[a-zA-Z]\s*[，。]',  # English followed by Chinese punctuation without space
            ]
            
            import re
            for pattern in awkward_patterns:
                if re.search(pattern, translation):
                    return True
        
        # Check based on content type
        content_type = scene_info.get("content_type", "other")
        if content_type in ["tutorial", "interview", "entertainment"]:
            # These content types benefit from more natural, conversational language
            return True
            
        return False
    
    def _needs_context_optimization(self, translation: str, source_text: str, scene_info: Dict) -> bool:
        """Check if translation needs context-specific optimization."""
        content_type = scene_info.get("content_type", "other")
        expertise_level = scene_info.get("expertise_level", "general")
        
        # Technical content for beginners often needs simplification
        if content_type == "educational" and expertise_level == "beginner":
            return True
        
        # Business content needs professional tone
        if content_type == "presentation" and "business" in scene_info.get("domain", ""):
            return True
        
        # Tutorial content needs clear, actionable language
        if content_type == "tutorial":
            return True
            
        return False
    
    def _needs_terminology_refinement(self, translation: str, terminology: Dict, scene_info: Dict) -> bool:
        """Check if translation needs terminology refinement."""
        if not terminology or not terminology.get('terms'):
            return False
        
        # Check if high-priority terms could be better applied
        high_priority_terms = [t for t in terminology['terms'] if t.get('priority') == 'high']
        if len(high_priority_terms) > 2:  # If there are many important terms
            return True
        
        # Check for technical domains that benefit from terminology refinement
        domain = scene_info.get("domain", "general")
        if domain in ["technology", "science", "medicine", "finance"]:
            return True
            
        return False
    
    def _build_semantic_optimization_prompt(self, original_text: str, initial_translation: str, 
                                          scene_info: Dict[str, Any], terminology: List[Dict]) -> str:
        """Build prompt for semantic optimization based on scene context."""
        try:
            # Extract key scene characteristics
            content_type = scene_info.get("content_type", "general")
            domain = scene_info.get("domain", "general")
            style = scene_info.get("presentation_style", "neutral")
            expertise = scene_info.get("expertise_level", "general")
            cultural_context = scene_info.get("cultural_context", "neutral")
            
            # Build context-aware optimization prompt
            prompt = f"""Optimize the following translation to better match the specific scene and context requirements:

Original Text:
{original_text}

Initial Translation:
{initial_translation}

Scene Information:
- Content Type: {content_type}
- Domain: {domain}
- Style: {style}
- Expertise Level: {expertise}
- Cultural Context: {cultural_context}

Optimization Requirements:
1. Ensure translation accuracy and fluency
2. Adjust language style and technical terminology usage based on scene
3. Consider target language expression habits
4. Preserve original tone and emotional color
5. Optimize professional expressions for specific domains

CRITICAL: Preserve ALL numbered tags [N] exactly as they appear in the initial translation. Do not remove, modify, or merge tags.

Please provide ONLY the optimized translation without explanations or commentary:"""

            # Add terminology context if available
            if terminology:
                high_priority = [t for t in terminology if t.get("priority") == "high" and t.get('src') and t.get('tgt')]
                if high_priority:
                    terms_text = ", ".join([f"{t['src']} → {t['tgt']}" for t in high_priority[:5]])
                    prompt += f"\n\nImportant Terminology Reference: {terms_text}"
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error building semantic optimization prompt: {e}")
            return f"请优化以下翻译：\n原文：{original_text}\n初译：{initial_translation}"
    
    def _clean_optimization_response(self, response_text: str) -> str:
        """Clean and extract optimized translation from response."""
        try:
            if not response_text:
                return ""
            
            # Look for common markers indicating the optimized translation
            markers = [
                "优化后的翻译：",
                "优化翻译：",
                "建议翻译：",
                "最终翻译：",
                "翻译结果：",
                "Optimized translation:",
                "Final translation:"
            ]
            
            # Try to extract translation after markers
            for marker in markers:
                if marker in response_text:
                    parts = response_text.split(marker, 1)
                    if len(parts) > 1:
                        # Extract the translation part
                        translation_part = parts[1].strip()
                        # Stop at explanation markers
                        explanation_markers = ["优化理由：", "解释：", "说明：", "Explanation:", "Reason:"]
                        for exp_marker in explanation_markers:
                            if exp_marker in translation_part:
                                translation_part = translation_part.split(exp_marker)[0].strip()
                                break
                        
                        # Clean up formatting
                        cleaned = translation_part.strip(' "\'`\n\t')
                        if cleaned:
                            return cleaned
            
            # If no markers found, try to extract first substantial line
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            if lines:
                # Skip lines that look like headers or instructions
                for line in lines:
                    if not any(marker.replace('：', '').replace(':', '') in line.lower() 
                             for marker in ['原文', '初译', '优化', '理由', 'original', 'initial', 'reason']):
                        if len(line) > 5:  # Substantial content
                            return line.strip(' "\'`')
            
            # Fallback: return cleaned response
            return response_text.strip(' "\'`\n\t')
            
        except Exception as e:
            logger.error(f"Error cleaning optimization response: {e}")
            return response_text.strip() if response_text else ""
    
    def _validate_optimization_quality(self, original: str, initial: str, optimized: str) -> bool:
        """Validate the quality of semantic optimization."""
        try:
            if not optimized or optimized == initial:
                return False
            
            # Length validation - optimized shouldn't be drastically different
            len_ratio = len(optimized) / max(len(initial), 1)
            if len_ratio < 0.3 or len_ratio > 3.0:
                logger.warning(f"Optimization length ratio suspicious: {len_ratio}")
                return False
            
            # Content validation - should contain substantial text
            if len(optimized.strip()) < 5:
                return False
            
            # Quality indicators - optimized should be different but related
            common_chars = set(optimized.lower()) & set(initial.lower())
            if len(common_chars) < min(5, len(initial) // 3):
                logger.warning("Optimization seems unrelated to initial translation")
                return False
            
            # Check for obvious errors or artifacts
            error_indicators = [
                "错误", "error", "failed", "无法", "cannot",
                "###", "```", "ERROR", "FAIL"
            ]
            
            if any(indicator in optimized.lower() for indicator in error_indicators):
                logger.warning("Optimization contains error indicators")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating optimization quality: {e}")
            return False
