import json
import math
import logging
import requests
from typing import List, Dict, Any, Optional

# Use absolute import
from app.core.config import get_settings
from .utils import calc_text_width

logger = logging.getLogger(__name__)
settings = get_settings()

def split_sentence_by_ai(text: str, is_vertical_video: bool = False) -> List[str]:
    """
    Use OpenAI API for intelligent sentence segmentation
    Similar to the original videolingo project's split_sentence function
    
    Args:
        text: The text to split
        is_vertical_video: Whether this is for a vertical video (requiring stricter width limits)
        
    Returns:
        List of segmented sentences from AI, empty list if splitting fails
    """
    try:
        # Check API settings
        if not settings.OPENAI_API_KEY or not settings.OPENAI_MODEL:
            logger.warning("OpenAI API settings not configured, skipping AI sentence split")
            return []
            
        # Calculate needed splits based on text width
        text_width = calc_text_width(text)
        # Set character limits: 15 for vertical videos, 30 for horizontal videos
        max_width = 15 if is_vertical_video else 30
        logger.info(f"AI splitter using max {max_width} characters (vertical: {is_vertical_video})")
        
        # If text isn't long enough, no need to split
        if text_width <= max_width:
            return [text]
            
        # Calculate number of needed parts
        num_parts = math.ceil(text_width / max_width)
        # Limit parts to avoid overly complex API calls
        num_parts = min(num_parts, 5)
        
        # Build request
        prompt = f"""Split the following sentence into {num_parts} natural parts, each part should be around {max_width} characters or less.
Only split at natural pauses or punctuation when possible. Maintain the meaning and flow.
Format your response as a JSON with a key named 'split' that contains the split sentence with [br] as separators between parts.

Sentence to split: {text}

Example response format:
{{"split": "part1[br]part2[br]part3"}}
"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        
        api_url = f"{settings.OPENAI_BASE_URL}/chat/completions"
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        # Add response_format for models that support it
        if settings.OPENAI_MODEL in ["gpt-4-1106-preview", "gpt-4-vision-preview", "gpt-4-turbo", "gpt-3.5-turbo-1106"]:
            payload["response_format"] = {"type": "json_object"}
        
        # Send request
        logger.info(f"Sending AI sentence split request for text: {text[:30]}...")
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.warning(f"AI sentence split failed with status {response.status_code}: {response.text}")
            return []
            
        # Parse response
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        
        # Handle potential JSON format issues
        try:
            if not content.strip().startswith('{'):
                # Try to extract JSON portion
                json_start = content.find('{')
                json_end = content.rfind('}')
                if json_start >= 0 and json_end > json_start:
                    content = content[json_start:json_end+1]
                else:
                    logger.warning(f"Unable to extract JSON from response: {content}")
                    return []
                    
            result = json.loads(content)
            
            # Validate response format
            if "split" not in result:
                logger.warning(f"Invalid AI response format, missing 'split' key: {result}")
                return []
                
            # Split text
            segments = result["split"].split("[br]")
            
            # Validate result
            if len(segments) < 2:
                logger.warning(f"AI split returned too few segments: {len(segments)}")
                return []
                
            # Filter empty segments
            segments = [s.strip() for s in segments if s.strip()]
            
            logger.info(f"AI sentence split successful: {len(segments)} segments")
            return segments
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}\nResponse: {content}")
            return []
            
    except Exception as e:
        logger.error(f"Error in AI sentence split: {str(e)}")
        return []
    
    return []
