#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Translation Service
Main service class for translation functionality
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
import pandas as pd

from app.core.config import settings 
from .context_translator import ContextualTranslator
from .batch_processor import BatchProcessor
from .tag_realignment_service import TagRealignmentService
from .terminology import TerminologyManager
from .utils import normalize_language_code, format_time
from ..translation_providers import BaseTranslationProvider, YunwuTranslationProvider # Removed ProviderFactory
from app.services.semantic_service import SemanticService  # Added import
# text_splitter has been moved to .unused - not used in current implementation
from app.utils.file_path_manager import get_file_path_manager, FileType

logger = logging.getLogger(__name__)

class TranslationService:
    """
    Main service for handling translation tasks.
    Coordinates between different components like providers, batch processing, and contextual translation.
    """
    
    def __init__(self, translation_provider_name: Optional[str] = None):
        """
        Initialize the translation service
        
        Args:
            translation_provider_name: Optional provider name override from settings.TRANSLATION_PROVIDER
        """
        # Use provider from argument, or fallback to settings.TRANSLATION_PROVIDER
        # The default in settings is 'yunwu' if TRANSLATION_PROVIDER env var is not set.
        effective_provider_name = translation_provider_name or settings.TRANSLATION_PROVIDER
        
        # Configuration now primarily comes from the central settings object
        self.config = {
            "provider": effective_provider_name,
            # Yunwu configuration from settings (保持兼容)
            "yunwu": {
                "api_key": settings.YUNWU_API_KEY,
                "base_url": settings.YUNWU_BASE_URL,
                "model": settings.YUNWU_MODEL,
                "temperature": settings.YUNWU_TEMPERATURE,
                "max_tokens": settings.YUNWU_MAX_TOKENS,
                "timeout": settings.YUNWU_TIMEOUT,
                "api_version": settings.YUNWU_API_VERSION,
                "organization": settings.YUNWU_ORGANIZATION,
            },
            # Translator configuration from settings (新增)
            "translator": {
                "api_key": settings.TRANSLATOR_API_KEY,
                "base_url": settings.TRANSLATOR_BASE_URL,
                "model": settings.TRANSLATOR_MODEL,
                "temperature": settings.TRANSLATOR_TEMPERATURE,
                "max_tokens": settings.TRANSLATOR_MAX_TOKENS,
                "timeout": settings.TRANSLATOR_TIMEOUT,
            }
        }
        
        # Validation is implicitly handled by Pydantic in Settings for required fields like YUNWU_API_KEY, YUNWU_BASE_URL, YUNWU_MODEL
        # If any of these are missing, Settings instantiation would have failed earlier.
        
        # Initialize sub-components
        self.contextual_translator = ContextualTranslator(self.config)
        self.batch_processor = BatchProcessor(self)
        self.terminology_manager = TerminologyManager()
        self.semantic_service = SemanticService() # Added SemanticService instantiation
        
        # Initialize tag realignment service
        provider = self.get_translation_provider()
        self.tag_realignment_service = TagRealignmentService(provider)
        
        logger.info(f"TranslationService initialized with provider: {self.config['provider']}")
        logger.info(f"  Yunwu Model: {self.config['yunwu']['model']}")
        logger.info(f"  Yunwu Timeout: {self.config['yunwu']['timeout']}")
    
    def get_translation_provider(self):
        """
        Get the appropriate translation provider implementation based on configuration
        
        Returns:
            Translation provider instance based on the configured provider
        """
        provider_name = self.config["provider"] # Get provider name from self.config set in __init__
        provider_config_params = self.config.get(provider_name) # Get specific config for this provider

        if not provider_config_params:
            raise ValueError(f"Configuration for provider '{provider_name}' not found in self.config.")

        # Instantiate provider based on settings
        if provider_name == "yunwu":
            return YunwuTranslationProvider(provider_config_params)
        elif provider_name == "translator":
            return YunwuTranslationProvider(provider_config_params)  # 使用相同的provider类，不同配置
        # Add other providers here if needed in the future
        # elif provider_name == "openai":
        #     from .openai_provider import OpenAITranslationProvider # Assuming it exists
        #     return OpenAITranslationProvider(provider_config_params)
        else:
            raise ValueError(f"Unsupported translation provider: {provider_name}")
            
    def translate_chunk(self, text: str, source_lang: str, target_lang: str, 
                      terminology: Dict = None, additional_context: str = None) -> str:
        """
        Legacy method for backward compatibility
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            terminology: Dictionary of terminology mappings
            additional_context: Additional context information
        
        Returns:
            Translated text
        """
        # Call the enhanced version and extract just the final text
        result = self.contextual_translator.translate_with_context(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            terminology=terminology,
            metadata={"context": additional_context} if additional_context else None
        )
        
        # Return the target text, or original text if translation failed
        return result["target_text"] if result["translation_status"] == "success" else text
    
    def translate_all(self, job_id: int, job_dir: str, source_lang: str, target_langs: Union[str, List[str]], 
                max_workers: int = 5) -> str:
        """
        Translate all chunks in the job directory to multiple target languages
        
        Args:
            job_id: Job ID for context propagation
            job_dir: Directory containing the input files and where results will be saved
            source_lang: Source language code
            target_langs: Target language code(s) as a string or list
            max_workers: Maximum number of parallel workers for translation
            
        Returns:
            Path to the translation results file
        """
        return self.batch_processor.process_batch_translation(
            job_id=job_id,
            job_dir=job_dir,
            source_lang=source_lang,
            target_langs=target_langs,
            max_workers=max_workers
        )
        
    def load_chunks(self, job_dir: str) -> pd.DataFrame:
        """
        Load chunks from the job directory
        
        Args:
            job_dir: Directory containing the chunks
            
        Returns:
            DataFrame with the chunks
        """
        # This is a simplified method - the actual implementation would depend on
        # how the chunks are stored in the job directory
        chunks_path = os.path.join(job_dir, "log", "transcription_text.xlsx")
        if not os.path.exists(chunks_path):
            chunks_path = os.path.join(job_dir, "log", "cleaned_chunks.xlsx")
            
        if not os.path.exists(chunks_path):
            logger.warning(f"No chunks found in {job_dir}")
            return None
            
        try:
            return pd.read_excel(chunks_path, engine='openpyxl')
        except Exception as e:
            logger.error(f"Error loading chunks: {str(e)}")
            return None
    
    def load_terminology(self, job_dir: str) -> Dict:
        """
        Load terminology mappings from the job directory
        
        Args:
            job_dir: Directory containing the terminology file
            
        Returns:
            Dictionary of terminology mappings
        """
        return self.terminology_manager.load_terminology(job_dir)
    
    def save_terminology(self, job_dir: str, terminology: Dict) -> None:
        """
        Save terminology mappings to the job directory
        
        Args:
            job_dir: Directory to save the terminology file to
            terminology: Dictionary of terminology mappings
        """
        self.terminology_manager.save_terminology(job_dir, terminology)
        
    # Forward key utility methods for backward compatibility
    def _normalize_language_code(self, lang_code: str) -> str:
        """Normalizes language code to standard format"""
        return normalize_language_code(lang_code)
        
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to a human-readable format"""
        return format_time(seconds)

    def analyze_content(self, user_id: int, job_id: int, source_lang: str, target_langs: List[str]) -> Dict:
        """
        Analyze content to generate summary and terminology.
        This method reads the transcript file and then calls SemanticService.
        
        Args:
            user_id: User ID
            job_id: Job ID
            source_lang: Source language of the transcript
            target_langs: List of target languages for terminology
            
        Returns:
            Dictionary with analysis results (summary, terminology)
        """
        file_manager = get_file_path_manager()
        
        # Create JobContext from user_id and job_id
        from app.models.job_context import JobContext
        context = JobContext(user_id=user_id, job_id=job_id)
        
        transcript_path = file_manager.get_file_path(
            context=context,
            file_type=FileType.REFINED_TRANSCRIPT
        )
        if not os.path.exists(transcript_path):
            logger.error(f"Transcript file not found at {transcript_path} for job_id={job_id}")
            return {"status": "error", "error": "Transcript file not found"}

        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
        except Exception as e:
            logger.error(f"Error reading transcript file {transcript_path} for job_id={job_id}: {str(e)}")
            return {"status": "error", "error": f"Error reading transcript: {str(e)}"}

        # For now, we'll pass the first target language for terminology generation in SemanticService
        # SemanticService.generate_summary_and_terminology expects a single target_lang
        # This might need adjustment if SemanticService is updated to handle multiple target_langs for terminology
        primary_target_lang = target_langs[0] if target_langs else source_lang

        # Assuming domain can be None or derived if necessary later
        domain = None 

        logger.info(f"Calling SemanticService.generate_summary_and_terminology for job_id={job_id}")
        return self.semantic_service.generate_summary_and_terminology(
            text=transcript_text,
            source_lang=source_lang,
            target_lang=primary_target_lang, # Pass the primary target language
            domain=domain,
            job_id=str(job_id) # Ensure job_id is a string as expected by SemanticService
        )
