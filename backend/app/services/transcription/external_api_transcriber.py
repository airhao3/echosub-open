"""
External API transcription functionality.
Handles transcription using external Whisper-compatible APIs.
"""

import os
import requests
import logging
import traceback
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)


class ExternalAPITranscriber:
    """Handles transcription using external APIs."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the external API transcriber.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.api_config = {
            "whisper_api": {
                "name": "Whisper API",
                "base_url": os.getenv("WHISPER_API_URL", "https://whisper.defaqman.com"),
                "endpoint": "/api/v1/audio/transcriptions",
                "method": "POST",
                "headers": {},  # No auth required
                "max_file_size_mb": 25,
                "supported_formats": [".mp3", ".wav", ".mp4", ".flac", ".ogg", ".webm"],
                "rate_limit": "10 requests per minute",
                "model": os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")
            }
        }
    
    def transcribe_audio_with_api(self, audio_path: str, provider: str = "whisper_api", 
                                  language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe audio using external API.
        
        Args:
            audio_path: Path to the audio file
            provider: API provider name
            language: Language code (optional)
            
        Returns:
            Dictionary containing transcription results
        """
        if provider not in self.api_config:
            return self._create_error_result(f"Unsupported API provider: {provider}")
        
        api_config = self.api_config[provider]
        
        # Validate file exists and format
        if not os.path.exists(audio_path):
            return self._create_error_result(f"File does not exist: {audio_path}")

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        max_chunk_mb = api_config.get("max_file_size_mb", 25) - 1  # 1MB safety margin

        if file_size_mb <= max_chunk_mb:
            # Small enough — single request
            return self._transcribe_single(audio_path, api_config, language)
        else:
            # Too large — split into chunks and transcribe each
            logger.info(f"Audio file {file_size_mb:.1f}MB exceeds {max_chunk_mb}MB, splitting into chunks")
            return self._transcribe_chunked(audio_path, api_config, language, max_chunk_mb)
    
    def _transcribe_single(self, audio_path: str, api_config: Dict[str, Any],
                           language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe a single audio file via API."""
        try:
            url = f"{api_config['base_url']}{api_config['endpoint']}"
            headers = api_config["headers"].copy()

            with open(audio_path, 'rb') as audio_file:
                files = {'file': (os.path.basename(audio_path), audio_file, 'audio/mpeg')}
                data = {
                    'model': api_config.get('model', 'whisper-1'),
                    'response_format': 'verbose_json'
                }
                if language and language != "auto":
                    data['language'] = language

                logger.info(f"Uploading to {api_config['name']}... (timeout=600s)")
                response = requests.post(url, headers=headers, files=files, data=data, timeout=600)

            if response.status_code == 200:
                return self._process_api_response(response.json(), api_config.get('name', 'api'))
            else:
                return self._create_error_result(
                    f"API call failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"External API transcription failed: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_result(f"External API transcription failed: {str(e)}")

    def _transcribe_chunked(self, audio_path: str, api_config: Dict[str, Any],
                            language: Optional[str], max_chunk_mb: float) -> Dict[str, Any]:
        """Split audio into chunks and transcribe each, merging results."""
        import subprocess, math

        # Get audio duration
        try:
            probe = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
                capture_output=True, text=True, timeout=30)
            total_duration = float(probe.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to probe audio duration: {e}")
            return self._create_error_result(f"Cannot determine audio duration: {e}")

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        # Calculate chunk duration based on file size ratio
        chunk_duration = int(total_duration * (max_chunk_mb / file_size_mb))
        chunk_duration = max(60, min(chunk_duration, 1800))  # 1-30 minutes per chunk
        num_chunks = math.ceil(total_duration / chunk_duration)

        logger.info(f"Splitting {total_duration:.0f}s audio into {num_chunks} chunks of ~{chunk_duration}s")

        all_segments = []
        detected_language = "unknown"
        chunk_dir = os.path.join(os.path.dirname(audio_path), "chunks")
        os.makedirs(chunk_dir, exist_ok=True)

        for i in range(num_chunks):
            start_time = i * chunk_duration
            chunk_path = os.path.join(chunk_dir, f"chunk_{i:03d}.mp3")

            # Extract chunk with ffmpeg
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', audio_path,
                    '-ss', str(start_time), '-t', str(chunk_duration),
                    '-acodec', 'libmp3lame', '-ar', '16000', '-ac', '1', '-b:a', '64k',
                    chunk_path
                ], capture_output=True, timeout=120)
            except Exception as e:
                logger.error(f"Failed to extract chunk {i}: {e}")
                continue

            if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) < 1000:
                logger.warning(f"Chunk {i} too small or missing, skipping")
                continue

            logger.info(f"Transcribing chunk {i+1}/{num_chunks} (start={start_time:.0f}s)")
            result = self._transcribe_single(chunk_path, api_config, language)

            if result.get('error'):
                logger.error(f"Chunk {i} failed: {result.get('error_message')}")
                continue

            # Offset timestamps by chunk start time
            for seg in result.get('segments', []):
                seg['start'] = seg.get('start', 0) + start_time
                seg['end'] = seg.get('end', 0) + start_time
                for word in seg.get('words', []):
                    word['start'] = word.get('start', 0) + start_time
                    word['end'] = word.get('end', 0) + start_time
                all_segments.append(seg)

            if result.get('language', 'unknown') != 'unknown':
                detected_language = result['language']

            # Cleanup chunk file
            try:
                os.remove(chunk_path)
            except OSError:
                pass

        # Cleanup chunk directory
        try:
            os.rmdir(chunk_dir)
        except OSError:
            pass

        if not all_segments:
            return self._create_error_result("All chunks failed to transcribe")

        logger.info(f"Merged {len(all_segments)} segments from {num_chunks} chunks")
        return {
            'segments': all_segments,
            'language': detected_language,
            'duration': total_duration,
            'api_provider': api_config.get('name', 'api'),
        }

    def _validate_file(self, file_path: str, api_config: Dict[str, Any]) -> bool:
        """Validate file format and size."""
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in api_config["supported_formats"]:
            logger.error(f"Unsupported file format: {file_ext}")
            return False
        
        # Check file size
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024
        if file_size_mb > api_config["max_file_size_mb"]:
            logger.error(f"File too large: {file_size_mb:.2f}MB > {api_config['max_file_size_mb']}MB")
            return False
        
        logger.info(f"File validation passed: {file_path} ({file_size_mb:.2f}MB)")
        return True
    
    def _process_api_response(self, result_data: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """Process and standardize API response."""
        try:
            # Extract segments from API response
            segments = []
            
            if "segments" in result_data:
                for i, segment in enumerate(result_data["segments"]):
                    segment_dict = {
                        'id': i,
                        'start': segment.get("start", 0.0),
                        'end': segment.get("end", 0.0),
                        'text': segment.get("text", "").strip(),
                    }
                    
                    # Add word-level timestamps if available
                    if "words" in segment:
                        segment_dict['words'] = [{
                            'word': word.get("word", ""),
                            'start': word.get("start", 0.0),
                            'end': word.get("end", 0.0),
                            'score': word.get("probability", 0.0)
                        } for word in segment["words"]]
                    
                    segments.append(segment_dict)
            
            # If no segments but has text, create a single segment
            elif "text" in result_data:
                segments = [{
                    'id': 0,
                    'start': 0.0,
                    'end': result_data.get("duration", 30.0),
                    'text': result_data["text"].strip(),
                    'words': []
                }]
            
            result = {
                'segments': segments,
                'language': result_data.get("language", "unknown"),
                'duration': result_data.get("duration", 0.0),
                'api_provider': provider
            }
            
            logger.info(f"Successfully processed API response: {len(segments)} segments")
            return result
            
        except Exception as e:
            error_msg = f"Error processing API response: {str(e)}"
            logger.error(error_msg)
            return self._create_error_result(error_msg)
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error result."""
        return {
            'error': True,
            'error_message': error_message,
            'segments': [{
                'id': 0,
                'start': 0.0,
                'end': 1.0,
                'text': f"[Error: {error_message}]",
                'words': []
            }]
        }
    
    def get_available_providers(self) -> list:
        """Get list of available API providers."""
        return list(self.api_config.keys())
    
    def get_provider_info(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific API provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Provider configuration or None if not found
        """
        return self.api_config.get(provider)