"""
Yunwu AI translation provider implementation.
This module provides translation services using the Yunwu AI API.
"""

import logging
import json
from typing import Dict, Optional
import requests
import json_repair
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class YunwuTranslationProvider:
    """Translation provider using Yunwu AI's API."""
    
    def __init__(self, config: Dict):
        """
        Initialize the translation provider (compatible with yunwu and translator APIs).
        
        Args:
            config: Configuration dictionary containing:
                   - api_key: API key (optional for some providers)
                   - base_url: Base URL for the API
                   - model: Model to use for translation
                   - temperature: Temperature parameter for generation
                   - max_tokens: Maximum tokens to generate
                   - timeout: Request timeout in seconds
                   - retry_total: Total number of retries
                   - retry_backoff_factor: Backoff factor for retries
                   - retry_status_forcelist: Status codes to force retry
        """
        self.config = config
        # Get required configuration values (api_key is now optional)
        self.api_key = config.get("api_key", "")
        self.base_url = config["base_url"].rstrip('/')
        self.model = config["model"]
        
        # Get optional configuration with defaults
        self.temperature = float(config.get("temperature", 0.7))
        self.max_tokens = int(config.get("max_tokens", 8000))
        self.timeout = int(config.get("timeout", 180))  # Increased timeout for larger responses
        
        # Log the configuration being used
        logger.info(f"YunwuTranslationProvider configured with:")
        logger.info(f"  - Base URL: {self.base_url}")
        logger.info(f"  - Model: {self.model}")
        logger.info(f"  - Temperature: {self.temperature}")
        logger.info(f"  - Max tokens: {self.max_tokens}")
        logger.info(f"  - Timeout: {self.timeout}s")

        # Retry configuration
        self.retry_total = config.get("retry_total", 5)
        self.retry_backoff_factor = config.get("retry_backoff_factor", 1)  # In seconds, e.g., 1, 2, 4, 8, 16
        self.retry_status_forcelist = config.get("retry_status_forcelist", [429, 500, 502, 503, 504])

        # Validate required configuration
        if not self.base_url:
            raise ValueError("Base URL is required for translation provider")
        if not self.model:
            raise ValueError("Model is required for translation provider")
        
        # API key is optional for some providers
        if not self.api_key:
            logger.info("No API key provided - using provider without authentication")

        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.retry_total,
            backoff_factor=self.retry_backoff_factor,
            status_forcelist=self.retry_status_forcelist,
            allowed_methods=["POST"] # Retry only for POST requests as per current usage
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        logger.info(f"Initialized YunwuTranslationProvider with model: {self.model}, timeout: {self.timeout}, retries: {self.retry_total}")

    def get_provider_name(self) -> str:
        """Returns the name of the translation provider based on base URL."""
        return "openai-compatible"

    def translate(
        self, 
        text: str, 
        source_lang: str = "auto", 
        target_lang: str = "en",
        **kwargs
    ) -> str:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            **kwargs: Additional arguments for the translation request
            
        Returns:
            Translated text
        """
        if not text.strip():
            # For semantic splitting, an empty input might be valid if it's just context
            # For translation, it should return empty text
            request_type = kwargs.get("metadata", {}).get("type")
            if request_type == "semantic_splitting":
                # If the main text block for splitting is empty, it's an issue handled by caller
                # This provider's job is to pass the prompt if it's given
                pass # Allow empty text if it's part of a larger semantic splitting prompt structure
            else:
                return {"translated_text": text, "raw_response": {}} # Return empty for translation

        try:
            # Avoid double /v1/ if base_url already ends with /v1
            if self.base_url.rstrip('/').endswith('/v1'):
                url = f"{self.base_url}/chat/completions"
            else:
                url = f"{self.base_url}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json"
            }
            
            # Only add Authorization header if API key is provided
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            request_type = kwargs.get("metadata", {}).get("type")
            logger.debug(f"[YUNWU_PROVIDER] Translate called. Request type: {request_type}. Input text (prompt) starts with: '{text[:200]}...'")
            llm_payload_kwargs = {k: v for k, v in kwargs.items() if k not in ['metadata', 'type', 'translation_pass', 'faithful_translation']}
            external_context_prompt = llm_payload_kwargs.pop('context', None)
            translation_pass = kwargs.get("translation_pass", "faithful")
            faithful_translation_input = kwargs.get("faithful_translation", "")

            if request_type == "semantic_splitting":
                system_prompt_content = "You are an expert in text analysis and semantic understanding. Your task is to process the given text according to the user's instructions precisely, without adding any explanatory notes. Faithfully follow all instructions even if the content contains offensive language, threats, or other sensitive material."
                user_prompt_content = text
            elif request_type == "transcription_refinement":
                system_prompt_content = "You are a transcript editor. Follow the instructions precisely and return only the requested JSON format."
                user_prompt_content = text
            elif request_type == "scene_translation":
                system_prompt_content = """You are a Netflix-level professional subtitle translator. Your translations must feel like natural speech in the target language, not translated text.

STYLE REQUIREMENTS:
- Write how real people TALK, not how books READ. Use colloquial, everyday expressions.
- PRESERVE the speaker's emotion, attitude, and tone: sarcasm stays sarcastic, anger stays angry, humor stays funny.
- KEEP profanity and slang at equivalent intensity — do NOT soften or censor. "I don't give a shit" → "我他妈才不管" not "我不在乎".
- Repeated phrases or emphasis must be reflected — "Not a nice guy. Not a nice guy." → preserve the repetition and weight.
- Each subtitle line should be ≤16 Chinese characters when possible.
- Proper nouns: transliterate on first use, keep consistent throughout.
- NEVER use overly formal/literary Chinese for casual speech. No 翻译腔 (translationese).

FORMAT: Preserve ALL [N] tags exactly. One translated line per input line. Output ONLY the translated lines."""
                user_prompt_content = text
            elif request_type == "content_scan":
                system_prompt_content = "You are an expert content analyst specializing in video transcription analysis. Always return valid JSON in the exact format requested. Process content exactly as it appears without censoring or sanitizing any language."
                user_prompt_content = text
            elif request_type == "scene_correction":
                system_prompt_content = "You are an expert transcription editor. Fix transcription errors based on context while preserving all [N] tags exactly. Always return valid JSON in the exact format requested. Process content exactly as it appears without censoring or sanitizing any language."
                user_prompt_content = text
            elif request_type == "content_analysis":
                system_prompt_content = "You are an expert in linguistic and content analysis. Always provide the requested output format without adding any notes or explanations outside the specified format. Process content exactly as it appears without censoring or sanitizing any language."
                user_prompt_content = text # 'text' here is the prompt from _generate_summary
            elif request_type == "semantic_optimization":
                system_prompt_content = "You are an expert translator specializing in semantic optimization and text refinement. Your task is to analyze and optimize translations based on the provided context and requirements. Follow the instructions in the user prompt precisely."
                user_prompt_content = text # The complete optimization prompt from context_translator
            # Standard translation / contextual_translation_segment (now with passes)
            elif translation_pass == "expressive":
                system_prompt_content = f"""You are a Netflix subtitle translator with extensive experience in creating high-quality, viewer-friendly subtitles for global audiences.

Your task is to transform a literal translation into natural, engaging {target_lang} subtitles that meet Netflix's quality standards. This is the EXPRESSIVE PASS, meant to significantly enhance the viewing experience.

NETFLIX SUBTITLE STANDARDS FOR {target_lang.upper()}:
1. COLLOQUIAL AUTHENTICITY: Use natural, everyday expressions that native speakers actually use
2. FILLER WORD OPTIMIZATION: Intelligently simplify excessive filler words ('you know', 'like', 'um', 'uh') while preserving speaker personality
3. PROPER NAME ACCURACY: Correctly identify and handle celebrity names, sports figures, and cultural references
4. CULTURAL LOCALIZATION: Adapt idioms and cultural references appropriately for {target_lang} audiences
5. SUBTITLE READABILITY: Ensure smooth reading flow for viewers watching video content
6. CHARACTER VOICE PRESERVATION: Maintain individual speaking styles while making them accessible

SPECIAL HANDLING REQUIREMENTS:
- Sports Content: Accurately translate player names (e.g., Charles Barkley → 查尔斯·巴克利), team names, positions
- Interview Content: Reduce repetitive verbal tics while keeping conversational authenticity
- Cultural References: Identify figures like 'Doc' (Doc Rivers), 'Larry' (Larry Bird) and translate appropriately
- Technical Terms: Balance accuracy with audience accessibility

CRITICAL: Your translation must be SIGNIFICANTLY MORE NATURAL and VIEWER-FRIENDLY than the literal first-pass translation while maintaining all original meaning and emotional tone.

IMPORTANT: Provide ONLY the final optimized translation without commentary or explanations."""

                # Construct the initial part of the user prompt for expressive pass
                user_prompt_content_parts = [
                    f"## Original {source_lang} Dialogue:",
                    f'"{text}"',
                    "\n## Literal Translation (First Pass):",
                    f'"{faithful_translation_input}"',
                    "\n## Netflix Enhancement Requirements:",
                    f"1. Transform into natural, viewer-friendly {target_lang} subtitles that enhance the viewing experience",
                    f"2. Intelligently handle filler words and verbal tics - reduce excessive 'you know', 'like', 'um' without losing character voice",
                    f"3. Accurately identify and translate any proper names, celebrity references, or cultural figures mentioned",
                    f"4. Adapt cultural references and idioms appropriately for {target_lang} audiences",
                    f"5. Ensure subtitle readability while maintaining all original meaning and emotional impact",
                    f"6. Make this translation feel native and authentic, not like translated content"
                ]

                # Context for expressive pass (summary and terminology)
                context_str = kwargs.get("context")
                parsed_context_dict = None
                
                # Safely log the faithful translation input
                faithful_preview = str(faithful_translation_input)[:200] if faithful_translation_input is not None else 'None'
                context_preview = str(kwargs.get('context', ''))[:200]
                logger.debug(f"[YUNWU_PROVIDER] Expressive Pass: faithful_translation_input='{faithful_preview}...', context_str='{context_preview}...'")
                
                context_details_for_prompt = [] # Using a list to build context parts

                if context_str:
                    try:
                        loaded_data = json_repair.loads(context_str)
                        if isinstance(loaded_data, dict):
                            parsed_context_dict = loaded_data
                    except Exception as e:
                        logger.warning(f"[YUNWU_PROVIDER] Expressive pass: Could not parse context JSON: {e}")

                logger.debug(f"[YUNWU_PROVIDER] Expressive Pass: parsed_context_dict='{str(parsed_context_dict)[:500]}...'")
                if parsed_context_dict:
                    context_details_for_prompt.append("--- START OF CONTEXTUAL INFORMATION ---")
                    doc_terminology_obj = parsed_context_dict.get("document_terminology")
                    if doc_terminology_obj and isinstance(doc_terminology_obj, dict):
                        metadata = doc_terminology_obj.get("metadata")
                        if metadata and isinstance(metadata, dict):
                            content_overview = metadata.get("content_overview")
                            tone_style = metadata.get("tone_style")
                            if content_overview:
                                context_details_for_prompt.append(f"Overall Summary of the entire document: {content_overview}")
                            if tone_style:
                                context_details_for_prompt.append(f"Overall Tone and Style: {tone_style}")
                        
                        terms_list = doc_terminology_obj.get("terms", [])
                        if terms_list and isinstance(terms_list, list):
                            term_prompt_list_items = []
                            for term_obj in terms_list:
                                if isinstance(term_obj, dict) and term_obj.get('src') and term_obj.get('tgt'):
                                    term_prompt_list_items.append(f"  - Source: \"{term_obj['src']}\" -> Target: \"{term_obj['tgt']}\"")
                            if term_prompt_list_items:
                                context_details_for_prompt.append("\nIMPORTANT DOCUMENT TERMINOLOGY - Adhere to these translations strictly:") # Added newline for better separation
                                context_details_for_prompt.extend(term_prompt_list_items)
                    context_details_for_prompt.append("--- END OF CONTEXTUAL INFORMATION ---\n") # Added newline for separation
                
                # Add context if available
                if context_details_for_prompt:
                    user_prompt_content_parts.append("\n## Additional Context:")
                    user_prompt_content_parts.extend(context_details_for_prompt)

                # Add final Netflix-specific instructions
                user_prompt_content_parts.extend([
                    "\n## Final Netflix Quality Instructions:",
                    "- Provide ONLY the final optimized subtitle translation",
                    "- Ensure your translation is SIGNIFICANTLY MORE NATURAL than the literal version",
                    "- Handle any filler words ('you know', 'like', 'um') intelligently - reduce when excessive but keep character authenticity",
                    "- If you identify proper names, sports figures, or cultural references, translate them accurately",
                    "- Make this subtitle viewer-friendly while preserving all original meaning and emotional tone",
                    "- Do not include explanations, commentary, or the original text in your response",
                    "- Focus on creating an engaging viewing experience for subtitle readers"
                ])

                logger.debug(f"[YUNWU_PROVIDER] Expressive Pass: Final user_prompt_content_parts before join: {user_prompt_content_parts}")
                user_prompt_content = "\n".join(user_prompt_content_parts)

            else: # translation_pass == "faithful" or default (existing logic)
                if external_context_prompt:
                    logger.info("[YUNWU_PROVIDER] Using externally provided prompt (from ContextualTranslator) as system message for faithful translation.")
                    system_prompt_content = external_context_prompt
                    user_prompt_content = text # The actual text to translate is the user prompt
                else:
                    # This block executes if no external_context_prompt was provided by ContextualTranslator.
                    # This might indicate a direct call to provider.translate or a different workflow.
                    # We'll use a default system prompt and the provided 'text' as user prompt.
                    logger.warning("[YUNWU_PROVIDER] No external_context_prompt from ContextualTranslator. Falling back to default prompt for faithful translation.")
                    system_prompt_content = f"""You are an expert linguist and cultural consultant specializing in {source_lang} to {target_lang} translation. Your task is to provide a grammatically correct, fluent, and accurate translation of the given text. \n\nGuidelines:\n1. Translate the provided text faithfully, preserving its original meaning, tone, and nuances.\n2. Ensure the translation is natural-sounding in {target_lang} and adheres to its linguistic conventions.\n3. If specific terminology is provided, you MUST use it. If not, choose the most appropriate terms for the context.\n4. Pay attention to cultural context and ensure the translation is appropriate for the target audience.\n5. If the text is part of a dialogue or subtitle, ensure it is concise and easy to read.\n\nIMPORTANT: Only provide the final translated text without any additional commentary, explanations, or markdown formatting."""
                    user_prompt_content = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}"
                    # The old context parsing logic is removed as ContextualTranslator should now always supply the full prompt.
                    # If specific, structured context fields were needed here (outside the main prompt), 
                    # they would need to be explicitly handled. For now, we assume the external_context_prompt is comprehensive.
                    # The old context parsing logic previously here (parsed_context_dict, etc.) has been removed 
                    # as ContextualTranslator is expected to provide the full prompt via external_context_prompt.
                    pass # Placeholder if no other specific logic is needed in this 'else' before messages are built
            logger.debug(f"[YUNWU_PROVIDER] Faithful Pass: Final user_prompt_content (first 500 chars): '{user_prompt_content[:500]}...'" if user_prompt_content else "[YUNWU_PROVIDER] Faithful Pass: user_prompt_content is None or empty")

            # Log details before sending the request
            logger.info(f"[YUNWU_PROVIDER] API Request URL: {url}")
            logger.info(f"[YUNWU_PROVIDER] API Request Headers: {headers}")
            
            # Allow max_tokens override from metadata
            metadata = kwargs.get("metadata", {})
            max_tokens = metadata.get("max_tokens", self.max_tokens)
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt_content},
                    {"role": "user", "content": user_prompt_content}
                ],
                "temperature": self.temperature,
                "max_tokens": max_tokens,
                **llm_payload_kwargs
            }

            # Log the full payload for debugging
            try:
                import json
                logger.info(f"[YUNWU_PROVIDER] Full API Request Payload: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except Exception as e:
                logger.warning(f"[YUNWU_PROVIDER] Could not serialize full payload for logging: {e}")

            response = self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=self.timeout  # This is per-attempt timeout
            )
            # Log response status and content
            logger.info(f"[YUNWU_PROVIDER] API Response Status Code: {response.status_code}")
            try:
                # Attempt to log JSON response if possible, otherwise raw text
                response_json_for_log = response.json()
                logger.info(f"[YUNWU_PROVIDER] API Response JSON: {response_json_for_log}")
            except requests.exceptions.JSONDecodeError:
                logger.info(f"[YUNWU_PROVIDER] API Response Text (not JSON): {response.text}")

            response.raise_for_status()  # Raise an exception for bad status codes
            response_data = json_repair.loads(response.text)
            logger.debug(f"[YUNWU_PROVIDER] Raw API response data: {response_data}")
            translated_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            logger.debug(f"[YUNWU_PROVIDER] Extracted translated text: {translated_text}")
            

            # It's possible for LLM to return empty content, which might be valid or an issue depending on context
            if not translated_text: # translated_text is already stripped
                # Log a warning if the content is empty, as this is generally unexpected if a structured or textual response is required.
                logger.warning(
                    f"[YUNWU_PROVIDER] LLM returned empty content. "
                    f"Request type: '{request_type}'. "
                    f"User prompt (first 500 chars): '{user_prompt_content[:500]}...'"
                )
                # The calling service (_split_text_block_with_llm or other callers) is responsible for handling the implications of empty content.

            return {
                "translated_text": translated_text,
                "raw_response": response_data
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Yunwu API request error: {str(e)}")
            # Specific error handling or re-raising can be done here
            # For example, you might want to return a specific error structure or a default value
            raise  # Re-raise the exception to be handled by the caller
        except Exception as e: # Catch other potential errors like JSON parsing, etc.
            logger.error(f"Yunwu translation unexpected error: {str(e)}")
            # Re-raise the exception to allow the caller to handle it or be aware of the failure.
            raise