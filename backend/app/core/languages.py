"""
Centralized configuration for supported languages.
This file contains two lists:
1. SOURCE_LANGUAGES: Based on OpenAI Whisper's capabilities for transcription.
2. TARGET_LANGUAGES: Based on the translation capabilities of the LLM (e.g., Gemini).
"""

# List of languages supported by Whisper for transcription
# Sourced from user-provided, tiered list.
SOURCE_LANGUAGES = [
    # Tier 1: Best performance
    {"code": "auto", "name": "Auto Detect"},
    {"code": "en", "name": "English"},
    {"code": "zh", "name": "Chinese"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "ru", "name": "Russian"},

    # Tier 2: Good performance
    {"code": "it", "name": "Italian"},
    {"code": "nl", "name": "Dutch"},
    {"code": "id", "name": "Indonesian"},
    {"code": "ar", "name": "Arabic"},
    {"code": "hi", "name": "Hindi"},
    {"code": "vi", "name": "Vietnamese"},
    {"code": "tr", "name": "Turkish"},
    {"code": "th", "name": "Thai"},
    {"code": "pl", "name": "Polish"},
    {"code": "uk", "name": "Ukrainian"},

    # Tier 3: Moderate performance
    {"code": "el", "name": "Greek"},
    {"code": "cs", "name": "Czech"},
    {"code": "hu", "name": "Hungarian"},
    {"code": "fi", "name": "Finnish"},
    {"code": "he", "name": "Hebrew"},
    {"code": "sw", "name": "Swahili"},
    {"code": "ro", "name": "Romanian"},
    {"code": "bn", "name": "Bengali"},
    {"code": "ur", "name": "Urdu"},
    {"code": "ms", "name": "Malay"},

    # Tier 4: Limited performance (Low-resource)
    {"code": "is", "name": "Icelandic"},
    {"code": "eu", "name": "Basque"},
    {"code": "ca", "name": "Catalan"},
    {"code": "mt", "name": "Maltese"},
    {"code": "my", "name": "Burmese"},
    {"code": "si", "name": "Sinhala"},
    {"code": "ne", "name": "Nepali"},
    {"code": "km", "name": "Khmer"},
    {"code": "zu", "name": "Zulu"},
    {"code": "haw", "name": "Hawaiian"},
    {"code": "br", "name": "Breton"},
    {"code": "oc", "name": "Occitan"},
    {"code": "lb", "name": "Luxembourgish"},
    {"code": "tt", "name": "Tatar"},
]

# Comprehensive list of target languages for translation, based on modern LLM capabilities.
# This list includes 50+ languages to match our marketing claims and global reach.
TARGET_LANGUAGES = [
    # Tier 1: Major world languages with excellent translation quality
    {"code": "en", "name": "English"},
    {"code": "zh", "name": "Chinese (Simplified)"},
    {"code": "zh-TW", "name": "Chinese (Traditional)"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "ru", "name": "Russian"},
    {"code": "it", "name": "Italian"},
    {"code": "ar", "name": "Arabic"},
    {"code": "hi", "name": "Hindi"},
    
    # Tier 2: European languages
    {"code": "nl", "name": "Dutch"},
    {"code": "pl", "name": "Polish"},
    {"code": "uk", "name": "Ukrainian"},
    {"code": "tr", "name": "Turkish"},
    {"code": "sv", "name": "Swedish"},
    {"code": "da", "name": "Danish"},
    {"code": "no", "name": "Norwegian"},
    {"code": "fi", "name": "Finnish"},
    {"code": "el", "name": "Greek"},
    {"code": "cs", "name": "Czech"},
    {"code": "hu", "name": "Hungarian"},
    {"code": "ro", "name": "Romanian"},
    {"code": "bg", "name": "Bulgarian"},
    {"code": "hr", "name": "Croatian"},
    {"code": "sk", "name": "Slovak"},
    {"code": "sl", "name": "Slovenian"},
    {"code": "et", "name": "Estonian"},
    {"code": "lv", "name": "Latvian"},
    {"code": "lt", "name": "Lithuanian"},
    
    # Tier 3: Asian and Pacific languages
    {"code": "vi", "name": "Vietnamese"},
    {"code": "th", "name": "Thai"},
    {"code": "id", "name": "Indonesian"},
    {"code": "ms", "name": "Malay"},
    {"code": "tl", "name": "Filipino"},
    {"code": "bn", "name": "Bengali"},
    {"code": "ur", "name": "Urdu"},
    {"code": "ta", "name": "Tamil"},
    {"code": "te", "name": "Telugu"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "kn", "name": "Kannada"},
    {"code": "gu", "name": "Gujarati"},
    {"code": "pa", "name": "Punjabi"},
    {"code": "mr", "name": "Marathi"},
    {"code": "ne", "name": "Nepali"},
    {"code": "si", "name": "Sinhala"},
    {"code": "my", "name": "Burmese"},
    {"code": "km", "name": "Khmer"},
    {"code": "lo", "name": "Lao"},
    
    # Tier 4: Middle Eastern and African languages
    {"code": "he", "name": "Hebrew"},
    {"code": "fa", "name": "Persian"},
    {"code": "sw", "name": "Swahili"},
    {"code": "am", "name": "Amharic"},
    {"code": "zu", "name": "Zulu"},
    {"code": "af", "name": "Afrikaans"},
    
    # Tier 5: Additional European and regional languages
    {"code": "ca", "name": "Catalan"},
    {"code": "eu", "name": "Basque"},
    {"code": "gl", "name": "Galician"},
    {"code": "is", "name": "Icelandic"},
    {"code": "mt", "name": "Maltese"},
    {"code": "cy", "name": "Welsh"},
    {"code": "ga", "name": "Irish"},
    {"code": "mk", "name": "Macedonian"},
    {"code": "sq", "name": "Albanian"},
    {"code": "be", "name": "Belarusian"},
    {"code": "kk", "name": "Kazakh"},
    {"code": "ky", "name": "Kyrgyz"},
    {"code": "uz", "name": "Uzbek"},
    {"code": "az", "name": "Azerbaijani"},
    {"code": "hy", "name": "Armenian"},
    {"code": "ka", "name": "Georgian"},
    {"code": "mn", "name": "Mongolian"},
]
