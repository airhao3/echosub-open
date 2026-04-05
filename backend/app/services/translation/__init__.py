#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Translation service package
Provides modular components for high-quality contextual translation
"""

# Import main service class for backward compatibility
from .service import TranslationService
from .context_manager import TranslationContext
from .quality_assessment import TranslationQualityAssessor, QualityScores
from .enhanced_translator import EnhancedTranslator

__all__ = [
    'TranslationService',
    'TranslationContext',
    'TranslationQualityAssessor',
    'QualityScores',
    'EnhancedTranslator'
]
