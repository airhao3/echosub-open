import os
import re
from json_repair import json_repair
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, TypedDict
import difflib
import math

from app.core.config import settings
from app.services.translation_providers.yunwu_provider import YunwuTranslationProvider

class Job:
    def __init__(self, id):
        self.id = id

# Language code to name mapping
LANG_CODE_TO_NAME = {
    'en': 'English', 'zh': 'Chinese', 'es': 'Spanish', 'fr': 'French',
    'de': 'German', 'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian',
    'ar': 'Arabic', 'pt': 'Portuguese', 'it': 'Italian', 'hi': 'Hindi',
    'auto': 'Auto-detected'
}

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

class SubtitleSegment(TypedDict):
    """Represents a segmented subtitle with metadata"""
    id: int          # Segment ID
    text: str        # Text content of the segment
    start_char: int  # Start character position in original text
    end_char: int    # End character position in original text

class SemanticService:
    """
    Service for semantic text segmentation and related NLP tasks.
    Uses LLM for semantic understanding with fallback to rule-based methods.
    """
    
    def __init__(self):
        provider_name = settings.TRANSLATION_PROVIDER
        self.config = {
            "provider": provider_name,
            "yunwu": {
                "api_key": settings.YUNWU_API_KEY,
                "base_url": settings.YUNWU_BASE_URL,
                "model": settings.YUNWU_MODEL,
                "temperature": settings.YUNWU_TEMPERATURE,
                "max_tokens": settings.YUNWU_MAX_TOKENS,
                "timeout": settings.YUNWU_TIMEOUT,
            },
            "translator": {
                "api_key": settings.TRANSLATOR_API_KEY,
                "base_url": settings.TRANSLATOR_BASE_URL,
                "model": settings.TRANSLATOR_MODEL,
                "temperature": settings.TRANSLATOR_TEMPERATURE,
                "max_tokens": settings.TRANSLATOR_MAX_TOKENS,
                "timeout": settings.TRANSLATOR_TIMEOUT,
            }
        }
        
        # 根据provider选择配置
        if provider_name == "translator":
            self.provider = YunwuTranslationProvider(self.config["translator"])
            logger.info("SemanticService initialized with translator provider.")
        else:  # yunwu或其他
            self.provider = YunwuTranslationProvider(self.config["yunwu"])
            logger.info("SemanticService initialized with yunwu provider.")

    def _get_semantic_split_prompt(self, text: str, marker: str, target_length_words: int) -> str:
        """
        Generate a prompt for semantic text segmentation.
        
        Args:
            text: The text to be segmented
            marker: The marker to use for segment boundaries
            target_length_words: Target length in words for each segment
            
        Returns:
            A formatted prompt for semantic segmentation
        """
        return f"""Given the following text, split it into meaningful segments using '{marker}' as the separator. 
        Each segment should be approximately {target_length_words} words long, but prioritize maintaining semantic coherence. 
        Ensure that each segment is a complete thought or idea.
        
        Text: {text}
        """
        
    def generate_summary_and_terminology(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> Dict:
        """
        Generate summary and extract terminology from the given text
        
        Args:
            text: Source text to analyze
            source_lang: Source language code
            target_lang: Target language code
            domain: Optional domain/category of the content
            job_id: Optional job ID for logging
            
        Returns:
            Dictionary containing summary and terminology
        """
        logger.info(f"[SEMANTIC] Starting summary and terminology generation for job_id={job_id}")
        logger.info(f"[SEMANTIC] Input text length: {len(text)} chars, source_lang={source_lang}, target_lang={target_lang}, domain={domain}")
        
        # Generate summary
        logger.info(f"[SEMANTIC] Generating summary for job_id={job_id}")
        summary = self.generate_summary(text, source_lang, job_id)
        logger.info(f"[SEMANTIC] Summary generation completed, length={len(summary)} chars")
        
        # Extract terminology
        logger.info(f"[SEMANTIC] Extracting terminology for job_id={job_id}, source={source_lang}, target={target_lang}")
        
        # Create a temporary job object for terminology extraction
        class TempJob:
            def __init__(self, job_id):
                self.id = job_id
        
        temp_job = TempJob(job_id) if job_id else TempJob("unknown")
        
        terminology = self.extract_terminology(
            job=temp_job,
            text=text,
            domain=domain or "general",
            source_lang=source_lang,
            target_lang=target_lang,
            output_path=None,
            content_analysis=None
        )
        term_count = len(terminology.get('terms', []))
        logger.info(f"[SEMANTIC] Terminology extraction completed, found {term_count} terms")
            
        result = {
            "summary": summary,
            "terminology": terminology,
            "status": "success"
        }
        logger.info(f"[SEMANTIC] Summary and terminology generation successful for job_id={job_id}")
        return result
            
   

    def _handle_summary_error(self, job_id: str, error: Exception) -> Dict:
        """Handle errors in summary generation"""
        logger.error(f"[SEMANTIC] Error in generate_summary_and_terminology for job_id={job_id}: {str(error)}", exc_info=True)
        return {
                "summary": "",
                "terminology": {"terms": []},
                "status": "error",
                "error": str(e)
            }
    
    def _clean_and_parse_json(self, raw_text: str, job_id: Optional[str] = None, context: str = "default") -> Optional[Dict]:
        """
        Cleans and parses a JSON object from a raw string, which may contain markdown or other text.
        This function is designed to be robust against common LLM response variations.
        
        Args:
            raw_text: The raw string response from the LLM.
            job_id: Optional job ID for logging.
            context: A string indicating the context of the call (e.g., 'summary', 'terminology').

        Returns:
            A dictionary if parsing is successful, otherwise None.
        """
        logger.info(f"[{context.upper()}] Cleaning and parsing JSON for job_id={job_id}")

        json_str = None
        
        # 1. Try to find a JSON markdown block, which is the most reliable format.
        # This regex handles ```json ... ``` and ``` ... ```, ensuring the content is a valid JSON object or array.
        match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", raw_text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            logger.info(f"[{context.upper()}] Extracted JSON from markdown code block for job_id={job_id}")
        else:
            # 2. If no markdown block is found, find the first '{' or '[' and the last '}' or ']'.
            # This is a more aggressive fallback for responses without proper markdown.
            start_brace = raw_text.find('{')
            start_bracket = raw_text.find('[')
            
            start_pos = -1
            
            # Find the first occurrence of either '{' or '['
            if start_brace != -1 and start_bracket != -1:
                start_pos = min(start_brace, start_bracket)
            elif start_brace != -1:
                start_pos = start_brace
            elif start_bracket != -1:
                start_pos = start_bracket
                
            if start_pos != -1:
                # Find the last occurrence of either '}' or ']'
                end_brace = raw_text.rfind('}')
                end_bracket = raw_text.rfind(']')
                end_pos = max(end_brace, end_bracket)
                
                if end_pos > start_pos:
                    json_str = raw_text[start_pos : end_pos + 1]
                    logger.info(f"[{context.upper()}] Extracted potential JSON by finding first/last brackets for job_id={job_id}")

        if not json_str:
            logger.warning(f"[{context.upper()}] Could not find a valid JSON string in the raw text for job_id={job_id}")
            logger.debug(f"[{context.upper()}] Raw text: {raw_text[:500]}...")
            return None

        # 3. Use json_repair for robust parsing
        try:
            repaired_json = json_repair.loads(json_str)
            logger.info(f"[{context.upper()}] Successfully parsed JSON for job_id={job_id}")
            return repaired_json
        except Exception as e:
            logger.error(f"[{context.upper()}] Final JSON parsing failed for job_id={job_id}: {e}")
            logger.debug(f"[{context.upper()}] Faulty JSON string: {json_str[:500]}...")
            return None

    def generate_summary(
        self,
        text: str,
        source_lang: str,
        job_id: Optional[str] = None
    ) -> str:
        """
        Generate a comprehensive content analysis with enhanced scene-aware dimensions for improved translation.
        
        Args:
            text: Input text to analyze
            source_lang: Source language code
            job_id: Optional job ID for logging
            
        Returns:
            JSON string containing structured analysis with scene-aware insights for translation optimization
        """
        logger.info(f"[SUMMARY] Generating enhanced content analysis with scene-aware dimensions for job_id={job_id}")
        
        json_example = '''{
  "content_overview": "The video explains the basics of quantum computing. It emphasizes how qubits differ from classical bits, enabling new computational possibilities.",
  "tone_style": "Informative and slightly technical, but accessible",
  "target_audience": "General public with an interest in technology",
  "content_type": "educational",
  "domain_context": "technology",
  "presentation_style": "explanatory",
  "emotional_undertone": "enthusiastic",
  "cultural_context": "western_academic",
  "expertise_level": "intermediate",
  "translation_strategy": "technical_accuracy_with_accessibility",
  "key_concepts": ["quantum computing", "qubits", "classical bits"],
  "communication_purpose": "educate_and_inform"
}'''
        prompt = f"""You are an expert content analyst, specializing in understanding video scripts for advanced translation and localization. 
Your task is to analyze the provided text and extract comprehensive scene-aware information to optimize translation quality.

TEXT TO ANALYZE:
{text}

INSTRUCTIONS:
Analyze the text and provide the following information:

1. **Content Overview (content_overview)**: Provide a two-sentence summary capturing the main topic and key takeaway.

2. **Tone and Style (tone_style)**: Describe the primary tone and style (e.g., informative, conversational, formal, technical).

3. **Target Audience (target_audience)**: Identify the intended audience (e.g., experts, general public, professionals).

4. **Content Type (content_type)**: Classify the content type:
   - "educational" - Teaching or explaining concepts
   - "entertainment" - Comedy, drama, storytelling
   - "promotional" - Marketing, advertising, sales
   - "news" - News reporting, journalism
   - "interview" - Conversations, Q&A sessions
   - "tutorial" - Step-by-step instructions
   - "documentary" - Factual exploration
   - "presentation" - Business or academic presentations
   - "review" - Product/service reviews
   - "other" - If none of the above fit

5. **Domain Context (domain_context)**: Identify the primary domain:
   - "technology", "business", "science", "medicine", "education", "entertainment", 
   - "sports", "politics", "lifestyle", "finance", "legal", "other"

6. **Presentation Style (presentation_style)**: How is the information presented:
   - "narrative" - Story-telling approach
   - "explanatory" - Step-by-step explanation
   - "demonstrative" - Showing through examples
   - "conversational" - Dialogue or chat style
   - "lecture" - Formal presentation style
   - "interview" - Question and answer format

7. **Emotional Undertone (emotional_undertone)**: The underlying emotional quality:
   - "neutral", "enthusiastic", "serious", "humorous", "urgent", "calm", "passionate", "analytical"

8. **Cultural Context (cultural_context)**: Cultural or regional approach:
   - "western_formal", "western_casual", "eastern_formal", "eastern_casual", 
   - "academic", "business", "youth_oriented", "general"

9. **Expertise Level (expertise_level)**: Required knowledge level:
   - "beginner", "intermediate", "advanced", "expert", "general"

10. **Translation Strategy (translation_strategy)**: Recommended approach:
    - "literal_accuracy" - Precise word-for-word translation
    - "cultural_adaptation" - Adapt for cultural understanding
    - "technical_accuracy_with_accessibility" - Technical precision but accessible
    - "creative_localization" - Creative adaptation for target culture
    - "formal_professional" - Professional/business tone
    - "casual_conversational" - Natural, everyday language

11. **Key Concepts (key_concepts)**: List 3-5 most important terms/concepts (array of strings).

12. **Communication Purpose (communication_purpose)**: Primary intent:
    - "educate_and_inform", "persuade_and_convince", "entertain_and_engage", 
    - "instruct_and_guide", "report_and_document", "promote_and_sell"

IMPORTANT: Analyze EXACTLY what is written without modification. Provide objective analysis based solely on the content.

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object with all 12 keys. Use the exact key names specified above.
Example:
```json
{json_example}
```

Your response (JSON object only):
"""
        try:
            # Use the translation provider to call the LLM
            logger.info("[SUMMARY] Sending content analysis request to LLM")
            response = self.provider.translate(
                prompt,  # The prompt is now a complete f-string
                source_lang,
                "en",  # Always get analysis in English for consistency
                metadata={"type": "content_analysis"}
            )
            
            raw_response = str(response.get("translated_text", "{}")).strip()
            
            analysis_json = self._clean_and_parse_json(raw_response, job_id, context="summary")

            if analysis_json and isinstance(analysis_json, dict):
                # Validate and enhance the analysis with default values
                validated_analysis = self._validate_and_enhance_summary_json(analysis_json, source_lang, job_id)
                logger.info(f"[SUMMARY] Successfully parsed and validated content analysis for job_id={job_id}")
                return json.dumps(validated_analysis, ensure_ascii=False, indent=2)
            else:
                logger.error(f"[SUMMARY] Failed to parse analysis as JSON after cleaning for job_id={job_id}")
                logger.debug(f"[SUMMARY] Raw analysis content: {raw_response[:500]}...")
                # Return a minimal valid JSON with the error
                fallback_analysis = self._get_fallback_summary_json(source_lang, job_id, "Failed to parse analysis as JSON", raw_response[:1000])
                return json.dumps(fallback_analysis, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[SUMMARY] Error generating content analysis: {str(e)}", exc_info=True)
            # Return minimal valid JSON structure if analysis fails
            fallback_analysis = self._get_fallback_summary_json(source_lang, job_id, "Failed to generate content analysis", str(e))
            return json.dumps(fallback_analysis, ensure_ascii=False)
    
    def _validate_and_enhance_summary_json(self, analysis_json: Dict, source_lang: str, job_id: Optional[str] = None) -> Dict:
        """
        Validate summary JSON and add missing fields with intelligent defaults
        
        Args:
            analysis_json: Raw analysis JSON from LLM
            source_lang: Source language code
            job_id: Optional job ID for logging
            
        Returns:
            Enhanced and validated analysis JSON with all required fields
        """
        logger.debug(f"[SUMMARY_VALIDATION] Validating and enhancing summary JSON for job_id={job_id}")
        
        # Define default values for all expected fields
        defaults = {
            "content_overview": "Content analysis not available",
            "tone_style": "Unable to determine",
            "target_audience": "General audience",
            "content_type": "other",
            "domain_context": "other",
            "presentation_style": "explanatory",
            "emotional_undertone": "neutral",
            "cultural_context": "general",
            "expertise_level": "general",
            "translation_strategy": "technical_accuracy_with_accessibility",
            "key_concepts": [],
            "communication_purpose": "educate_and_inform"
        }
        
        # Start with a copy of the original analysis
        enhanced_analysis = analysis_json.copy()
        
        # Fill in missing fields with defaults
        for field, default_value in defaults.items():
            if field not in enhanced_analysis or enhanced_analysis[field] is None or enhanced_analysis[field] == "":
                enhanced_analysis[field] = default_value
                logger.debug(f"[SUMMARY_VALIDATION] Added default value for missing field '{field}': {default_value}")
        
        # Validate and clean specific fields
        enhanced_analysis = self._clean_summary_field_values(enhanced_analysis)
        
        # Add metadata
        enhanced_analysis["metadata"] = {
            "analysis_version": "2.0",  # Updated version for enhanced analysis
            "source_language": source_lang,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "job_id": job_id,
            "enhanced": True,
            "validation_passed": True
        }
        
        logger.debug(f"[SUMMARY_VALIDATION] Successfully validated and enhanced summary for job_id={job_id}")
        return enhanced_analysis
    
    def _clean_summary_field_values(self, analysis: Dict) -> Dict:
        """
        Clean and validate individual field values in the summary analysis
        
        Args:
            analysis: Analysis dictionary to clean
            
        Returns:
            Cleaned analysis dictionary
        """
        # Ensure key_concepts is always a list
        if not isinstance(analysis.get("key_concepts"), list):
            if isinstance(analysis.get("key_concepts"), str):
                # Try to convert string to list
                key_concepts_str = analysis["key_concepts"].strip()
                if key_concepts_str:
                    # Split by common delimiters
                    concepts = [c.strip() for c in re.split(r'[,;|]', key_concepts_str) if c.strip()]
                    analysis["key_concepts"] = concepts[:5]  # Limit to 5 concepts
                else:
                    analysis["key_concepts"] = []
            else:
                analysis["key_concepts"] = []
        else:
            # Ensure we don't have more than 5 concepts and they're all strings
            concepts = [str(concept).strip() for concept in analysis["key_concepts"][:5] if str(concept).strip()]
            analysis["key_concepts"] = concepts
        
        # Validate content_type against allowed values
        valid_content_types = [
            "educational", "entertainment", "promotional", "news", "interview", 
            "tutorial", "documentary", "presentation", "review", "other"
        ]
        if analysis.get("content_type") not in valid_content_types:
            analysis["content_type"] = "other"
        
        # Validate domain_context against allowed values
        valid_domains = [
            "technology", "business", "science", "medicine", "education", "entertainment",
            "sports", "politics", "lifestyle", "finance", "legal", "other"
        ]
        if analysis.get("domain_context") not in valid_domains:
            analysis["domain_context"] = "other"
        
        # Validate presentation_style
        valid_presentation_styles = [
            "narrative", "explanatory", "demonstrative", "conversational", "lecture", "interview"
        ]
        if analysis.get("presentation_style") not in valid_presentation_styles:
            analysis["presentation_style"] = "explanatory"
        
        # Validate emotional_undertone
        valid_emotions = [
            "neutral", "enthusiastic", "serious", "humorous", "urgent", "calm", "passionate", "analytical"
        ]
        if analysis.get("emotional_undertone") not in valid_emotions:
            analysis["emotional_undertone"] = "neutral"
        
        # Validate cultural_context
        valid_cultural_contexts = [
            "western_formal", "western_casual", "eastern_formal", "eastern_casual",
            "academic", "business", "youth_oriented", "general"
        ]
        if analysis.get("cultural_context") not in valid_cultural_contexts:
            analysis["cultural_context"] = "general"
        
        # Validate expertise_level
        valid_expertise_levels = ["beginner", "intermediate", "advanced", "expert", "general"]
        if analysis.get("expertise_level") not in valid_expertise_levels:
            analysis["expertise_level"] = "general"
        
        # Validate translation_strategy
        valid_translation_strategies = [
            "literal_accuracy", "cultural_adaptation", "technical_accuracy_with_accessibility",
            "creative_localization", "formal_professional", "casual_conversational"
        ]
        if analysis.get("translation_strategy") not in valid_translation_strategies:
            analysis["translation_strategy"] = "technical_accuracy_with_accessibility"
        
        # Validate communication_purpose
        valid_purposes = [
            "educate_and_inform", "persuade_and_convince", "entertain_and_engage",
            "instruct_and_guide", "report_and_document", "promote_and_sell"
        ]
        if analysis.get("communication_purpose") not in valid_purposes:
            analysis["communication_purpose"] = "educate_and_inform"
        
        return analysis
    
    def _get_fallback_summary_json(self, source_lang: str, job_id: Optional[str], error: str, details: str) -> Dict:
        """
        Generate a fallback summary JSON with all required fields when analysis fails
        
        Args:
            source_lang: Source language code
            job_id: Optional job ID for logging
            error: Error message
            details: Error details
            
        Returns:
            Complete fallback analysis JSON
        """
        return {
            "content_overview": "Analysis failed due to processing error",
            "tone_style": "Unable to determine",
            "target_audience": "General audience",
            "content_type": "other",
            "domain_context": "other", 
            "presentation_style": "explanatory",
            "emotional_undertone": "neutral",
            "cultural_context": "general",
            "expertise_level": "general",
            "translation_strategy": "technical_accuracy_with_accessibility",
            "key_concepts": [],
            "communication_purpose": "educate_and_inform",
            "error": error,
            "error_details": details[:1000],  # Limit error details length
            "metadata": {
                "analysis_version": "2.0",
                "source_language": source_lang,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "job_id": job_id,
                "enhanced": False,
                "validation_passed": False,
                "fallback_used": True
            }
        }
    
    # ============================================================
    # Step 2: Content Understanding & Correction (Post-Transcription)
    # ============================================================

    # Maximum lines per window for LLM calls
    WINDOW_SIZE = 100

    def scan_content(
        self,
        text: str,
        source_lang: str,
        job_id: Optional[str] = None
    ) -> Dict:
        """
        Step 2.1 — Global scan with sliding-window progressive summarization.

        For short texts (<=WINDOW_SIZE lines): single LLM call (original behaviour).
        For long texts: process in windows, summarize each, then merge summaries
        into a final global analysis + scene list.
        """
        logger.info(f"[SCAN_CONTENT] Starting global content scan for job_id={job_id}")

        if not source_lang or source_lang.lower() == 'auto':
            source_lang = 'en'

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        total_lines = len(lines)
        logger.info(f"[SCAN_CONTENT] Input: {total_lines} lines, {len(text)} chars")

        if total_lines <= self.WINDOW_SIZE:
            return self._scan_single_window(lines, total_lines, source_lang, job_id)
        else:
            return self._scan_multi_window(lines, total_lines, source_lang, job_id)

    # ── Short text: single call (unchanged logic) ──────────────────

    def _scan_single_window(self, lines: List[str], total_lines: int,
                            source_lang: str, job_id: Optional[str]) -> Dict:
        lang_name = LANG_CODE_TO_NAME.get(source_lang, source_lang)
        text = '\n'.join(lines)

        json_example = '{"global_analysis":{"content_overview":"...","domain":"...","tone":"...","content_type":"...","key_terms":[{"term":"...","explanation":"..."}],"speaker_info":"...","target_audience":"..."},"scenes":[{"scene_id":1,"start_line":1,"end_line":15,"topic":"..."}]}'

        prompt = f"""You are an expert content analyst specializing in video transcription analysis.

TASK: Analyze the following transcription and:
1. Produce a global content analysis (domain, tone, key terms, etc.)
2. Divide the content into natural SCENES based on topic shifts, speaker changes, or structural transitions.

TRANSCRIPTION ({lang_name}, {total_lines} lines):
{text}

INSTRUCTIONS FOR SCENE DIVISION:
- Each scene should represent a coherent topic or segment (NOT fixed-size chunks)
- Identify natural breakpoints: topic changes, speaker switches, transitions
- Every line must belong to exactly one scene, with no gaps or overlaps
- start_line and end_line refer to the [N] tag numbers in the transcription

INSTRUCTIONS FOR KEY TERMS:
- Extract 5-15 important terms (proper nouns, technical terms, domain-specific vocabulary)

OUTPUT: Return ONLY valid JSON: {json_example}
Your response (JSON only):"""

        try:
            response = self.provider.translate(prompt, source_lang, "en",
                                               metadata={"type": "content_scan"})
            raw = str(response.get("translated_text", "{}")).strip()
            result = self._clean_and_parse_json(raw, job_id, context="scan_content")
            if result and isinstance(result, dict):
                scenes = result.get('scenes', [])
                if not scenes:
                    result['scenes'] = [{"scene_id": 1, "start_line": 1,
                                         "end_line": total_lines, "topic": "Full content"}]
                else:
                    result['scenes'] = self._validate_scene_boundaries(scenes, total_lines, job_id)
                result.setdefault('global_analysis', self._empty_global_analysis())
                logger.info(f"[SCAN_CONTENT] Single-window: {len(result['scenes'])} scenes for job_id={job_id}")
                return result
        except Exception as e:
            logger.error(f"[SCAN_CONTENT] Single-window error: {e}", exc_info=True)
        return self._get_fallback_scan_result(total_lines)

    # ── Long text: sliding-window with progressive summarization ───

    def _scan_multi_window(self, lines: List[str], total_lines: int,
                           source_lang: str, job_id: Optional[str]) -> Dict:
        lang_name = LANG_CODE_TO_NAME.get(source_lang, source_lang)
        window = self.WINDOW_SIZE

        # Phase 1: scan each window → get local scenes + summary
        window_results = []
        running_summary = ""

        for start in range(0, total_lines, window):
            end = min(start + window, total_lines)
            chunk_lines = lines[start:end]
            chunk_text = '\n'.join(chunk_lines)
            first_tag = start + 1
            last_tag = end

            context_block = ""
            if running_summary:
                context_block = f"\nPREVIOUS CONTENT SUMMARY:\n{running_summary}\n"

            prompt = f"""You are an expert content analyst. Analyze this SEGMENT of a longer transcription.
{context_block}
SEGMENT ({lang_name}, lines {first_tag}-{last_tag} of {total_lines}):
{chunk_text}

Return ONLY valid JSON:
{{
  "summary": "2-3 sentence summary of THIS segment",
  "domain": "topic domain",
  "key_terms": [{{"term":"...","explanation":"..."}}],
  "scenes": [{{"scene_id":1,"start_line":{first_tag},"end_line":{last_tag},"topic":"..."}}]
}}

SCENE RULES:
- start_line/end_line must be within {first_tag}-{last_tag}
- Split into natural scenes based on topic shifts
- Each scene should be 10-40 lines

Your response (JSON only):"""

            logger.info(f"[SCAN_CONTENT] Window {first_tag}-{last_tag}/{total_lines} for job_id={job_id}")
            try:
                resp = self.provider.translate(prompt, source_lang, "en",
                                               metadata={"type": "content_scan"})
                raw = str(resp.get("translated_text", "{}")).strip()
                parsed = self._clean_and_parse_json(raw, job_id,
                                                     context=f"scan_window_{first_tag}_{last_tag}")
                if parsed and isinstance(parsed, dict):
                    window_results.append(parsed)
                    # Accumulate running summary for next window
                    new_summary = parsed.get('summary', '')
                    if new_summary:
                        running_summary = f"{running_summary} {new_summary}".strip()
                        # Keep running summary compact (last 500 chars)
                        if len(running_summary) > 500:
                            running_summary = running_summary[-500:]
                else:
                    # Fallback: single scene for this window
                    window_results.append({
                        "summary": "",
                        "scenes": [{"scene_id": 1, "start_line": first_tag,
                                    "end_line": last_tag, "topic": "Content"}]
                    })
            except Exception as e:
                logger.error(f"[SCAN_CONTENT] Window {first_tag}-{last_tag} error: {e}")
                window_results.append({
                    "summary": "",
                    "scenes": [{"scene_id": 1, "start_line": first_tag,
                                "end_line": last_tag, "topic": "Content"}]
                })

        # Phase 2: merge all window results
        all_scenes = []
        all_key_terms = []
        all_summaries = []
        domain_votes = []

        for wr in window_results:
            for scene in wr.get('scenes', []):
                all_scenes.append(scene)
            for term in wr.get('key_terms', []):
                all_key_terms.append(term)
            if wr.get('summary'):
                all_summaries.append(wr['summary'])
            if wr.get('domain'):
                domain_votes.append(wr['domain'])

        # Re-number scenes sequentially
        for i, scene in enumerate(all_scenes):
            scene['scene_id'] = i + 1

        # Validate boundaries
        all_scenes = self._validate_scene_boundaries(all_scenes, total_lines, job_id)

        # Deduplicate key terms
        seen_terms = set()
        unique_terms = []
        for term in all_key_terms:
            t = term.get('term', '') if isinstance(term, dict) else str(term)
            if t.lower() not in seen_terms:
                seen_terms.add(t.lower())
                unique_terms.append(term)

        # Build global analysis from merged summaries
        overview = ' '.join(all_summaries)
        if len(overview) > 500:
            overview = overview[:500] + '...'

        domain = max(set(domain_votes), key=domain_votes.count) if domain_votes else "general"

        result = {
            "global_analysis": {
                "content_overview": overview,
                "domain": domain,
                "tone": "mixed",
                "content_type": "long-form",
                "key_terms": unique_terms[:15],
                "speaker_info": "Multiple segments analyzed",
                "target_audience": "General"
            },
            "scenes": all_scenes
        }

        logger.info(f"[SCAN_CONTENT] Multi-window complete: {len(all_scenes)} scenes, "
                     f"{len(unique_terms)} terms for job_id={job_id}")
        return result

    @staticmethod
    def _empty_global_analysis() -> Dict:
        return {
            "content_overview": "Analysis not available",
            "domain": "general",
            "tone": "neutral",
            "content_type": "other",
            "key_terms": [],
            "speaker_info": "Unknown",
            "target_audience": "General"
        }

    def _validate_scene_boundaries(self, scenes: List[Dict], total_lines: int, job_id: Optional[str] = None) -> List[Dict]:
        """
        Validate and fix scene boundaries to ensure complete coverage without gaps/overlaps.
        """
        if not scenes:
            return [{"scene_id": 1, "start_line": 1, "end_line": total_lines, "topic": "Full content"}]

        # Sort by start_line
        scenes = sorted(scenes, key=lambda s: s.get('start_line', 0))

        # Fix gaps and overlaps
        fixed_scenes = []
        for i, scene in enumerate(scenes):
            start = scene.get('start_line', 1)
            end = scene.get('end_line', total_lines)

            if i == 0 and start > 1:
                start = 1  # First scene must start at line 1

            if i > 0:
                prev_end = fixed_scenes[-1]['end_line']
                if start <= prev_end:
                    start = prev_end + 1  # Fix overlap
                elif start > prev_end + 1:
                    # Fill gap by extending previous scene
                    fixed_scenes[-1]['end_line'] = start - 1

            if start <= total_lines and start <= end:
                fixed_scenes.append({
                    "scene_id": i + 1,
                    "start_line": start,
                    "end_line": min(end, total_lines),
                    "topic": scene.get('topic', f'Scene {i+1}')
                })

        # Ensure last scene extends to total_lines
        if fixed_scenes and fixed_scenes[-1]['end_line'] < total_lines:
            fixed_scenes[-1]['end_line'] = total_lines

        logger.info(f"[SCAN_CONTENT] Validated {len(fixed_scenes)} scenes covering lines 1-{total_lines} for job_id={job_id}")
        return fixed_scenes

    def _get_fallback_scan_result(self, total_lines: int) -> Dict:
        """Return a minimal fallback scan result when LLM fails."""
        return {
            "global_analysis": {
                "content_overview": "Analysis failed — using fallback",
                "domain": "general",
                "tone": "neutral",
                "content_type": "other",
                "key_terms": [],
                "speaker_info": "Unknown",
                "target_audience": "General"
            },
            "scenes": [{"scene_id": 1, "start_line": 1, "end_line": total_lines, "topic": "Full content"}]
        }

    def correct_scene(
        self,
        scene_text: str,
        scene_info: Dict,
        global_analysis: Dict,
        previous_digests: List[Dict],
        source_lang: str,
        job_id: Optional[str] = None
    ) -> Dict:
        """
        Step 2.2 — Correct a single scene's transcription text using global context
        and chained digests from previous scenes.

        Args:
            scene_text: The raw transcription text for this scene (with [N] tags)
            scene_info: Scene metadata (scene_id, topic, start_line, end_line)
            global_analysis: The global analysis from scan_content()
            previous_digests: List of scene digests from all previous scenes
            source_lang: Source language code
            job_id: Optional job ID for logging

        Returns:
            Dict with 'corrected_text' and 'scene_digest' keys
        """
        scene_id = scene_info.get('scene_id', '?')
        logger.info(f"[CORRECT_SCENE] Processing scene {scene_id} for job_id={job_id}")

        # Resolve 'auto' to a concrete language
        if not source_lang or source_lang.lower() == 'auto':
            source_lang = 'en'

        lang_name = LANG_CODE_TO_NAME.get(source_lang, source_lang)

        # Build context from previous scene digests
        # For ultra-long content: compress distant digests, keep recent ones detailed
        context_text = self._build_scene_context(previous_digests)

        # Build key terms reference
        key_terms = global_analysis.get('key_terms', [])
        terms_text = ""
        if key_terms:
            terms_list = []
            for t in key_terms:
                if isinstance(t, dict):
                    terms_list.append(f"- {t.get('term', '')}: {t.get('explanation', '')}")
                else:
                    terms_list.append(f"- {t}")
            terms_text = "KEY TERMS:\n" + "\n".join(terms_list)

        prompt = f"""You are an expert transcription editor specializing in {lang_name} content.

TASK: Review and correct the transcription for Scene {scene_id}.
Fix any obvious transcription errors (misheard words, incorrect proper nouns, broken sentences) based on the context provided.
Then produce a brief SCENE DIGEST summarizing what happens in this scene.

GLOBAL CONTEXT:
- Content: {global_analysis.get('content_overview', 'N/A')}
- Domain: {global_analysis.get('domain', 'general')}
- Topic of this scene: {scene_info.get('topic', 'N/A')}
{terms_text}

{f"PREVIOUS SCENE CONTEXT:{chr(10)}{context_text}" if context_text else "This is the first scene."}

TRANSCRIPTION TO CORRECT (Scene {scene_id}, {lang_name}):
{scene_text}

RULES:
1. PRESERVE all [N] number tags exactly as they are — do not add, remove, or renumber tags
2. Only fix clear transcription errors (wrong words that don't fit context, garbled text, obvious mishearings)
3. Do NOT rephrase, restructure, or "improve" correct text — keep the speaker's natural wording
4. Keep the same number of lines — one tagged line in, one tagged line out
5. The scene_digest should be 1-3 sentences capturing the key information/events in this scene

OUTPUT: Return ONLY a valid JSON object:
```json
{{
  "corrected_text": "[1] corrected line one\\n[2] corrected line two\\n...",
  "scene_digest": "Brief summary of what happens in this scene"
}}
```

Your response (JSON only):"""

        try:
            response = self.provider.translate(
                prompt,
                source_lang,
                source_lang,  # Output in same language as input
                metadata={"type": "scene_correction"}
            )

            raw_response = str(response.get("translated_text", "{}")).strip()
            result = self._clean_and_parse_json(raw_response, job_id, context=f"correct_scene_{scene_id}")

            if result and isinstance(result, dict):
                corrected = result.get('corrected_text', scene_text)
                digest = result.get('scene_digest', f'Scene {scene_id}: {scene_info.get("topic", "content")}')

                # Validate that corrected text still has the expected tags
                corrected = self._validate_corrected_tags(corrected, scene_text, scene_id, job_id)

                logger.info(f"[CORRECT_SCENE] Scene {scene_id} corrected successfully for job_id={job_id}")
                return {
                    "corrected_text": corrected,
                    "scene_digest": digest
                }
            else:
                logger.warning(f"[CORRECT_SCENE] Failed to parse correction for scene {scene_id}, using original text")
                return {
                    "corrected_text": scene_text,
                    "scene_digest": f"Scene {scene_id}: {scene_info.get('topic', 'content')}"
                }

        except Exception as e:
            logger.error(f"[CORRECT_SCENE] Error correcting scene {scene_id}: {str(e)}", exc_info=True)
            return {
                "corrected_text": scene_text,
                "scene_digest": f"Scene {scene_id}: {scene_info.get('topic', 'content')}"
            }

    def _build_scene_context(self, previous_digests: List[Dict], max_recent: int = 5, max_compressed: int = 10) -> str:
        """
        Build context string from previous scene digests.
        For ultra-long content: keep recent digests detailed, compress distant ones.

        Args:
            previous_digests: List of {"scene_id": N, "digest": "...", "topic": "..."} dicts
            max_recent: Number of recent digests to keep in full detail
            max_compressed: Maximum number of compressed (distant) digests to include

        Returns:
            Formatted context string
        """
        if not previous_digests:
            return ""

        total = len(previous_digests)

        if total <= max_recent:
            # All digests fit in "recent" — keep them all detailed
            lines = []
            for d in previous_digests:
                lines.append(f"Scene {d.get('scene_id', '?')} ({d.get('topic', '')}): {d.get('digest', '')}")
            return "\n".join(lines)

        # Split into distant (compressed) and recent (detailed)
        distant = previous_digests[:-max_recent]
        recent = previous_digests[-max_recent:]

        lines = []

        # Compress distant digests — just topic summaries
        if len(distant) <= max_compressed:
            for d in distant:
                lines.append(f"[Scene {d.get('scene_id', '?')}] {d.get('topic', '')}")
        else:
            # Ultra-long: sample from distant digests
            step = max(1, len(distant) // max_compressed)
            sampled = distant[::step][:max_compressed]
            for d in sampled:
                lines.append(f"[Scene {d.get('scene_id', '?')}] {d.get('topic', '')}")
            lines.append(f"... ({len(distant) - len(sampled)} more scenes omitted)")

        lines.append("--- Recent scenes (detailed) ---")

        for d in recent:
            lines.append(f"Scene {d.get('scene_id', '?')} ({d.get('topic', '')}): {d.get('digest', '')}")

        return "\n".join(lines)

    def _validate_corrected_tags(self, corrected: str, original: str, scene_id: int, job_id: Optional[str] = None) -> str:
        """
        Validate that corrected text retains all original [N] tags.
        If tags are missing, fall back to original text.
        """
        import re
        original_tags = set(re.findall(r'\[(\d+)\]', original))
        corrected_tags = set(re.findall(r'\[(\d+)\]', corrected))

        missing = original_tags - corrected_tags
        if missing:
            logger.warning(f"[CORRECT_SCENE] Scene {scene_id}: corrected text missing tags {missing}, using original for job_id={job_id}")
            return original

        return corrected

    def refine_transcription_text(
        self,
        text: str,
        source_lang: str,
        job_id: Optional[str] = None,
        max_lines_per_chunk: int = 6,  # Even smaller chunks to avoid token limits
        min_lines_for_chunking: int = 10  # Lower threshold for chunking
    ) -> str:
        """
        Refine and reorganize raw transcription text into clear, complete sentences using LLM
        while preserving number labels. Uses simplified prompts and smaller chunks to avoid token limits.
        
        Args:
            text: Raw transcription text to refine
            source_lang: Source language code of the transcription
            job_id: Optional job ID for logging
            max_lines_per_chunk: Maximum lines per chunk (reduced to avoid token limits)
            min_lines_for_chunking: Minimum lines to trigger chunking (lowered threshold)
            
        Returns:
            Refined text with improved clarity and structure, with number labels preserved
        """
        logger.info(f"[REFINEMENT] Starting transcription text refinement for job_id={job_id}")
        
        # Skip processing if text is empty or too short
        if not text or len(text.strip()) < 10:
            logger.warning(f"[REFINEMENT] Text too short for refinement, returning as-is. Length: {len(text)}")
            return text
        
        # Count non-empty lines to determine if chunking is needed
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        line_count = len(lines)
        
        logger.info(f"[REFINEMENT] Input contains {line_count} lines")
        
        # Decide whether to use chunking based on line count
        if line_count <= min_lines_for_chunking:
            logger.info(f"[REFINEMENT] Line count ({line_count}) <= {min_lines_for_chunking}, using single-chunk processing")
            return self._refine_single_chunk(text, source_lang, job_id)
        else:
            logger.info(f"[REFINEMENT] Line count ({line_count}) > {min_lines_for_chunking}, using sentence-boundary chunking")
            return self._refine_with_sentence_boundary_chunking(text, source_lang, job_id, max_lines_per_chunk)
    
    def _refine_with_sentence_boundary_chunking(
        self,
        text: str,
        source_lang: str,
        job_id: Optional[str] = None,
        max_lines_per_chunk: int = 8  # Match the reduced chunk size
    ) -> str:
        """
        Process large text by splitting at complete sentence boundaries and refining each chunk.
        
        Args:
            text: Text to process
            source_lang: Source language code
            job_id: Optional job ID for logging
            max_lines_per_chunk: Maximum lines per chunk
            
        Returns:
            Refined text with all chunks merged
        """
        logger.info(f"[REFINEMENT_CHUNKED] Starting sentence-boundary chunking for job_id={job_id}")
        
        try:
            # Split text into chunks at complete sentence boundaries
            chunks = self._split_text_at_sentence_boundaries(text, max_lines_per_chunk, source_lang)
            logger.info(f"[REFINEMENT_CHUNKED] Split text into {len(chunks)} chunks based on sentence boundaries")
            
            # Process each chunk with retry mechanism
            refined_chunks = []
            for i, chunk in enumerate(chunks):
                logger.info(f"[REFINEMENT_CHUNKED] Processing chunk {i+1}/{len(chunks)} ({len(chunk.split())} lines)")
                
                refined_chunk = self._refine_chunk_with_retry(chunk, source_lang, job_id, i+1)
                refined_chunks.append(refined_chunk)
                
                logger.info(f"[REFINEMENT_CHUNKED] Completed chunk {i+1}/{len(chunks)}")
            
            # Merge refined chunks
            result = '\n'.join(refined_chunks)
            logger.info(f"[REFINEMENT_CHUNKED] Successfully completed sentence-boundary chunking for job_id={job_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"[REFINEMENT_CHUNKED] Error in sentence-boundary chunking: {str(e)}", exc_info=True)
            # Fallback to single chunk processing
            logger.warning(f"[REFINEMENT_CHUNKED] Falling back to single chunk processing")
            return self._refine_single_chunk(text, source_lang, job_id)
    
    def _split_text_at_sentence_boundaries(self, text: str, max_lines_per_chunk: int, source_lang: str = 'en') -> List[str]:
        """
        Split text into chunks at complete sentence boundaries.
        
        Args:
            text: Text to split
            max_lines_per_chunk: Maximum lines per chunk
            source_lang: Source language for sentence boundary detection
            
        Returns:
            List of text chunks split at sentence boundaries
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        chunks = []
        current_chunk = []
        
        # Define sentence ending patterns for different languages
        sentence_endings = {
            'en': r'[.!?](?:\s*["\'\]\)])?$',  # English: period, exclamation, question mark
            'zh': r'[。！？](?:\s*["\'\]\）】])?$',  # Chinese: Chinese punctuation
            'es': r'[.!?¿¡](?:\s*["\'\]\)])?$',  # Spanish: including inverted punctuation
            'fr': r'[.!?](?:\s*["\'\]\)])?$',   # French
            'de': r'[.!?](?:\s*["\'\]\)])?$',   # German
            'ja': r'[。！？](?:\s*["\'\]\）】])?$',  # Japanese
            'ko': r'[.!?](?:\s*["\'\]\)])?$',   # Korean
            'default': r'[.!?。！？](?:\s*["\'\]\)）】])?$'  # Mixed pattern
        }
        
        # Get pattern based on source language, fallback to default
        pattern = sentence_endings.get(source_lang, sentence_endings['default'])
        
        i = 0
        while i < len(lines):
            current_chunk.append(lines[i])
            
            # Check if we should try to end this chunk
            if len(current_chunk) >= max_lines_per_chunk:
                # Look for a good sentence boundary within the next few lines
                boundary_found = False
                look_ahead_limit = min(20, len(lines) - i - 1)  # Look ahead up to 20 lines
                
                for j in range(look_ahead_limit + 1):
                    if i + j >= len(lines):
                        break
                        
                    current_line = lines[i + j] if j > 0 else lines[i]
                    
                    # Check if this line ends with complete sentence punctuation
                    if re.search(pattern, current_line):
                        # Found a sentence boundary
                        if j > 0:
                            # Add the additional lines up to the sentence boundary
                            for k in range(1, j + 1):
                                if i + k < len(lines):
                                    current_chunk.append(lines[i + k])
                            i += j  # Skip the lines we just added
                        
                        # Save current chunk and start a new one
                        if current_chunk:
                            chunks.append('\n'.join(current_chunk))
                            current_chunk = []
                        boundary_found = True
                        break
                
                # If no sentence boundary found within look-ahead, force split at current position
                if not boundary_found:
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
            
            i += 1
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Ensure we have at least one chunk
        if not chunks:
            chunks.append(text)
        
        return chunks
    
    def _refine_chunk_with_retry(
        self,
        chunk: str,
        source_lang: str,
        job_id: Optional[str] = None,
        chunk_num: int = 1,
        max_retries: int = 3
    ) -> str:
        """
        Refine a single chunk with retry mechanism for robustness.
        
        Args:
            chunk: Text chunk to refine
            source_lang: Source language code
            job_id: Optional job ID for logging
            chunk_num: Chunk number for logging
            max_retries: Maximum number of retries
            
        Returns:
            Refined chunk text
        """
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"[REFINEMENT_CHUNK_{chunk_num}] Attempt {attempt + 1}/{max_retries + 1}")
                
                result = self._refine_single_chunk(chunk, source_lang, f"{job_id}_chunk_{chunk_num}")
                
                # Validate the result
                if result and len(result.strip()) > 0:
                    logger.debug(f"[REFINEMENT_CHUNK_{chunk_num}] Successfully refined on attempt {attempt + 1}")
                    return result
                else:
                    logger.warning(f"[REFINEMENT_CHUNK_{chunk_num}] Empty result on attempt {attempt + 1}")
                    if attempt == max_retries:
                        logger.error(f"[REFINEMENT_CHUNK_{chunk_num}] All attempts failed, returning original chunk")
                        return chunk
                    
            except Exception as e:
                logger.error(f"[REFINEMENT_CHUNK_{chunk_num}] Error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries:
                    logger.error(f"[REFINEMENT_CHUNK_{chunk_num}] All attempts failed, returning original chunk")
                    return chunk
                
                # Wait before retrying (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"[REFINEMENT_CHUNK_{chunk_num}] Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        return chunk
    
    def _refine_single_chunk(
        self,
        text: str,
        source_lang: str,
        job_id: Optional[str] = None
    ) -> str:
        """
        Refine a single chunk of text (original refinement logic).
        
        Args:
            text: Text chunk to refine
            source_lang: Source language code
            job_id: Optional job ID for logging
            
        Returns:
            Refined text chunk
        """
        # Extract and store number labels with their positions
        label_pattern = r'^\[(\d+)\]\s*(.*?)\s*$'
        lines = text.split('\n')
        processed_lines = []
        labels = []
        
        for line in lines:
            match = re.match(label_pattern, line)
            if match:
                label_num = match.group(1)
                content = match.group(2).strip()
                if content:  # Only include non-empty lines
                    labels.append(f'[{label_num}]')
                    processed_lines.append(f'__LABEL_{len(labels)-1}__ {content}')
        
        text_with_placeholders = '\n'.join(processed_lines)
        has_labels = bool(labels)
        
        if not has_labels:
            # Fallback to original behavior if no labels found
            label_pattern = r'\[(\d+)\]'
            def label_replacer(match):
                label = match.group(0)
                labels.append(label)
                return f'__LABEL_{len(labels)-1}__'
            text_with_placeholders = re.sub(label_pattern, label_replacer, text)
            has_labels = bool(labels)
        
        if has_labels:
            logger.debug(f"[REFINEMENT_SINGLE] Found and replaced {len(labels)} number labels with placeholders")
            
        try:
            # Prepare the input as a JSON array of text segments
            segments = [s.strip() for s in text_with_placeholders.split('\n') if s.strip()]
            input_json = json.dumps(segments, ensure_ascii=False)
            
            # Dynamic token allocation based on input size
            # Estimate ~50-80 tokens per segment in output JSON format
            # For Gemini models, allocate more tokens to account for reasoning overhead
            estimated_output_tokens = len(segments) * 80 + 500  # Increased base overhead for reasoning
            global_max_tokens = self.config["yunwu"]["max_tokens"]  # Respect global setting
            max_tokens_needed = min(max(2000, estimated_output_tokens), global_max_tokens)  # Use global max
            
            logger.info(f"[REFINEMENT_SINGLE] Processing {len(segments)} segments, allocating {max_tokens_needed} max tokens")
            logger.debug(f"[REFINEMENT_SINGLE] Input length: {len(input_json)} chars, estimated output tokens: {estimated_output_tokens}")
            
            # Prepare the ultra-simplified prompt for semantic merging and refinement
            prompt = """Merge transcript segments into complete sentences. Keep __LABEL_X__ placeholders unchanged. Return JSON array only.

Input: {input_json}"""
            # Use the translation provider to call the LLM
            logger.debug(f"[REFINEMENT_SINGLE] Sending transcription refinement request to LLM for job_id={job_id}")
            
            # Ensure we have valid language codes
            src_lang = source_lang if source_lang and source_lang.lower() != 'auto' else 'en'
            
            # Use the ultra-simplified prompt directly
            full_prompt = prompt
            
            # Use the provider with explicit instruction to not translate
            response = self.provider.translate(
                full_prompt.format(input_json=input_json),
                src_lang,  # Use the resolved source language
                src_lang,  # Same for target to indicate no translation
                metadata={
                    "type": "transcription_refinement",
                    "job_id": job_id,
                    "source_lang": src_lang,
                    "task": "text_refinement",  # Explicit task type
                    "max_tokens": max_tokens_needed  # Dynamic token allocation based on input size
                },
                skip_translation=True  # If the provider supports this flag
            )
            
            # Get the raw response text and restore number labels if any were present
            if has_labels and labels:
                logger.debug(f"[REFINEMENT_SINGLE] Restoring {len(labels)} number labels in the refined text")
                # Convert response to string if it's a dict
                if isinstance(response, dict):
                    response_text = str(response.get("translated_text", "")).strip()
                else:
                    response_text = str(response).strip()
                
                # Restore number labels in the response
                def restore_labels(match):
                    label_index = int(match.group(1))
                    if 0 <= label_index < len(labels):
                        return labels[label_index]
                    return match.group(0)  # Return original if index is out of range
                
                # Restore labels in the response text
                response_text = re.sub(r'__LABEL_(\d+)__', restore_labels, response_text)
                
                # Update the response object with restored labels
                if isinstance(response, dict):
                    response["translated_text"] = response_text
                else:
                    response = response_text
                    
            # Handle both dict and string response types
            if isinstance(response, dict):
                refined_response = str(response.get("translated_text", "")).strip()
                raw_response_data = response.get("raw_response", {})
            else:
                refined_response = str(response).strip()
                raw_response_data = {}
            
            logger.debug(f"[REFINEMENT_SINGLE] Raw LLM response: {refined_response[:200]}...")
            
            # Check for empty response - this is a critical error that should be reported immediately
            if not refined_response:
                # Check if we have raw response data to understand why it's empty
                finish_reason = None
                if isinstance(raw_response_data, dict) and 'choices' in raw_response_data:
                    choices = raw_response_data.get('choices', [])
                    if choices and isinstance(choices[0], dict):
                        finish_reason = choices[0].get('finish_reason')
                
                error_msg = f"[REFINEMENT_SINGLE] LLM returned empty content for job_id={job_id}"
                if finish_reason:
                    error_msg += f" (finish_reason: {finish_reason})"
                if finish_reason == 'length':
                    error_msg += " - Model hit token limit during reasoning without producing output"
                    # For token limit errors, try to split into smaller chunks if possible
                    if len(segments) > 3:
                        logger.warning(f"[REFINEMENT_SINGLE] Token limit hit with {len(segments)} segments, attempting chunked processing")
                        return self._refine_with_sentence_boundary_chunking(text, source_lang, job_id, max_lines_per_chunk=3)
                
                logger.error(error_msg)
                raise ValueError(f"LLM refinement failed: empty response (finish_reason: {finish_reason})")
            
            # Try to parse the response as a list of merged sentences
            try:
                # First, try to extract a JSON array from the response
                json_match = re.search(r'\[.*\]', refined_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0).strip()
                    logger.debug(f"[REFINEMENT_SINGLE] Extracted JSON: {json_str[:200]}...")
                    
                    # Clean and repair the JSON if needed
                    json_str = json_str.replace('\n', ' ').replace('\r', '')
                    try:
                        result = json.loads(json_str)
                        
                        # Verify the structure is as expected
                        if not isinstance(result, list):
                            raise ValueError("Expected a list of strings")
                        
                        # Join sentences with newlines to maintain one sentence per line
                        refined_text = '\n'.join(
                            str(sentence).strip()
                            for sentence in result
                            if str(sentence).strip()
                        )
                        
                        # Validate content quality before returning
                        if self._validate_refined_content(refined_text, text):
                            logger.debug(f"[REFINEMENT_SINGLE] Successfully refined and validated transcription for job_id={job_id}")
                            return refined_text
                        else:
                            logger.error(f"[REFINEMENT_SINGLE] Content validation failed for job_id={job_id}")
                            raise ValueError("Refined content failed validation - quality check failed")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"[REFINEMENT_SINGLE] JSON decode error for job_id={job_id}: {str(e)}")
                        try:
                            # Try to repair the JSON
                            import json_repair
                            result = json_repair.loads(json_str)
                            
                            # Verify the structure is still a list after repair
                            if not isinstance(result, list):
                                raise ValueError("Repaired JSON is not a list")
                            
                            # Join sentences with newlines to maintain one sentence per line
                            refined_text = '\n'.join(
                                str(sentence).strip()
                                for sentence in result
                                if str(sentence).strip()
                            )
                            
                            # Validate content quality before returning
                            if self._validate_refined_content(refined_text, text):
                                logger.debug(f"[REFINEMENT_SINGLE] Successfully refined and validated transcription after JSON repair for job_id={job_id}")
                                return refined_text
                            else:
                                logger.error(f"[REFINEMENT_SINGLE] Content validation failed after JSON repair for job_id={job_id}")
                                raise ValueError("Refined content failed validation after JSON repair")
                            
                        except Exception as repair_error:
                            logger.error(f"[REFINEMENT_SINGLE] Failed to repair JSON for job_id={job_id}: {str(repair_error)}")
                            raise ValueError(f"JSON parsing failed and repair unsuccessful: {str(repair_error)}")
                    
                # If we get here, we couldn't extract a valid JSON array
                logger.error(f"[REFINEMENT_SINGLE] Could not extract valid JSON array from response for job_id={job_id}")
                raise ValueError("LLM response does not contain valid JSON array format")
                
            except Exception as e:
                logger.error(f"[REFINEMENT_SINGLE] Error processing LLM response for job_id={job_id}: {str(e)}", exc_info=True)
                raise ValueError(f"Failed to process LLM refinement response: {str(e)}")
                
        except Exception as e:
            logger.error(f"[REFINEMENT_SINGLE] Failed to refine transcription for job_id={job_id}: {str(e)}", exc_info=True)
            # Re-raise the exception instead of returning original text
            raise RuntimeError(f"Transcription refinement failed for job_id={job_id}: {str(e)}") from e

    def _normalize_language_code(self, lang_code: str) -> str:
        """
        Normalize and validate language codes, handling special cases
        
        Args:
            lang_code: Input language code to normalize
            
        Returns:
            str: Normalized language code (defaults to 'en' if invalid)
        """
        if not lang_code or not isinstance(lang_code, str):
            return 'en'
            
        # Convert to lowercase and strip whitespace
        lang_code = lang_code.lower().strip()
        
        # Handle Chinese variants
        if lang_code in ('zh', 'zh-cn', 'zh-tw', 'zh-hans', 'zh-hant', 'z', 'h'):
            return 'zh'
            
        # Handle other common cases
        lang_mapping = {
            'en': 'en',
            'es': 'es',
            'fr': 'fr',
            'de': 'de',
            'it': 'it',
            'pt': 'pt',
            'ru': 'ru',
            'ja': 'ja',
            'ko': 'ko',
            'ar': 'ar',
            'hi': 'hi',
            'auto': 'en'  # Default to English for auto-detection
        }
        
        # Check if it's a valid language code
        if lang_code in lang_mapping:
            return lang_code
            
        # Check if it's a known language code (first 2 chars)
        if len(lang_code) >= 2:
            code_prefix = lang_code[:2]
            if code_prefix in lang_mapping:
                return code_prefix
                
        # Default to English for unknown codes
        return 'en'
        
    def _is_valid_language_code(self, lang_code: str) -> bool:
        """
        Validate if a language code is valid
        
        Args:
            lang_code: Language code to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not lang_code or not isinstance(lang_code, str):
            return False
            
        normalized = self._normalize_language_code(lang_code)
        return normalized != 'en' or lang_code.lower() in ('en', 'eng', 'english')

    def extract_terminology(
        self,
        job: 'Job',
        text: str,
        domain: str,
        source_lang: str,
        target_lang: str,
        output_path: Optional[str] = None,
        content_analysis: Optional[Dict] = None
    ) -> Dict:
        """
        Extract domain-specific terminology from the text with enhanced context awareness
        
        Args:
            text: Input text to analyze
            source_lang: Source language code
            target_lang: Target language code
            domain: Optional domain/category
            output_path: Optional path to save the extracted terminology as a JSON file
            content_analysis: Optional dictionary from the content analysis step.
            
        Returns:
            Dictionary containing extracted terminology with enhanced context
        """
        original_source, original_target = source_lang, target_lang
        source_lang = self._normalize_language_code(source_lang)
        target_lang = self._normalize_language_code(target_lang)
        
        if original_source != source_lang: logger.warning(f"[TERMINOLOGY] Normalized source lang from '{original_source}' to '{source_lang}'")
        if original_target != target_lang: logger.warning(f"[TERMINOLOGY] Normalized target lang from '{original_target}' to '{target_lang}'")
            
        logger.info(f"[TERMINOLOGY] Starting terminology extraction for job {job.id}, domain={domain}")

        actual_summary_data = {}
        if content_analysis:
            logger.info("[TERMINOLOGY] Using provided content analysis for context.")
            if isinstance(content_analysis, dict):
                actual_summary_data = content_analysis.get("summary", {})
            elif isinstance(content_analysis, str):
                try:
                    parsed_content = self._clean_and_parse_json(content_analysis, job.id)
                    if isinstance(parsed_content, dict):
                        actual_summary_data = parsed_content.get("summary", {})
                except ValueError as e:
                    logger.warning(f"[TERMINOLOGY] Could not parse content_analysis string: {e}")

        if not isinstance(actual_summary_data, dict):
            logger.warning(f"[TERMINOLOGY] 'summary' data is not a dict, but {type(actual_summary_data)}. Resetting.")
            actual_summary_data = {}

        prompt = self._build_terminology_prompt(
            text=text, source_lang=source_lang, target_lang=target_lang, domain=domain,
            content_analysis=actual_summary_data
        )
        
        max_retries, retry_delay = 2, 5
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"[TERMINOLOGY] Sending request to LLM (attempt {attempt + 1})")
                context_data = {
                    "document_terminology": {
                        "metadata": {key: actual_summary_data.get(key, "") for key in ["content_overview", "tone_style", "target_audience"]},
                        "terms": []
                    },
                    "summary": actual_summary_data
                }

                response = self.provider.translate(
                    prompt, source_lang, target_lang, context=context_data,
                    metadata={"type": "terminology_extraction", "job_id": job.id}
                )
                
                llm_output_str = str(response.get("translated_text", "")).strip()
                if not llm_output_str:
                    logger.warning(f"[TERMINOLOGY] LLM returned empty content on attempt {attempt + 1}")
                    if attempt == max_retries: raise ValueError("LLM returned empty content after all retries.")
                    time.sleep(retry_delay)
                    continue

                parsed_response = self._parse_terminology_response(llm_output_str, job_id=job.id)
                
                if parsed_response and parsed_response.get('terms'):
                    result = parsed_response
                    result.update({'source_language': source_lang, 'target_language': target_lang, 'domain': domain, 'extracted_at': datetime.utcnow().isoformat()})
                    
                    if output_path:
                        self.save_terminology_to_file(result, os.path.dirname(output_path), filename=os.path.basename(output_path))
                        logger.info(f"[TERMINOLOGY] Saved terminology to {output_path}")

                    logger.info(f"[TERMINOLOGY] Successfully extracted {len(result['terms'])} terms for job {job.id}.")
                    return result
                else:
                    logger.warning(f"[TERMINOLOGY] Failed to parse terms on attempt {attempt + 1}.")
                    if attempt == max_retries: raise ValueError("Failed to extract valid terminology after all retries.")
                    time.sleep(retry_delay)

            except Exception as e:
                logger.error(f"[TERMINOLOGY] Error on attempt {attempt + 1}: {e}", exc_info=True)
                if attempt == max_retries:
                    logger.error(f"[TERMINOLOGY] All {max_retries + 1} attempts failed for job {job.id}")
                    error_payload = {
                        'terms': [], 'source_language': source_lang, 'target_language': target_lang, 'domain': domain,
                        'error_details': str(e), 'extracted_at': datetime.utcnow().isoformat()
                    }
                    if output_path:
                        self.save_terminology_to_file(error_payload, os.path.dirname(output_path), filename=os.path.basename(output_path))
                    return error_payload
                time.sleep(retry_delay)
                
        logger.error(f"[TERMINOLOGY] Exited retry loop unexpectedly for job {job.id}")
        return {
            'terms': [], 'source_language': source_lang, 'target_language': target_lang, 'domain': domain,
            'error_details': 'Exited retry loop unexpectedly.', 'extracted_at': datetime.utcnow().isoformat()
        }

    def _build_terminology_prompt(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
        content_analysis: Optional[Dict] = None
    ) -> str:
        """Build the enhanced prompt for scene-aware terminology extraction."""
        logger.info(f"[TERMINOLOGY_PROMPT] Building enhanced scene-aware prompt. Source: {source_lang}, Target: {target_lang}, Domain: {domain}")
        
        source_lang_name = LANG_CODE_TO_NAME.get(source_lang, source_lang)
        target_lang_name = LANG_CODE_TO_NAME.get(target_lang, target_lang)
        domain_context = f" in the {domain} domain" if domain else ""
        
        # Enhanced content analysis section with scene-aware guidance
        analysis_section, term_priorities = self._build_scene_aware_analysis_section(content_analysis)
                
        json_example = '''[
  {
    "src": "[actual term from text]",
    "tgt": "[translation]",
    "definition": "[brief explanation in English]",
    "category": "[technical, acronym, proper_noun, product, organization, concept]",
    "priority": "[high, medium, low]",
    "context": "[brief usage context]"
  }
]'''
        prompt = f"""## Role
You are an expert terminology specialist with deep understanding of {source_lang_name} to {target_lang_name} translation{domain_context}, capable of scene-aware term extraction and prioritization.

## Task
Extract and translate the most important terminology from the provided {source_lang_name} text, using scene-aware analysis to prioritize terms that are essential for accurate translation.

## Language Context
- Source: {source_lang_name} ({source_lang})
- Target: {target_lang_name} ({target_lang})
{analysis_section}

## Scene-Aware Term Prioritization
{term_priorities}

## Text to Analyze
{text[:4000]}{'  [Content truncated if too long]' if len(text) > 4000 else ''}

## Enhanced Extraction Guidelines

### 1. Scene-Aware Term Selection:
   - **High Priority**: Core concepts, specialized terminology, key technical terms, proper nouns central to content
   - **Medium Priority**: Supporting terminology, descriptive terms, secondary concepts
   - **Low Priority**: General vocabulary, common terms, less critical descriptors

### 2. Category Classification:
   - **technical**: Specialized technical/scientific terms
   - **acronym**: Abbreviations and acronyms  
   - **proper_noun**: Names of people, places, organizations, products
   - **product**: Specific products, services, or brand names
   - **organization**: Company, institution, or group names
   - **concept**: Abstract concepts, methodologies, theories

### 3. Quality Standards:
   - Extract only terms that appear in the provided text
   - Prioritize multi-word terms and compound concepts
   - Focus on domain-specific vocabulary relevant to the scene
   - Exclude overly common words unless contextually significant
   - Ensure translations are culturally and technically appropriate

### 4. Output Format:
   - Return ONLY a valid JSON array of term objects
   - Each term object MUST have these exact fields: "src", "tgt", "definition", "category", "priority", "context"
   - If no relevant terms found, return an empty array: []

## Example Format Only (DO NOT COPY THESE TERMS)
```json
{json_example}
```

### Bad Examples (DO NOT DO THIS):
- "tgt": "选秀权 (xuǎn xiù quán)"  // Contains pinyin
- "tgt": "选秀权 (draft pick)"      // Contains English in parentheses
- "tgt": "选秀权 - draft pick"    // Contains extra text
- "tgt": "选秀权 [pronounced: xuan xiu quan]"  // Contains pronunciation guide
- "tgt": "选秀权 (means draft pick in Chinese)"  // Contains explanation
- "tgt": "选秀权 - NBA选秀"  // Contains extra information
- "tgt": "威灵顿系统公司"  // Adding unnecessary words like "公司" when source doesn't have "Company"

### Good Examples (DO THIS):
- "tgt": "选秀权"
- "tgt": "威灵顿系统"  // Match source precision: "Wellington Systems" → "威灵顿系统" (not adding 公司)

## Important Rules
- Your response MUST be a valid JSON array.
- Your response MUST start with [ and end with ].
- Do not include any text, explanations, or markdown formatting outside the JSON array.
- In the "tgt" field, DO NOT include:
  * Any text in parentheses ( ) or brackets [ ]
  * Pronunciation guides or pinyin
  * Explanatory notes or definitions
  * Additional context or clarifications
  * Any characters other than the clean translation in the target language

Your response (JSON array only):
"""
        return prompt

    def _build_scene_aware_analysis_section(self, content_analysis: Optional[Dict] = None) -> tuple[str, str]:
        """
        Build scene-aware analysis section and generate term prioritization guidance.
        
        Args:
            content_analysis: Enhanced content analysis dictionary
            
        Returns:
            Tuple of (analysis_section, term_priorities) strings
        """
        if not content_analysis or not isinstance(content_analysis, dict):
            return "", "Focus on technical terms, proper nouns, and domain-specific vocabulary."
        
        analysis_section = "\n## Scene-Aware Content Analysis\n"
        
        # Extract key fields for analysis
        content_type = content_analysis.get("content_type", "other")
        domain_context = content_analysis.get("domain_context", "other")
        presentation_style = content_analysis.get("presentation_style", "explanatory")
        emotional_undertone = content_analysis.get("emotional_undertone", "neutral")
        expertise_level = content_analysis.get("expertise_level", "general")
        translation_strategy = content_analysis.get("translation_strategy", "technical_accuracy_with_accessibility")
        key_concepts = content_analysis.get("key_concepts", [])
        communication_purpose = content_analysis.get("communication_purpose", "educate_and_inform")
        
        # Build structured analysis section
        analysis_section += f"- **Content Type**: {content_type}\n"
        analysis_section += f"- **Domain**: {domain_context}\n" 
        analysis_section += f"- **Presentation Style**: {presentation_style}\n"
        analysis_section += f"- **Expertise Level**: {expertise_level}\n"
        analysis_section += f"- **Translation Strategy**: {translation_strategy.replace('_', ' ')}\n"
        analysis_section += f"- **Communication Purpose**: {communication_purpose.replace('_', ' ')}\n"
        
        if key_concepts:
            concepts_str = ", ".join(key_concepts[:5])  # Limit to top 5
            analysis_section += f"- **Key Concepts**: {concepts_str}\n"
        
        # Generate scene-aware term prioritization guidance
        term_priorities = self._generate_term_priorities(
            content_type, domain_context, presentation_style, 
            expertise_level, translation_strategy, communication_purpose
        )
        
        return analysis_section, term_priorities
    
    def _generate_term_priorities(
        self, 
        content_type: str, 
        domain_context: str, 
        presentation_style: str,
        expertise_level: str,
        translation_strategy: str,
        communication_purpose: str
    ) -> str:
        """
        Generate scene-aware terminology prioritization guidance.
        
        Returns:
            String with prioritization instructions
        """
        priorities = []
        
        # Content type specific priorities
        if content_type == "educational":
            priorities.append("educational concepts, learning terminology, academic terms")
        elif content_type == "tutorial":
            priorities.append("step-by-step instructions, procedural terms, action words")
        elif content_type == "presentation":
            priorities.append("business terminology, presentation keywords, professional concepts")
        elif content_type == "documentary":
            priorities.append("factual terms, research concepts, investigative vocabulary")
        elif content_type == "interview":
            priorities.append("conversational terms, personal experiences, dialogue-specific language")
        elif content_type == "promotional":
            priorities.append("marketing terms, product names, persuasive language")
        elif content_type == "news":
            priorities.append("news terminology, current events, journalistic language")
        else:
            priorities.append("general domain terminology")
        
        # Domain specific priorities
        domain_priorities = {
            "technology": "technical specifications, software/hardware terms, innovation concepts",
            "business": "corporate terminology, financial terms, market concepts", 
            "science": "scientific terminology, research methods, experimental concepts",
            "medicine": "medical terminology, treatment methods, health concepts",
            "education": "educational methodology, learning concepts, academic terms",
            "entertainment": "entertainment industry terms, creative concepts, media terminology",
            "sports": "sports terminology, competition terms, athletic concepts",
            "politics": "political terminology, policy concepts, governmental terms",
            "finance": "financial instruments, economic terms, investment concepts",
            "legal": "legal terminology, procedural terms, jurisprudence concepts"
        }
        
        if domain_context in domain_priorities:
            priorities.append(domain_priorities[domain_context])
        
        # Expertise level adjustments
        if expertise_level == "expert":
            priorities.append("advanced technical terminology, specialized jargon, expert-level concepts")
        elif expertise_level == "advanced":
            priorities.append("sophisticated terminology, advanced concepts, professional language")
        elif expertise_level == "beginner":
            priorities.append("fundamental terms, basic concepts, introductory vocabulary")
        
        # Translation strategy adjustments  
        if translation_strategy == "technical_accuracy_with_accessibility":
            priorities.append("precise technical terms balanced with accessible explanations")
        elif translation_strategy == "cultural_adaptation":
            priorities.append("culturally specific terms, localized concepts, regional terminology")
        elif translation_strategy == "literal_accuracy":
            priorities.append("exact terminological equivalents, precise technical translations")
        elif translation_strategy == "creative_localization":
            priorities.append("creatively adapted terms, culturally resonant concepts")
        
        # Communication purpose adjustments
        if communication_purpose == "persuade_and_convince":
            priorities.append("persuasive terminology, convincing language, influential concepts")
        elif communication_purpose == "instruct_and_guide":
            priorities.append("instructional terms, guidance vocabulary, procedural language")
        elif communication_purpose == "entertain_and_engage":
            priorities.append("engaging terminology, entertaining concepts, audience-appealing language")
        
        # Combine all priorities
        if priorities:
            return f"Prioritize: {'; '.join(priorities)}. Focus on terms that are central to the content's purpose and audience."
        else:
            return "Focus on technical terms, proper nouns, and domain-specific vocabulary that are essential for understanding."

    def _parse_terminology_response(
        self,
        response: str,
        job_id: Optional[str] = None
    ) -> Dict:
        """
        Parses the LLM response into a structured terminology dictionary with enhanced field validation.

        Args:
            response: Raw LLM response.
            job_id: Optional job ID for logging.

        Returns:
            A dictionary with a 'terms' list, which may be empty if parsing fails.
        """
        logger.info(f"[TERMINOLOGY_PARSER] Parsing enhanced terminology response for job_id={job_id}")
        
        if not response or not isinstance(response, str):
            logger.error(f"[TERMINOLOGY_PARSER] Empty or invalid response from LLM for job_id={job_id}")
            return {'terms': []}

        parsed_data = self._clean_and_parse_json(response, job_id, context="terminology")

        if parsed_data is None:
            logger.error(f"[TERMINOLOGY_PARSER] Failed to extract any JSON from the response for job_id={job_id}")
            return {'terms': []}

        raw_terms = []
        if isinstance(parsed_data, list):
            raw_terms = parsed_data
        elif isinstance(parsed_data, dict) and 'terms' in parsed_data and isinstance(parsed_data['terms'], list):
            raw_terms = parsed_data['terms']
        else:
            logger.warning(f"[TERMINOLOGY_PARSER] Parsed JSON is not a list or a dict with a 'terms' list for job_id={job_id}. Type: {type(parsed_data)}")
            return {'terms': []}

        # Validate and enhance each term
        validated_terms = []
        for term in raw_terms:
            if isinstance(term, dict):
                validated_term = self._validate_and_enhance_term(term, job_id)
                if validated_term:
                    validated_terms.append(validated_term)

        logger.info(f"[TERMINOLOGY_PARSER] Successfully parsed and validated {len(validated_terms)} terms for job_id={job_id}")
        return {'terms': validated_terms}
    
    def _validate_and_enhance_term(self, term: Dict, job_id: Optional[str] = None) -> Optional[Dict]:
        """
        Validate and enhance a single terminology term with required fields and defaults.
        
        Args:
            term: Raw term dictionary
            job_id: Optional job ID for logging
            
        Returns:
            Enhanced term dictionary or None if invalid
        """
        try:
            # Required fields
            if not term.get('src') or not term.get('tgt'):
                logger.debug(f"[TERMINOLOGY_VALIDATION] Skipping term missing src/tgt: {term}")
                return None
            
            # Create enhanced term with defaults
            enhanced_term = {
                'src': str(term['src']).strip(),
                'tgt': str(term['tgt']).strip(),
                'definition': str(term.get('definition', 'No definition provided')).strip(),
                'category': self._validate_term_category(term.get('category', 'technical')),
                'priority': self._validate_term_priority(term.get('priority', 'medium')),
                'context': str(term.get('context', 'General usage')).strip()
            }
            
            # Additional validation
            if len(enhanced_term['src']) > 200 or len(enhanced_term['tgt']) > 200:
                logger.debug(f"[TERMINOLOGY_VALIDATION] Skipping overly long term: {enhanced_term['src'][:50]}...")
                return None
                
            return enhanced_term
            
        except Exception as e:
            logger.warning(f"[TERMINOLOGY_VALIDATION] Error validating term {term}: {str(e)}")
            return None
    
    def _validate_term_category(self, category: str) -> str:
        """Validate and normalize term category."""
        valid_categories = ['technical', 'acronym', 'proper_noun', 'product', 'organization', 'concept']
        category = str(category).lower().strip()
        return category if category in valid_categories else 'technical'
    
    def _validate_term_priority(self, priority: str) -> str:
        """Validate and normalize term priority."""
        valid_priorities = ['high', 'medium', 'low']
        priority = str(priority).lower().strip()
        return priority if priority in valid_priorities else 'medium'

    def _parse_unstructured_terminology(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict:
        """
        Fallback method to parse terminology from unstructured text
        
        Args:
            text: Unstructured text containing terminology
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Dictionary with structured terminology
        """
        logger.info("[TERMINOLOGY_FALLBACK] Starting fallback parsing of unstructured terminology text")
        logger.info(f"[TERMINOLOGY_FALLBACK] Text length: {len(text)} chars")
        
        terms = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        logger.info(f"[TERMINOLOGY_FALLBACK] Found {len(lines)} non-empty lines in text")
        
        # Try to find term patterns in the text
        term_patterns = [
            (r'(?i)term\s*[:：]\s*(?P<src>.+?)\s*[\-–—]\s*(?P<tgt>.+?)(?:\s*[,\n]|$)', 'term'),
            (r'(?i)(?P<src>[^:：\n]+?)\s*[:：]\s*(?P<tgt>[^\n]+?)(?:\s*[,\n]|$)', 'colon'),
            (r'(?i)(?P<src>.+?)\s*[\-–—]\s*(?P<tgt>.+?)(?:\s*[,\n]|$)', 'dash')
        ]
        
        for line in lines:
            for pattern, pattern_type in term_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    src = match.group('src').strip()
                    tgt = match.group('tgt').strip()
                    
                    # Skip if either part is too long (likely not a term-definition pair)
                    if len(src) > 100 or len(tgt) > 100:
                        continue
                        
                    terms.append({
                        'src': src,
                        'tgt': tgt,
                        'definition': '',
                        'context': '',
                        'category': 'extracted'
                    })
                    logger.debug(f"[TERMINOLOGY_FALLBACK] Extracted term with {pattern_type} pattern: {src} -> {tgt}")
                    break
        
        # If no terms found with patterns, try to split on common separators
        if not terms and len(lines) > 0:
            for line in lines:
                parts = re.split(r'[,\|/]', line)
                if len(parts) >= 2:
                    src = parts[0].strip()
                    tgt = parts[1].strip()
                    if src and tgt and len(src) < 50 and len(tgt) < 50:
                        terms.append({
                            'src': src,
                            'tgt': tgt,
                            'definition': '',
                            'context': '',
                            'category': 'extracted'
                        })
        
        logger.info(f"[TERMINOLOGY_FALLBACK] Extracted {len(terms)} terms from unstructured text")
        
        return {
            'source_language': source_lang,
            'target_language': target_lang,
            'terms': terms
        }
    
    def _clean_markdown_response(self, text: str) -> str:
        """
        Clean and extract JSON content from markdown-formatted LLM responses.
        
        Args:
            text: Raw LLM response that might contain markdown formatting
            
        Returns:
            Cleaned JSON string with markdown code blocks removed
        """
        import re
        
        # If the response is already valid JSON, return as is
        text = text.strip()
        if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
            return text
            
        # Try to extract JSON from markdown code blocks
        code_block_pattern = r'```(?:json\n)?(.*?)```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        
        if matches:
            # Get the first code block and clean it up
            json_str = matches[0].strip()
            # Remove any remaining markdown formatting
            json_str = re.sub(r'^```(json)?|```$', '', json_str, flags=re.MULTILINE)
            return json_str.strip()
            
        # If no code blocks found, try to find JSON between triple backticks
        backtick_matches = re.findall(r'```(.*?)```', text, re.DOTALL)
        if backtick_matches:
            return backtick_matches[0].strip()
            
        # If still no match, try to find JSON between square brackets or curly braces
        json_match = re.search(r'[\[\{](.*)[\]\}]', text, re.DOTALL)
        if json_match:
            return json_match.group(0).strip()
            
        # If all else fails, return the original text and let the JSON parser handle it
        return text
        
    
    def _fallback_split(self, text: str, max_segment_length: int = 100) -> List[SubtitleSegment]:
        """
        Fallback method to split text into segments when semantic splitting fails.
        This is a simpler, more explicit implementation that's easier to debug.
        
        Args:
            text: Input text to split.
            max_segment_length: Maximum allowed segment length in characters.
        
        Returns:
            List of SubtitleSegment objects with character positions.
        """
        if not text or not text.strip():
            return []
            
        text = text.strip()
        segments = []
        current_pos = 0
        
        # Keep splitting until we've processed the entire text
        while current_pos < len(text):
            # Find the next good split point
            split_pos = self._find_next_split_point(text, current_pos, max_segment_length)
            
            # If no good split point found, take the remaining text
            if split_pos == -1 or split_pos <= current_pos:
                split_pos = len(text)
                
            # Extract the segment
            segment_text = text[current_pos:split_pos].strip()
            if segment_text:  # Only add non-empty segments
                segments.append(SubtitleSegment(
                    id=len(segments) + 1,
                    text=segment_text,
                    start_char=current_pos,
                    end_char=split_pos
                ))
                
            # Move to the next position after the split
            current_pos = split_pos
            
            # Skip any whitespace after the split
            while current_pos < len(text) and text[current_pos].isspace():
                current_pos += 1
                
        return segments
        
    def _find_next_split_point(self, text: str, start_pos: int, max_length: int) -> int:
        """
        Helper method to find the next good split point in the text.
        
        Args:
            text: The full text to search in
            start_pos: Position to start searching from
            max_length: Maximum length to search before forcing a split
            
        Returns:
            Position of the next split point, or -1 if no good split found
        """
        # Calculate the end position for this segment
        end_pos = min(start_pos + max_length, len(text))
        
        # If we're at the end of the text, return that position
        if start_pos >= end_pos:
            return start_pos
            
        # First try to find a sentence boundary (., !, ? followed by space)
        for i in range(min(end_pos, len(text) - 1), start_pos, -1):
            if text[i] in '.!?' and i + 1 < len(text) and text[i+1].isspace():
                return i + 1  # Split after the punctuation
                
        # Then try to find a clause boundary (comma, semicolon, colon)
        for i in range(min(end_pos, len(text) - 1), start_pos, -1):
            if text[i] in ',;:' and (i + 1 >= len(text) or text[i+1].isspace()):
                return i + 1  # Split after the punctuation
                
        # Then try to find a word boundary (whitespace)
        for i in range(min(end_pos, len(text) - 1), start_pos, -1):
            if text[i].isspace():
                return i + 1  # Split after the whitespace
                
        # If no good split point found, return -1 to indicate no split
        return -1

    def save_terminology_to_file(
        self,
        terminology: Dict,
        output_dir: str,
        filename: str = "terminology.json"
    ) -> str:
        """
        Save terminology to a JSON file using FilePathManager for consistent path handling
        
        Args:
            terminology: Terminology dictionary
            output_dir: Base directory to save the file (for backward compatibility)
            filename: Output filename (default: terminology.json)
            
        Returns:
            Path to the saved file
        """
        from app.utils.file_path_manager import get_file_path_manager, FileType
        from app.models.job_context import JobContext
        
        # Extract job_id from output_dir if possible (format: .../users/{user_id}/jobs/{job_id}/...)
        job_id = None
        try:
            parts = output_dir.split(os.sep)
            if 'jobs' in parts:
                job_idx = parts.index('jobs')
                if job_idx + 1 < len(parts):
                    job_id = int(parts[job_idx + 1])
        except (ValueError, IndexError) as e:
            logger.warning(f"[TERMINOLOGY_FILE] Could not extract job_id from {output_dir}: {str(e)}")
        
        if job_id is not None:
            # Use FilePathManager for consistent path handling
            file_manager = get_file_path_manager()
            
            # Create a minimal JobContext
            context = JobContext(
                job_id=job_id,
                user_id=1,  # Default user_id, will be overridden if job exists
                content_hash=None
            )
            
            # Get the terminology file path using FilePathManager
            output_path = file_manager.get_file_path(
                context=context,
                file_type=FileType.TERMINOLOGY_JSON
            )
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        else:
            # If we can't determine job_id, raise an error instead of falling back
            logger.error(f"[TERMINOLOGY_FILE] Cannot determine job_id from output_dir: {output_dir}")
            raise ValueError(f"Cannot determine job_id from output directory: {output_dir}")
        
        try:
            # Use file_path_manager for writing JSON
            file_manager = get_file_path_manager()
            file_manager.write_json(output_path, terminology)
            logger.info(f"[TERMINOLOGY_FILE] Saved terminology to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"[TERMINOLOGY_FILE] Error saving terminology to {output_path}: {str(e)}", exc_info=True)
            raise

    def load_terminology_from_file(self, filepath: str) -> Dict:
        """
        Load terminology from a file or directory
        
        Args:
            filepath: Path to the terminology file (or directory containing terminology.json)
            
        Returns:
            Dictionary with terminology data
        """
        # If the path is a directory, try to extract job_id and use file_path_manager
        if os.path.isdir(filepath):
            try:
                # Try to extract job_id from the directory path
                job_id = None
                path_parts = filepath.replace('\\', '/').split('/')
                for i, part in enumerate(path_parts):
                    if part == 'jobs' and i + 1 < len(path_parts):
                        job_id = int(path_parts[i + 1])
                        break
                
                if job_id is not None:
                    # Use file_path_manager to get the proper terminology file path
                    file_manager = get_file_path_manager()
                    context = JobContext(job_id=job_id, user_id=1, content_hash=None)
                    terminology_path = file_manager.get_file_path(context, FileType.TERMINOLOGY_JSON)
                    
                    if os.path.exists(terminology_path):
                        logger.info(f"[TERMINOLOGY_FILE] Loading terminology using file_path_manager: {terminology_path}")
                        return self._load_terminology_file(terminology_path)
            except (ValueError, IndexError) as e:
                logger.debug(f"[TERMINOLOGY_FILE] Could not extract job_id from {filepath}: {str(e)}")
            
            # Fallback: look for terminology.json in the directory
            root_filepath = os.path.join(filepath, 'terminology.json')
            if os.path.exists(root_filepath):
                logger.info(f"[TERMINOLOGY_FILE] Loading terminology from directory: {root_filepath}")
                return self._load_terminology_file(root_filepath)
            
            # If we get here, the file doesn't exist
            logger.warning(f"[TERMINOLOGY_FILE] Terminology file not found in {filepath}")
            return {"terms": []}
        
        # If it's a file path, just try to load it directly
        logger.info(f"[TERMINOLOGY_FILE] Loading terminology from file: {filepath}")
        return self._load_terminology_file(filepath)
        
    def _load_terminology_file(self, filepath: str) -> Dict:
        """
        Internal method to load a terminology file from a specific path
        
        Args:
            filepath: Full path to the terminology file
            
        Returns:
            Dictionary with terminology data
        """
        if not os.path.exists(filepath):
            logger.warning(f"[TERMINOLOGY_FILE] Terminology file not found: {filepath}")
            return {"terms": []}
         
        try:   
            with open(filepath, 'r', encoding='utf-8') as f:
                terminology = json.load(f)
                
            term_count = len(terminology.get('terms', []))
            logger.info(f"[TERMINOLOGY_FILE] Successfully loaded terminology with {term_count} terms from {filepath}")
            return terminology
        except json.JSONDecodeError as e:
            logger.error(f"[TERMINOLOGY_FILE] Error parsing terminology JSON file {filepath}: {str(e)}")
            return {"terms": []}
        except Exception as e:
            logger.error(f"[TERMINOLOGY_FILE] Error loading terminology file {filepath}: {str(e)}", exc_info=True)
            return {"terms": []}
    
    def _validate_refined_content(self, refined_text: str, original_text: str) -> bool:
        """
        Validate that the refined content is reasonable and hasn't been contaminated with unrelated text.
        
        Args:
            refined_text: The refined text from LLM
            original_text: The original input text
            
        Returns:
            bool: True if content appears valid, False otherwise
        """
        if not refined_text or not original_text:
            return False
            
        # Check for obviously invalid markers or content
        invalid_indicators = [
            "[удалено]",  # Russian "deleted" marker
            "爱因斯坦认为",  # Einstein theory content  
            "时间只是一个幻觉",  # Time illusion theory
            "胶片上的所有内容",  # Film content
            "请问您有什么需要帮助的吗",  # Generic assistant response
            "```",  # Code block markers
            "ERROR",
            "FAIL",
            "浴室里没有灯光",  # Bathroom content
            "你最好的朋友",  # Best friend content
            # New contamination patterns from Job 11
            "This is getting a little silly",
            "Yes, let's move on",
            "I just hope I'm doing it right",
            "I'm sure you are",
            "I'm glad you think so", 
            "That's good to know",
            "Alright, I'm ready",
            "Me too",
            "Let's do this",
            # Generic conversational patterns that shouldn't appear in NBA content
            "need to get this done",
            "move on",
            "hope I'm doing",
            "glad you think",
            "good to know",
            "I'm ready"
        ]
        
        # Check if refined text contains obvious contamination
        refined_lower = refined_text.lower()
        for indicator in invalid_indicators:
            if indicator.lower() in refined_lower:
                logger.warning(f"[CONTENT_VALIDATION] Found invalid content indicator: {indicator}")
                return False
        
        # Check length ratio - refined text shouldn't be drastically longer
        length_ratio = len(refined_text) / max(len(original_text), 1)
        if length_ratio > 3.0:  # More than 3x longer is suspicious
            logger.warning(f"[CONTENT_VALIDATION] Refined text suspiciously long: {length_ratio:.2f}x original")
            return False
        
        # Check for reasonable character overlap
        original_chars = set(original_text.lower())
        refined_chars = set(refined_text.lower())
        
        # Should have some overlap in characters (at least 20% of original chars)
        overlap = len(original_chars & refined_chars)
        min_overlap = len(original_chars) * 0.2
        
        if overlap < min_overlap:
            logger.warning(f"[CONTENT_VALIDATION] Insufficient character overlap: {overlap}/{len(original_chars)}")
            return False
        
        # Check for preserved labels (if original had labels)
        original_labels = re.findall(r'\[(\d+)\]', original_text)
        refined_labels = re.findall(r'\[(\d+)\]', refined_text)
        
        if original_labels and len(refined_labels) != len(original_labels):
            logger.warning(f"[CONTENT_VALIDATION] Label count mismatch: {len(original_labels)} -> {len(refined_labels)}")
            return False
        
        # Check for completely unrelated languages (basic heuristic)
        # Count non-ASCII characters to detect language mixing
        original_non_ascii = sum(1 for c in original_text if ord(c) > 127)
        refined_non_ascii = sum(1 for c in refined_text if ord(c) > 127)
        
        # If original was mostly ASCII but refined is mostly non-ASCII (or vice versa), it's suspicious
        if original_non_ascii < len(original_text) * 0.1 and refined_non_ascii > len(refined_text) * 0.5:
            logger.warning(f"[CONTENT_VALIDATION] Suspicious language change: ASCII {original_non_ascii}/{len(original_text)} -> {refined_non_ascii}/{len(refined_text)}")
            return False
        
        return True
    
    def _detect_mixed_language_contamination(self, text: str) -> bool:
        """
        Enhanced detection for mixed language contamination patterns
        
        Args:
            text: Text to check for contamination
            
        Returns:
            bool: True if contamination detected, False otherwise
        """
        # Check for lines that have both Chinese and English in suspicious patterns
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove label patterns like [1], [2], etc.
            clean_line = re.sub(r'\[\d+\]', '', line).strip()
            
            # Count Chinese characters and English words
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_line))
            english_words = len(re.findall(r'\b[a-zA-Z]+\b', clean_line))
            
            # If a single line has both significant Chinese content AND English sentences, it's suspicious
            if chinese_chars > 3 and english_words > 3:
                # Check if it contains complete English sentences (with proper grammar patterns)
                english_sentence_patterns = [
                    r'\b(I|You|We|They|It|He|She)\s+\w+',  # Subject-verb patterns
                    r'\b\w+\s+(is|are|was|were|will|can|should)\s+',  # Verb patterns
                    r'\b(this|that|these|those)\s+is\s+',  # Demonstrative patterns
                    r'\b(let\'s|let\s+us)\s+\w+',  # "Let's" patterns
                ]
                
                for pattern in english_sentence_patterns:
                    if re.search(pattern, clean_line, re.IGNORECASE):
                        logger.warning(f"[CONTENT_VALIDATION] Mixed language contamination in line: {line[:100]}...")
                        return True
        
        return False
    
    def _detect_semantic_contamination(self, refined_text: str, original_text: str) -> bool:
        """
        Detect semantic contamination by checking for completely unrelated content
        
        Args:
            refined_text: The refined text to check
            original_text: The original text for context
            
        Returns:
            bool: True if contamination detected, False otherwise
        """
        # Extract key topics from original text
        original_keywords = self._extract_key_terms(original_text)
        refined_keywords = self._extract_key_terms(refined_text)
        
        # Check if refined content has completely different topics
        if original_keywords and refined_keywords:
            # Calculate overlap between key terms
            overlap = len(original_keywords & refined_keywords)
            overlap_ratio = overlap / max(len(original_keywords), 1)
            
            # If there's almost no overlap in key terms, it might be contaminated
            if overlap_ratio < 0.1 and len(refined_text) > 50:
                logger.warning(f"[CONTENT_VALIDATION] Low semantic overlap: {overlap_ratio:.2f}")
                return True
        
        return False
    
    def _extract_key_terms(self, text: str) -> set:
        """
        Extract key terms from text for semantic comparison
        
        Args:
            text: Text to extract terms from
            
        Returns:
            set: Set of key terms
        """
        # Remove labels and punctuation, convert to lowercase
        clean_text = re.sub(r'\[\d+\]', '', text).lower()
        clean_text = re.sub(r'[^\w\s]', ' ', clean_text)
        
        # Extract meaningful words (filter out common stop words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                     'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
                     'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must'}
        
        words = clean_text.split()
        key_terms = {word for word in words if len(word) > 2 and word not in stop_words}
        
        return key_terms
