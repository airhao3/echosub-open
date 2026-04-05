#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Translation Utilities
Common utility functions for translation services
"""

import functools
import logging
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Custom exception for translation-related errors."""
    pass

def normalize_language_code(lang_code: str) -> Optional[str]:
    """
    Normalize language code to standard format
    
    Args:
        lang_code: Language code to normalize
        
    Returns:
        Normalized language code or None if invalid
    """
    if not lang_code or not isinstance(lang_code, str):
        return None
        
    lang_code = lang_code.strip().lower()
    
    # Fix potential single-character codes
    if lang_code == 'z':
        logger.warning(f"Detected problematic single-character code '{lang_code}', fixing to 'zh'")
        return 'zh'
    
    # Map common short/incorrect codes to standard codes
    lang_mapping = {
        'ch': 'zh',   # Common mistake for Chinese
        'cn': 'zh',   # Common mistake for Chinese
        'jp': 'ja',   # Common mistake for Japanese
        'kr': 'ko',   # Common mistake for Korean
        'du': 'nl',   # Common mistake for Dutch
        'ge': 'de',   # Common mistake for German
    }
    
    if lang_code in lang_mapping:
        return lang_mapping[lang_code]
        
    return lang_code

@functools.lru_cache(maxsize=32)
def get_language_name(lang_code: str) -> str:
    """
    Get full language name from language code (with caching for performance)
    
    Args:
        lang_code: ISO language code
        
    Returns:
        Full language name
    """
    language_names = {
        'zh': 'Chinese', 'en': 'English', 'es': 'Spanish',
        'fr': 'French', 'de': 'German', 'ja': 'Japanese',
        'ko': 'Korean', 'ru': 'Russian', 'ar': 'Arabic',
        'hi': 'Hindi', 'pt': 'Portuguese', 'it': 'Italian',
        'nl': 'Dutch', 'tr': 'Turkish', 'vi': 'Vietnamese',
        'th': 'Thai', 'id': 'Indonesian'
    }
    return language_names.get(lang_code.lower(), f"language with code '{lang_code}'")

def format_time(seconds: float) -> str:
    """
    Format time in seconds to a human-readable format
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    minutes = math.floor(seconds / 60)
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:06.3f}"

def format_time_srt(seconds: float) -> str:
    """
    Format time in seconds to SRT format: HH:MM:SS,mmm
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string in SRT format
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

def truncate_with_meaning(text: str, max_length: int, language: str) -> str:
    """
    Truncate text to max_length while preserving meaning
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        language: Language code for language-specific handling
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
        
    # For CJK languages, character-based truncation works well
    if language in ['zh', 'ja', 'ko']:
        # Try to find a good breaking point like a punctuation mark
        punctuation = ['。', '，', '！', '？', '；', '：', ')', '）', ' ']
        
        for i in range(max_length, max(0, max_length-10), -1):
            if i < len(text) and text[i] in punctuation:
                return text[:i+1] + '...' if i+3 < len(text) else text[:i+1]
        
        # If no good breaking point, just truncate
        return text[:max_length] + '...'
    else:
        # For other languages, word-based truncation
        words = text.split()
        result = ""
        
        for word in words:
            if len(result) + len(word) + 1 > max_length - 3:  # Leave room for "..."
                break
            result += " " + word if result else word
            
        return result + "..." if len(text) > len(result) else result

def detect_sentences(text: str) -> List[str]:
    """
    Detect sentences in text
    
    Args:
        text: Text to analyze
        
    Returns:
        List of sentences
    """
    # Simple sentence detection based on punctuation
    # In a real implementation, this would use more sophisticated NLP
    import re
    
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    
    # Filter out empty sentences
    return [s.strip() for s in sentences if s.strip()]

def merge_dictionaries(dict1: Dict, dict2: Dict, override: bool = True) -> Dict:
    """
    Merge two dictionaries
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        override: Whether values in dict2 should override those in dict1
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = merge_dictionaries(result[key], value, override)
        elif key not in result or override:
            # Add new keys or override existing ones
            result[key] = value
            
    return result
