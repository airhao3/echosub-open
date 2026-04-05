"""
Context management for translation service to maintain conversation context
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TranslationContext:
    """Manages context for translation to improve quality and consistency"""
    
    def __init__(self, window_size: int = 3):
        """Initialize with a context window size"""
        self.window_size = window_size
        self.previous_segments: List[str] = []
        self.next_segments: List[str] = []
        self.terminology: Dict = {}
        self.conversation_history: List[Dict[str, Any]] = []
        
    def update_context(self, current_segment: str, next_segment: Optional[str] = None) -> None:
        """Update the context window with new segments"""
        # Add current segment to history
        self.previous_segments.append(current_segment)
        
        # Maintain window size
        if len(self.previous_segments) > self.window_size:
            self.previous_segments.pop(0)
            
        # Update next segments
        if next_segment:
            self.next_segments = [next_segment] + self.next_segments[:self.window_size-1]
        else:
            self.next_segments = self.next_segments[1:] if self.next_segments else []
            
        # Log the update
        logger.debug(
            f"Context updated - Previous: {len(self.previous_segments)} segments, "
            f"Next: {len(self.next_segments)} segments"
        )
            
    def get_context_prompt(self) -> str:
        """Generate a context prompt for the translation model"""
        context_parts = []
        
        if self.previous_segments:
            context_parts.append("Previous context:")
            context_parts.extend(f"- {s}" for s in self.previous_segments)
            
        if self.next_segments:
            context_parts.append("\nUpcoming context:")
            context_parts.extend(f"- {s}" for s in reversed(self.next_segments))
            
        if self.terminology and 'terms' in self.terminology and self.terminology['terms']:
            context_parts.append("\nTerminology (use these translations):")
            context_parts.extend(
                f"- {term.get('source', '')} -> {term.get('target', '')}" 
                for term in self.terminology['terms']
            )
            
        return "\n".join(context_parts) if context_parts else "No additional context available."
    
    def add_to_history(self, source: str, translation: str, metadata: Optional[Dict] = None) -> None:
        """Add a translation pair to the conversation history"""
        entry = {
            'source': source,
            'translation': translation,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        self.conversation_history.append(entry)
        logger.debug(f"Added to translation history: {entry}")
    
    def clear(self) -> None:
        """Clear all context and history"""
        self.previous_segments = []
        self.next_segments = []
        self.conversation_history = []
        logger.info("Translation context cleared")
