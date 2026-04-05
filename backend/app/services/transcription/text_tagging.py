"""
Text Tagging Service

This module provides functionality to add numeric tags to segmented transcription text.
The tags are used for maintaining timestamp alignment through the refinement and translation pipeline.
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.utils.file_path_manager import FilePathManager, FileType
from app.models.job_context import JobContext

logger = logging.getLogger(__name__)


class TextTaggingService:
    """
    Service for adding numeric tags to segmented transcription text.
    
    This service implements the tag-based alignment system where each segment
    is tagged with [1], [2], [3], etc. for precise timing maintenance through
    the LLM refinement and translation pipeline.
    """
    
    def __init__(self):
        """Initialize the text tagging service."""
        self.file_manager = FilePathManager()
    
    def add_tags_to_segments(self, input_text: str) -> str:
        """
        Add sequential numeric tags to text segments.
        
        Args:
            input_text: Raw segmented text (one segment per line)
            
        Returns:
            Tagged text with [1], [2], [3] prefixes
        """
        if not input_text or not input_text.strip():
            logger.warning("Empty input text provided for tagging")
            return ""
        
        lines = input_text.strip().split('\n')
        tagged_lines = []
        tag_number = 1
        
        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            # Check if line already has a tag
            if re.match(r'^\[\d+\]', line):
                # Line already tagged, keep as is
                tagged_lines.append(line)
                # Extract and update tag number for next line
                match = re.match(r'^\[(\d+)\]', line)
                if match:
                    tag_number = int(match.group(1)) + 1
            else:
                # Add tag to line
                tagged_line = f"[{tag_number}] {line}"
                tagged_lines.append(tagged_line)
                tag_number += 1
        
        result = '\n'.join(tagged_lines)
        logger.info(f"Added tags to {len(tagged_lines)} segments")
        return result
    
    def process_segmented_transcript(self, context: JobContext) -> Dict[str, Any]:
        """
        Process the segmented transcript by adding numeric tags.
        
        Args:
            context: JobContext containing user_id and job_id
            
        Returns:
            Dictionary containing processing results and output paths
        """
        try:
            # Get input path (segmented transcript)
            input_path = self.file_manager.get_file_path(
                context, FileType.SEGMENTED_TRANSCRIPT
            )
            
            # Get output path (labeled segmented transcript)
            output_path = self.file_manager.get_file_path(
                context, FileType.LABELED_SEGMENTED_TRANSCRIPT
            )
            
            # Check if input file exists
            if not os.path.exists(input_path):
                error_msg = f"Segmented transcript not found at {input_path}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error_message': error_msg,
                    'input_path': input_path,
                    'output_path': output_path
                }
            
            # Read input text
            with open(input_path, 'r', encoding='utf-8') as f:
                input_text = f.read()
            
            logger.info(f"Read {len(input_text)} characters from {input_path}")
            
            # Add tags to segments
            tagged_text = self.add_tags_to_segments(input_text)
            
            if not tagged_text:
                error_msg = "Failed to generate tagged text"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error_message': error_msg,
                    'input_path': input_path,
                    'output_path': output_path
                }
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write tagged text to output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tagged_text)
            
            logger.info(f"Successfully wrote tagged transcript to {output_path}")
            
            # Count segments
            segment_count = len([line for line in tagged_text.split('\n') if line.strip()])
            
            return {
                'success': True,
                'input_path': input_path,
                'output_path': output_path,
                'segment_count': segment_count,
                'message': f'Successfully tagged {segment_count} segments'
            }
            
        except Exception as e:
            error_msg = f"Error during text tagging: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error_message': error_msg,
                'input_path': input_path if 'input_path' in locals() else None,
                'output_path': output_path if 'output_path' in locals() else None
            }
    
    def validate_tagged_text(self, text: str) -> Dict[str, Any]:
        """
        Validate that text contains proper sequential numeric tags.
        
        Args:
            text: Tagged text to validate
            
        Returns:
            Dictionary with validation results
        """
        if not text or not text.strip():
            return {
                'valid': False,
                'error': 'Empty text',
                'tags_found': [],
                'missing_tags': [],
                'duplicate_tags': []
            }
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        tag_pattern = re.compile(r'^\[(\d+)\]')
        
        tags_found = []
        duplicate_tags = []
        tag_counts = {}
        
        for line in lines:
            match = tag_pattern.match(line)
            if match:
                tag_num = int(match.group(1))
                tags_found.append(tag_num)
                
                if tag_num in tag_counts:
                    tag_counts[tag_num] += 1
                    if tag_num not in duplicate_tags:
                        duplicate_tags.append(tag_num)
                else:
                    tag_counts[tag_num] = 1
        
        # Check for sequential tags
        tags_found.sort()
        expected_tags = list(range(1, len(lines) + 1))
        missing_tags = [tag for tag in expected_tags if tag not in tags_found]
        
        is_valid = (
            len(tags_found) == len(lines) and  # All lines should have tags
            len(missing_tags) == 0 and        # No missing tags
            len(duplicate_tags) == 0 and      # No duplicate tags
            tags_found == expected_tags       # Sequential tags
        )
        
        return {
            'valid': is_valid,
            'total_lines': len(lines),
            'tagged_lines': len(tags_found),
            'tags_found': tags_found,
            'missing_tags': missing_tags,
            'duplicate_tags': duplicate_tags,
            'error': None if is_valid else 'Invalid tag sequence'
        }