"""
Prompt Templates Storage Module

This module provides a centralized storage for all prompt templates used across
VideoLingo SaaS Backend services. Centralizing prompts helps maintain consistency
across different services and translation providers.
"""

import logging
import os
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

# Language mapping for better prompt context
LANGUAGE_MAP = {
    # Main languages
    "en": "English",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "it": "Italian",
    
    # Additional languages
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "cs": "Czech",
    "hu": "Hungarian",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "ro": "Romanian",
    "el": "Greek",
    "uk": "Ukrainian",
    "he": "Hebrew",
    "fa": "Persian",
    
    # Alternate codes
    "cn": "Chinese",
    "jp": "Japanese",
    "kr": "Korean",
    "gr": "Greek",
    "dk": "Danish",
    
    # Generic fallbacks for safety
    "source": "Source Language",
    "target": "Target Language",
    
    # Full language names as fallbacks
    "english": "English",
    "chinese": "Chinese",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "japanese": "Japanese",
    "korean": "Korean",
    "russian": "Russian",
    "arabic": "Arabic",
    "hindi": "Hindi",
    "portuguese": "Portuguese",
    "italian": "Italian"
}

def get_language_name(lang_code: str) -> str:
    """
    Convert language code to full language name with validation
    
    Args:
        lang_code: ISO language code or language name
        
    Returns:
        Full language name, with fallbacks for unrecognized codes
    """
    if not lang_code or not isinstance(lang_code, str):
        logger.warning(f"Invalid language code provided: {lang_code}, defaulting to English")
        return "English"  # Default safe fallback
    
    # Normalize the code
    normalized_code = lang_code.lower().strip()
    
    # Check for direct match first
    if normalized_code in LANGUAGE_MAP:
        return LANGUAGE_MAP[normalized_code]
    
    # Try to find partial matches (useful for longer language codes like 'en-US')
    for code, name in LANGUAGE_MAP.items():
        if normalized_code.startswith(code + '-') or normalized_code.endswith('-' + code):
            logger.info(f"Found match for extended language code {normalized_code} -> {name}")
            return name
    
    # If we get here, no match was found
    logger.warning(f"Unrecognized language code: {lang_code}, using as-is")
    
    # If it's a very short code (1-2 chars) that wasn't recognized, default to English for safety
    if len(normalized_code) <= 2:
        logger.warning(f"Short unrecognized code defaulting to English: {lang_code}")
        return "English"
    
    # Otherwise return the original code, might be a full language name already
    return lang_code

def get_translation_system_prompt(source_lang: str, target_lang: str, context: Optional[str] = None) -> str:
    """
    Generate the system prompt for translation tasks
    Uses language codes directly from frontend without additional validation
    """
    # Use language codes directly - respect frontend's choice
    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)
    
    # Clear, direct instruction focused on just translation
    system_prompt = f"You are a translator from {source_name} to {target_name}. Your ONLY task is to translate the provided text."
    system_prompt += "\n\nRULES:\n1. Output ONLY the translation\n2. Do not add any explanations\n3. Do not add any comments\n4. Do not add any metadata\n5. Do not apologize or explain anything\n6. Do not mention languages in your response"
    
    # Special handling for Chinese translations, but simplified for clarity
    if target_lang.lower() in ['zh', 'cn', 'chinese']:
        system_prompt += "\n\n你是一位专业翻译。请直接输出翻译结果，不要添加任何其他内容。直接翻译，不要解释，不要道歉，不要添加前缀。"
    
    if context:
        system_prompt += f"\n\nAdditional context: {context}"
    
    return system_prompt

def get_translation_user_prompt(text: str, source_lang: str, target_lang: str) -> str:
    """
    Generate user prompt for translation
    Simplified to avoid any language detection issues
    
    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Formatted user prompt
    """
    # Create a simple, direct translation request
    source_lang_name = get_language_name(source_lang)
    target_lang_name = get_language_name(target_lang)
    return f"Text to translate to {target_lang_name}:\n\n{text}\n\nJust provide the {target_lang_name} translation, nothing else."

def get_text_split_prompt(text: str, num_parts: int, word_limit: int = 18, attempt: int = 0) -> str:
    """
    Generate prompt for splitting text
    
    Args:
        text: Text to split
        num_parts: Number of parts to split into
        word_limit: Target word limit per part
        attempt: Attempt number for retries
        
    Returns:
        Formatted prompt for text splitting
    """
    base_prompt = f"""Split the following sentence into {num_parts} parts, each with around {word_limit} words. 
    Maintain the meaning and readability of each part. 
    Mark splits with '[br]' inserted between parts. 
    Only return the split text, with no additional explanation.
    Do not number the parts.
    
    Original sentence: {text}"""
    
    # Add randomness for retries to encourage different response
    if attempt > 0:
        base_prompt += f"\n\nNote: Previous {attempt} attempts failed to produce valid splits. Please approach this differently."
    
    return base_prompt

def generate_shared_prompt(previous_content: str, after_content: str, 
                          summary: str, notes: str) -> str:
    """
    Generate a shared context prompt with surrounding content
    
    Args:
        previous_content: Content before the current section
        after_content: Content after the current section
        summary: Summary of the content
        notes: Special notes or instructions
        
    Returns:
        Formatted context prompt
    """
    return f'''### Context Information
<previous_content>
{previous_content}
</previous_content>

<subsequent_content>
{after_content}
</subsequent_content>

### Content Summary
{summary}

### Points to Note
{notes}'''

def get_summary_prompt(transcript_text: str, max_words: int = 250) -> str:
    """
    Generate prompt for summarizing content
    
    Args:
        transcript_text: Text to summarize
        max_words: Maximum word count for summary
        
    Returns:
        Formatted prompt for summarization
    """
    return f"""Summarize the following transcript text in about {max_words} words.
    Focus on the main topics, key points, and overall narrative.
    Maintain the professional tone of the original content.
    
    Transcript:
    {transcript_text}"""

def get_terminology_extraction_prompt(text: str, domain: Optional[str] = None) -> str:
    """
    Generate prompt for terminology extraction
    
    Args:
        text: Source text to extract terminology from
        domain: Optional domain context (e.g., medical, technical, legal)
        
    Returns:
        Formatted prompt for terminology extraction
    """
    domain_context = f"in the {domain} domain" if domain else ""
    
    return f"""Extract important terminology {domain_context} from the following text.
    For each term, provide:
    1. The term itself
    2. A concise definition or explanation
    3. The proper translation if applicable
    
    Format your response as a JSON object with terms as keys and objects containing definition and translation as values.
    
    Text:
    {text}"""

def get_subtitle_formatting_prompt(subtitle_text: str, target_lang: str, style_guide: Optional[str] = None) -> str:
    """
    Generate prompt for subtitle formatting
    
    Args:
        subtitle_text: Subtitle text to format
        target_lang: Target language code
        style_guide: Optional style guide specifications
        
    Returns:
        Formatted prompt for subtitle formatting
    """
    target_lang_name = get_language_name(target_lang)
    style_instructions = f"\n\nFollow these style guidelines:\n{style_guide}" if style_guide else ""
    
    return f"""Format the following {target_lang_name} subtitles for optimal readability.
    - Ensure each line is concise and complete in meaning
    - Break lines at natural pause points
    - Maintain consistent style and tone
    - Adhere to standard subtitle length guidelines (max 42 characters per line)
    - Preserve all meaning from the original subtitles{style_instructions}
    
    Subtitles to format:
    {subtitle_text}"""

def get_assistant_message_template(role: str = "assistant", content: str = "") -> Dict[str, str]:
    """
    Generate a message template for assistant messages
    
    Args:
        role: Message role 
        content: Message content
        
    Returns:
        Message dictionary
    """
    return {"role": role, "content": content}

def get_faithfulness_prompt(original_text: str, translation: str, source_lang: str, target_lang: str) -> str:
    """
    Generate prompt for checking translation faithfulness
    
    Args:
        original_text: Original source text
        translation: Translated text to verify
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Formatted prompt for faithfulness checking
    """
    source_lang_name = get_language_name(source_lang)
    target_lang_name = get_language_name(target_lang)
    
    return f"""Evaluate the faithfulness of this translation from {source_lang_name} to {target_lang_name}.
    
    Original {source_lang_name}:
    {original_text}
    
    Translation to {target_lang_name}:
    {translation}
    
    Rate the translation on a scale of 1-5 where:
    1 = Completely inaccurate, misses key points
    2 = Poor, multiple mistranslations or omissions
    3 = Acceptable, conveys the main meaning but has issues
    4 = Good, minor inconsistencies but preserves meaning
    5 = Excellent, fully preserves meaning and style
    
    Provide your rating with a brief explanation of any issues or strengths."""

def get_subtitle_trim_prompt(text: str, duration: float, rule: str) -> str:
    """
    Generate prompt for trimming subtitles to fit duration constraints
    
    Args:
        text: Subtitle text to trim
        duration: Duration in seconds
        rule: Rules for trimming
        
    Returns:
        Formatted prompt for subtitle trimming
    """
    return f"""
### Role
You are a professional subtitle editor for international streaming platforms.

### Task
Optimize the given subtitle to make it more concise and readable without losing essential meaning.

### Subtitle Duration
This subtitle will be displayed for {duration} seconds.

### Original Subtitle
{text}

### Processing Rules
{rule}

### Processing Steps
Please follow these steps and provide the results in the JSON output:
1. Analysis: Briefly analyze the subtitle's structure, key information, and filler words that can be omitted.
2. Trimming: Based on the rules and analysis, optimize the subtitle by making it more concise according to the processing rules.

### Output in JSON
{{
    "analysis": "Brief analysis of the subtitle, including structure, key information, and potential processing locations",
    "result": "Optimized and shortened subtitle in the original subtitle language"
}}

### Your Answer, Provide ONLY a valid JSON object:
""".strip()

def get_correct_text_prompt(text: str) -> str:
    """
    Generate prompt for correcting text for TTS (Text-to-Speech) systems
    
    Args:
        text: Text to be corrected
        
    Returns:
        Formatted prompt for TTS text correction
    """
    return f"""
### Role
You are a text cleaning expert for TTS (Text-to-Speech) systems.

### Task
Clean the given text by:
1. Keep only basic punctuation (.,?!)
2. Preserve the original meaning
3. Remove any characters that may cause issues in TTS like: @#$%^&*()[]{{}}()<>/\\|=+
4. Replace numbers with their word form where appropriate
5. Spell out abbreviations and acronyms, except for very common ones
6. Fix any grammatical or spelling errors

### Original Text
{text}

### Output
Provide ONLY the cleaned text with no explanations or additional commentary.
"""

def get_align_subtitle_prompt(subtitles: str, duration: float) -> str:
    """
    Generate prompt for aligning subtitles with audio duration
    
    Args:
        subtitles: Subtitles to align
        duration: Audio duration in seconds
        
    Returns:
        Formatted prompt for subtitle alignment
    """
    return f"""
### Role
You are a professional subtitle timing specialist working for a major streaming platform.

### Task
Aligning the provided subtitles to properly fit within the given audio duration, ensuring optimal readability.

### Audio Duration
Total duration: {duration} seconds

### Subtitles to Align
{subtitles}

### Alignment Rules
1. Each subtitle line should be displayed for an appropriate amount of time (2-7 seconds is typical)
2. Subtitle timing should match natural speech rhythms and pauses
3. Longer or more complex subtitles should have longer display times
4. Short or simple subtitles can have shorter display times
5. Ensure the sum of all subtitle durations matches the total audio duration

### Output Format
Provide a JSON array where each element contains:
- text: The subtitle text
- start_time: When the subtitle should appear (in seconds from start)
- end_time: When the subtitle should disappear (in seconds from start)

Example format:
```json
[
  {"text": "Hello world", "start_time": 0, "end_time": 2.5},
  {"text": "This is an example", "start_time": 2.5, "end_time": 5.0}
]
```

### Your Response (JSON only):
"""

def get_qa_prompt(content: str, question: str, context: Optional[str] = None) -> str:
    """
    Generate prompt for question answering based on content
    
    Args:
        content: The content to answer questions about
        question: The question to answer
        context: Additional context to consider when answering the question
        
    Returns:
        Formatted prompt for question answering
    """
    context_section = f"\n\n### Additional Context\n{context}" if context else ""
    
    return f"""
### Role
You are an intelligent assistant specialized in analyzing and answering questions about content.

### Content
{content}
{context_section}

### Question
{question}

### Instructions
1. Use only the information provided in the content and context to answer the question
2. If the answer cannot be determined from the given information, state this clearly
3. Provide a concise but comprehensive answer
4. Use bullet points for complex explanations when appropriate
5. If relevant, cite specific parts of the content that support your answer

### Your Answer:
"""

def get_terminology_extraction_detailed_prompt(text: str, target_lang: str, domain: Optional[str] = None) -> str:
    """
    Generate a detailed prompt for terminology extraction and translation
    
    Args:
        text: Source text to extract terminology from
        target_lang: Target language for translations
        domain: Optional domain context (e.g., medical, technical, legal)
        
    Returns:
        Formatted prompt for terminology extraction with translation
    """
    target_lang_name = get_language_name(target_lang)
    domain_context = f"in the {domain} domain" if domain else ""
    
    return f"""
### Role
You are a professional terminology expert and translator specializing in the extraction and translation of technical terms {domain_context}.

### Task
Analyze the text below to extract key terminology and provide accurate translations to {target_lang_name}.

### Source Text
{text}

### Instructions
1. Identify specialized terms, technical concepts, and domain-specific language
2. For each term:
   - Provide the source term as it appears in the text
   - Translate it accurately to {target_lang_name}
   - Add a brief but clear definition or explanation
   - Note any cultural or contextual adaptations needed for the target language

### Output Format
Provide your response in JSON format as follows:
```json
{{
  "terms": [
    {{
      "src": "source term",
      "tgt": "translated term",
      "note": "definition or explanation"
    }},
    {{...}}
  ]
}}
```

### Your Response (JSON only):
"""

def get_video_analysis_prompt(transcript: str, content_type: str) -> str:
    """
    Generate prompt for analyzing video content based on transcript
    
    Args:
        transcript: The video transcript to analyze
        content_type: Type of content (lecture, interview, tutorial, etc.)
        
    Returns:
        Formatted prompt for video content analysis
    """
    return f"""
### Role
You are a content analysis expert specializing in {content_type} videos.

### Task
Analyze the following transcript from a {content_type} video to extract key information and structure.

### Transcript
{transcript}

### Analysis Instructions
1. Identify the main topic and purpose of the content
2. Extract key points, arguments, or teaching moments
3. Identify the logical structure (introduction, body sections, conclusion)
4. Note any specialized terminology or concepts that might need explanation
5. Suggest appropriate chapter markers or sections based on content transitions

### Output Format
Provide your analysis in the following structured format:

```json
{{
  "title": "Suggested title based on content",
  "main_topic": "Primary subject matter",
  "key_points": [
    "Key point 1",
    "Key point 2",
    ...
  ],
  "structure": [
    {{
      "section": "Introduction",
      "timestamp_approx": "beginning",
      "content": "Brief description"
    }},
    {{...}}
  ],
  "terminology": [
    {{
      "term": "Technical term",
      "explanation": "Brief explanation"
    }},
    {{...}}
  ]
}}
```

### Your Response (JSON only):
"""

def get_cultural_adaptation_prompt(text: str, source_lang: str, target_lang: str, content_type: str) -> str:
    """
    Generate prompt for cultural adaptation of content
    
    Args:
        text: Content to adapt culturally
        source_lang: Source language code
        target_lang: Target language code
        content_type: Type of content (educational, marketing, entertainment, etc.)
        
    Returns:
        Formatted prompt for cultural adaptation
    """
    source_lang_name = get_language_name(source_lang)
    target_lang_name = get_language_name(target_lang)
    
    return f"""
### Role
You are a cross-cultural communication expert specializing in adapting {content_type} content from {source_lang_name} to {target_lang_name} cultures.

### Task
Analyze the following content and identify elements that may need cultural adaptation when presented to a {target_lang_name}-speaking audience.

### Content
{text}

### Analysis Instructions
1. Identify culturally specific references, idioms, humor, or examples
2. Flag potential cultural sensitivities or taboos
3. Suggest culturally appropriate alternatives for the target audience
4. Preserve the original intent and message while making it relevant to the target culture

### Output Format
Provide your analysis in the following structured JSON format:

```json
{{
  "cultural_elements": [
    {{
      "original": "Original cultural reference or phrase",
      "issue": "Description of potential cross-cultural issue",
      "suggestion": "Suggested adaptation or alternative"
    }},
    {{...}}
  ],
  "general_recommendations": [
    "General recommendation 1",
    "General recommendation 2"
  ],
  "adapted_content": "Full adapted version of the content with all suggested changes applied"
}}
```

### Your Response (JSON only):
"""
