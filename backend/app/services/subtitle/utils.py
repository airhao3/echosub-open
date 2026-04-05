import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Import the auto-correct functionality if available
try:
    import autocorrect_py as autocorrect
    has_autocorrect = True
    logger.info("autocorrect_py library loaded successfully.")
except ImportError:
    has_autocorrect = False
    logger.warning("autocorrect_py library not available. Text beautification will be limited.")


def calc_char_width(char: str) -> float:
    """
    Calculate character width based on language and character type
    Different languages and symbol systems have different character widths
    
    Args:
        char: The character to calculate width for
        
    Returns:
        The width weight of the character
    """
    # CJK characters (Chinese, Japanese, Kanji)
    if '\u4e00' <= char <= '\u9fff':
        return 1.75
    
    # Korean characters
    if '\uac00' <= char <= '\ud7a3':
        return 1.5
    
    # Thai characters
    if '\u0e00' <= char <= '\u0e7f':
        return 1.0
    
    # Full-width forms (including full-width punctuation)
    if '\uff01' <= char <= '\uff60' or '\uffe0' <= char <= '\uffe6':
        return 1.75
    
    # Default for western characters
    return 1.0


def calc_text_width(text: str) -> float:
    """
    Calculate the total width of text based on character width weights
    
    Args:
        text: The text to calculate width for
        
    Returns:
        The total width weight of the text
    """
    if not text:
        return 0.0
    
    return sum(calc_char_width(char) for char in text)


def clean_text_for_matching(text: str) -> str:
    """
    Clean text for better matching
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
        
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation that might interfere with matching
    text = re.sub(r'[.,;:\\"!?()\[\]{}]', '', text)
    
    # Trim whitespace
    text = text.strip()
    
    return text


def time_to_srt_format(seconds: float) -> str:
    """
    Convert time in seconds to SRT format (HH:MM:SS,mmm)
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Time in SRT format
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"


def check_ffmpeg() -> bool:
    """
    Check if FFmpeg is installed and available in the PATH
    
    Returns:
        True if FFmpeg is available, False otherwise
    """
    import subprocess
    import shutil
    
    # First check using shutil (faster)
    if shutil.which("ffmpeg"):
        return True
    
    # If not found with shutil, try running ffmpeg -version
    try:
        result = subprocess.run(["ffmpeg", "-version"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True, 
                               check=False)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"FFmpeg check failed: {str(e)}")
        return False
