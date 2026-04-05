import logging
import os
import gzip
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import get_settings

settings = get_settings()

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

# Define a compression-enabled rotating file handler
class CompressedRotatingFileHandler(RotatingFileHandler):
    """Extended version of RotatingFileHandler that compresses rotated files"""
    
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        
    def doRollover(self):
        """Compress rotated files and perform rollover as the parent class"""
        # Call parent rollover first
        super().doRollover()
        
        # Get rotated file name (the one just rotated)
        rotated_filename = f"{self.baseFilename}.1"
        
        # Compress the rotated file if it exists
        if os.path.exists(rotated_filename):
            try:
                with open(rotated_filename, 'rb') as f_in:
                    with gzip.open(f"{rotated_filename}.gz", 'wb') as f_out:
                        f_out.writelines(f_in)
                # Remove the original rotated file
                os.unlink(rotated_filename)
            except Exception as e:
                logging.error(f"Failed to compress rotated log file: {e}")

# Configure logging for the application
def setup_logging() -> None:
    """Setup logging configuration"""
    # Clear any existing handlers from root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set default log level
    root_logger.setLevel(logging.DEBUG)
    
    # Log file paths
    api_log_file = os.path.join(log_dir, "api.log")
    translation_log_file = os.path.join(log_dir, "translation.log")
    celery_log_file = os.path.join(log_dir, "celery.log")
    error_log_file = os.path.join(log_dir, "error.log")
    debug_log_file = os.path.join(log_dir, "debug.log")
    request_log_file = os.path.join(log_dir, "request.log")
    
    # Root logger configuration - only warnings and above by default
    root_logger.setLevel(logging.WARNING)
    
    # Console handler for all logs - only add if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Detailed formatter for translation logs
        translation_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Create file handler for API logs
    file_handler = CompressedRotatingFileHandler(
        api_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    # Safely get DEBUG setting with fallback to False
    debug_mode = getattr(settings, 'DEBUG', False)
    file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Create file handler for translation logs
    translation_handler = CompressedRotatingFileHandler(
        translation_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    translation_handler.setLevel(logging.INFO)
    translation_handler.setFormatter(translation_formatter)
    
    # File handler for all errors
    error_handler = RotatingFileHandler(
        error_log_file, maxBytes=10485760, backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
    )
    error_handler.setFormatter(error_format)
    root_logger.addHandler(error_handler)
    
    # Debug log handler - more detailed information for all components
    # Only add debug handler if not already present
    if not any(h.baseFilename == os.path.abspath(debug_log_file) for h in root_logger.handlers 
              if hasattr(h, 'baseFilename')):
        debug_handler = RotatingFileHandler(
            debug_log_file, maxBytes=10485760, backupCount=10
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s - %(message)s"
        )
        debug_handler.setFormatter(debug_format)
        root_logger.addHandler(debug_handler)
    
    # Request log handler - for tracking HTTP requests
    request_handler = RotatingFileHandler(
        request_log_file, maxBytes=10485760, backupCount=10
    )
    request_handler.setLevel(logging.INFO)
    request_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    request_handler.setFormatter(request_format)
    request_logger = logging.getLogger("app.api.request")
    request_logger.addHandler(request_handler)
    
    # API logger
    api_logger = logging.getLogger("app.api")
    api_handler = CompressedRotatingFileHandler(api_log_file, maxBytes=10485760, backupCount=10)
    api_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    api_handler.setFormatter(api_format)
    api_logger.addHandler(api_handler)
    
    # Celery logger
    celery_logger = logging.getLogger("app.core.tasks")
    celery_handler = RotatingFileHandler(celery_log_file, maxBytes=10485760, backupCount=10)
    celery_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    celery_handler.setFormatter(celery_format)
    celery_logger.addHandler(celery_handler)
    
    # Add translation logger and handler
    translation_logger = logging.getLogger('app.services.translation')
    translation_logger.setLevel(logging.INFO)
    translation_logger.addHandler(translation_handler)
    translation_logger.propagate = False  # Prevent duplicate logs in root logger
    
    # Set loggers for external libraries
    logging.getLogger("uvicorn").handlers = [console_handler]
    logging.getLogger("uvicorn.access").handlers = [console_handler]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Reduce noise from watchfiles module
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    
    # Specific services logging
    for service in ["video_service", "transcription_service", "subtitle_service", 
                   "workflow_service", "job_service"]:
        service_logger = logging.getLogger(f"app.services.{service}")
        service_log_file = os.path.join(log_dir, f"{service}.log")
        
        # Only add handler if not already present
        if not any(hasattr(h, 'baseFilename') and h.baseFilename == os.path.abspath(service_log_file) 
                  for h in service_logger.handlers):
            service_handler = CompressedRotatingFileHandler(service_log_file, maxBytes=5242880, backupCount=8)
            service_format = logging.Formatter(
                "%(asctime)s - %(levelname)s - [%(process)d:%(thread)d] - %(message)s"
            )
            service_handler.setFormatter(service_format)
            service_logger.setLevel(logging.INFO)
            service_logger.addHandler(service_handler)
            # Prevent duplicate logs from propagating to root logger
            service_logger.propagate = False
    
    # Explicitly set level for subtitle_version_service
    logging.getLogger("app.services.subtitle_version_service").setLevel(logging.INFO)

    # Set translation service to DEBUG level for detailed translation context logging
    translation_logger = logging.getLogger("app.services.translation.service")
    translation_log_file = os.path.join(log_dir, "translation_service.log")
    
    # Only add handler if not already present
    if not any(hasattr(h, 'baseFilename') and h.baseFilename == os.path.abspath(translation_log_file) 
              for h in translation_logger.handlers):
        translation_handler = CompressedRotatingFileHandler(translation_log_file, maxBytes=5242880, backupCount=8)
        translation_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(process)d:%(thread)d] - %(pathname)s:%(lineno)d - %(funcName)s - %(message)s"
        )
        translation_handler.setFormatter(translation_format)
        translation_logger.setLevel(logging.DEBUG)  # Set to DEBUG level to capture detailed logs
        translation_logger.addHandler(translation_handler)
        # Prevent duplicate logs from propagating to root logger
        translation_logger.propagate = False
    
    # Processing logger - for detailed job processing status
    processing_logger = logging.getLogger("app.processing")
    processing_log_file = os.path.join(log_dir, "processing.log")
    processing_handler = RotatingFileHandler(processing_log_file, maxBytes=10485760, backupCount=10)
    processing_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    processing_handler.setFormatter(processing_format)
    processing_logger.setLevel(logging.INFO)
    processing_logger.addHandler(processing_handler)
    processing_logger.addHandler(console_handler)  # Also log to console
