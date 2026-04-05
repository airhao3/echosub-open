from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseTranslationProvider(ABC):
    """
    Abstract base class for translation providers
    Different translation services (OpenAI, Azure, etc.) will implement this interface
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str, context: Optional[str] = None) -> str:
        """
        Translate text from source language to target language
        
        Args:
            text: The text to translate
            source_lang: The source language code
            target_lang: The target language code
            context: Optional context or instructions for the translation
            
        Returns:
            The translated text
        """
        pass
