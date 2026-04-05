#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Terminology Manager
Manages terminology dictionaries for consistent translation
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class TerminologyManager:
    """
    Manages terminology dictionaries for consistent translation
    """
    
    def __init__(self):
        """Initialize the terminology manager"""
        self.global_terminology = {}
        self.terminology_cache = {}
        
        # Check for global terminology file
        global_path = os.environ.get("TERMINOLOGY_GLOBAL_PATH", "")
        if global_path and os.path.exists(global_path):
            try:
                with open(global_path, 'r', encoding='utf-8') as f:
                    self.global_terminology = json.load(f)
                logger.info(f"Loaded global terminology from {global_path}: {len(self.global_terminology)} terms")
            except Exception as e:
                logger.warning(f"Failed to load global terminology from {global_path}: {str(e)}")
    
    def load_terminology(self, job_dir: str) -> Dict:
        """
        Load terminology map from JSON file
        
        Args:
            job_dir: Directory containing the terminology file (can be content hash or job directory)
            
        Returns:
            Dictionary of terminology mappings
        """
        # Check cache first
        if job_dir in self.terminology_cache:
            logger.debug(f"Using cached terminology for {job_dir}")
            return self.terminology_cache[job_dir]
            
        # Try to determine if this is a content hash or job directory
        # Look for indicators of hash format in the path
        is_content_hash = any(marker in job_dir for marker in ['content/', 'content\\'])
        video_hash = os.path.basename(job_dir) if is_content_hash else None
        
        # Get file path manager
        from app.utils.file_path_manager import get_file_path_manager, FileType
        file_manager = get_file_path_manager()
        
        # Determine terminology path using FilePathManager if possible
        if video_hash and len(video_hash) > 16:  # Likely a content hash
            try:
                log_dir = os.path.dirname(file_manager.get_file_path(video_hash, FileType.LOG))
                terminology_path = os.path.join(log_dir, "terminology.json")
                logger.debug(f"Using content hash path for terminology: {terminology_path}")
            except Exception as e:
                logger.warning(f"Error using FilePathManager for terminology path: {str(e)}")
                terminology_path = os.path.join(job_dir, "log", "terminology.json")
        else:
            # Fallback to traditional path
            terminology_path = os.path.join(job_dir, "log", "terminology.json")
            logger.debug(f"Using traditional path for terminology: {terminology_path}")
        
        # Initialize with empty terminology if file doesn't exist
        if not os.path.exists(terminology_path):
            terminology = {}
            os.makedirs(os.path.dirname(terminology_path), exist_ok=True)
            with open(terminology_path, "w", encoding="utf-8") as f:
                json.dump(terminology, f, ensure_ascii=False, indent=4)
            
            # Merge with global terminology if available
            merged_terminology = self._merge_terminology(terminology, self.global_terminology)
            
            # Update cache and return
            self.terminology_cache[job_dir] = merged_terminology
            return merged_terminology
        
        # Load existing terminology
        try:
            with open(terminology_path, "r", encoding="utf-8") as f:
                terminology = json.load(f)
                
            # Merge with global terminology if available
            merged_terminology = self._merge_terminology(terminology, self.global_terminology)
            
            # Update cache and return
            self.terminology_cache[job_dir] = merged_terminology
            return merged_terminology
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in terminology file: {terminology_path}")
            return {}
    
    def save_terminology(self, job_dir: str, terminology: Dict) -> None:
        """
        Save terminology map to JSON file
        
        Args:
            job_dir: Directory to save the terminology file to (can be content hash or job directory)
            terminology: Dictionary of terminology mappings
        """
        # Try to determine if this is a content hash or job directory
        # Look for indicators of hash format in the path
        is_content_hash = any(marker in job_dir for marker in ['content/', 'content\\'])
        video_hash = os.path.basename(job_dir) if is_content_hash else None
        
        # Get file path manager
        from app.utils.file_path_manager import get_file_path_manager, FileType
        file_manager = get_file_path_manager()
        
        # Determine terminology path using FilePathManager if possible
        if video_hash and len(video_hash) > 16:  # Likely a content hash
            try:
                log_dir = os.path.dirname(file_manager.get_file_path(video_hash, FileType.LOG))
                terminology_path = os.path.join(log_dir, "terminology.json")
                logger.debug(f"Using content hash path for terminology: {terminology_path}")
            except Exception as e:
                logger.warning(f"Error using FilePathManager for terminology path: {str(e)}")
                terminology_path = os.path.join(job_dir, "log", "terminology.json")
        else:
            # Fallback to traditional path
            terminology_path = os.path.join(job_dir, "log", "terminology.json")
            logger.debug(f"Using traditional path for terminology: {terminology_path}")
        
        os.makedirs(os.path.dirname(terminology_path), exist_ok=True)
        
        with open(terminology_path, "w", encoding="utf-8") as f:
            json.dump(terminology, f, ensure_ascii=False, indent=4)
        
        # Update cache
        self.terminology_cache[job_dir] = terminology
        
        logger.info(f"Saved terminology with {len(terminology.get('terms', []))} terms to {terminology_path}")
    
    def _merge_terminology(self, job_terminology: Dict, global_terminology: Dict) -> Dict:
        """
        Merge job-specific terminology with global terminology
        Job terminology takes precedence
        
        Args:
            job_terminology: Job-specific terminology
            global_terminology: Global terminology
            
        Returns:
            Merged terminology dictionary
        """
        if not global_terminology:
            return job_terminology
            
        # Start with a copy of global terminology
        merged = global_terminology.copy()
        
        # Override with job-specific terminology
        for term, translation in job_terminology.items():
            merged[term] = translation
            
        return merged
    
    def extract_terms_from_text(self, text: str, min_length: int = 2, max_terms: int = 10) -> List[str]:
        """
        Extract potential terminology candidates from text
        
        Args:
            text: Source text to analyze
            min_length: Minimum term length to consider
            max_terms: Maximum number of terms to extract
            
        Returns:
            List of potential terminology candidates
        """
        # Simple implementation - in a real system, this would use more
        # sophisticated NLP techniques for extracting domain-specific terms
        
        # Split text into words
        words = text.split()
        
        # Filter words by length
        candidates = [word for word in words if len(word) >= min_length]
        
        # Count term frequencies
        from collections import Counter
        frequency = Counter(candidates)
        
        # Get the most common terms
        common_terms = [term for term, count in frequency.most_common(max_terms)]
        
        return common_terms
    
    def add_term(self, job_dir: str, source_term: str, target_term: str, 
               domain: str = "general", priority: str = "normal") -> Dict:
        """
        Add a term to the terminology dictionary
        
        Args:
            job_dir: Directory containing the terminology file
            source_term: Source language term
            target_term: Target language term
            domain: Domain category for the term
            priority: Priority level (normal, high)
            
        Returns:
            Updated terminology dictionary
        """
        # Load current terminology
        terminology = self.load_terminology(job_dir)
        
        # Create or update term
        if domain != "general" or priority != "normal":
            terminology[source_term] = {
                "translation": target_term,
                "domain": domain,
                "priority": priority
            }
        else:
            # Simple string mapping for basic terms
            terminology[source_term] = target_term
            
        # Save updated terminology
        self.save_terminology(job_dir, terminology)
        
        return terminology
    
    def get_domain_terms(self, job_dir: str, domain: str) -> Dict:
        """
        Get terms for a specific domain
        
        Args:
            job_dir: Directory containing the terminology file
            domain: Domain to filter terms by
            
        Returns:
            Dictionary of terms for the specified domain
        """
        terminology = self.load_terminology(job_dir)
        domain_terms = {}
        
        for term, translation in terminology.items():
            if isinstance(translation, dict) and translation.get("domain") == domain:
                domain_terms[term] = translation
            elif domain == "general" and not isinstance(translation, dict):
                domain_terms[term] = translation
                
        return domain_terms
    
    def get_term_suggestions(self, job_dir: str, source_lang: str, target_lang: str, text: str) -> Dict:
        """
        Get term suggestions for a text based on existing terminology and text analysis
        
        Args:
            job_dir: Directory containing the terminology file
            source_lang: Source language code
            target_lang: Target language code
            text: Source text to analyze
            
        Returns:
            Dictionary of term suggestions
        """
        # This is a placeholder for a more sophisticated term suggestion system
        # In a real implementation, this would use NLP techniques to identify
        # important terms and suggest translations based on context
        
        # Extract potential terms from text
        candidates = self.extract_terms_from_text(text)
        
        # Load existing terminology
        terminology = self.load_terminology(job_dir)
        
        # Find matches in existing terminology
        suggestions = {}
        for term in candidates:
            if term in terminology:
                # Term already exists in terminology
                translation = terminology[term]
                if isinstance(translation, dict) and "translation" in translation:
                    suggestions[term] = translation["translation"]
                else:
                    suggestions[term] = translation
        
        return suggestions
