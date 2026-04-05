"""
纯外部API转录服务
完全移除本地模型依赖，仅使用外部API
"""

import os
import logging
import traceback
from typing import Dict, Any, Optional, List

from app.utils.file_path_manager import get_file_path_manager, FileType
from .external_api_transcriber import ExternalAPITranscriber
from .utils import TranscriptionUtils

# For type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.job_context import JobContext

# Configure logger
logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    纯外部API转录服务
    不依赖任何本地模型，仅使用外部API进行转录
    """
    
    def __init__(self):
        """初始化纯API转录服务"""
        # 默认配置 - 仅包含API相关配置
        self.config = {
            "api_provider": os.environ.get("EXTERNAL_TRANSCRIPTION_PROVIDER", "whisper_api"),
            "api_key": os.environ.get("EXTERNAL_TRANSCRIPTION_API_KEY", ""),
            "force_api_only": True,
            "enable_local_models": False,
            "enable_demucs": False,
            "enable_gpu": False
        }
        
        # 初始化组件
        self.external_api_transcriber = ExternalAPITranscriber({})
        self.file_manager = get_file_path_manager()
        
        logger.info(f"TranscriptionService initialized - API ONLY MODE")
        logger.info(f"Provider: {self.config['api_provider']}")
        logger.info(f"Force API only: {self.config['force_api_only']}")
    
    def transcribe(self, context: "JobContext", audio_path: str, progress_callback: Optional[callable] = None) -> str:
        """
        使用外部API转录音频文件
        
        Args:
            context: 作业上下文
            audio_path: 音频文件路径
            progress_callback: 进度回调函数
            
        Returns:
            转录结果文件路径
        """
        logger.info(f"[JOB:{context.job_id}] Starting API-only transcription: {audio_path}")
        
        provider = self.config["api_provider"]
        logger.info(f"[JOB:{context.job_id}] Using external API provider: {provider}")
        
        try:
            # 执行外部API转录
            transcription_result = self._transcribe_with_api(
                audio_path=audio_path,
                context=context,
                provider=provider,
                progress_callback=progress_callback
            )
            
            # 保存转录结果
            output_path = TranscriptionUtils.save_transcription_results(transcription_result, context)
            logger.info(f"[JOB:{context.job_id}] API transcription completed, saved to: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"[JOB:{context.job_id}] API transcription failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 记录错误
            error_file = TranscriptionUtils.log_error(f"API transcription failed: {str(e)}", context)
            
            # 创建错误转录结果
            error_results = [{
                'error': True,
                'error_message': f"API transcription failed: {str(e)}",
                'segments': [{
                    'start': 0.0,
                    'end': 1.0,
                    'text': f"[Error: API transcription failed - {str(e)}]",
                    'words': []
                }]
            }]
            
            try:
                TranscriptionUtils.save_transcription_results(error_results, context)
            except Exception as save_error:
                logger.error(f"[JOB:{context.job_id}] Failed to save error results: {str(save_error)}")
            
            raise RuntimeError(f"API transcription failed: {str(e)}. See {error_file} for details.")
    
    def _transcribe_with_api(self, audio_path: str, context: "JobContext",
                           provider: str, progress_callback: Optional[callable] = None) -> List[Dict[str, Any]]:
        """
        使用指定的外部API进行转录
        
        Args:
            audio_path: 音频文件路径
            context: 作业上下文
            provider: API提供商
            progress_callback: 进度回调函数
            
        Returns:
            转录结果列表
        """
        logger.info(f"[JOB:{context.job_id}] Starting external API transcription with {provider}")
        
        if progress_callback:
            progress_callback(10, f"Connecting to {provider} API")
        
        try:
            # 获取语言设置
            language = getattr(context, 'source_language', None)
            if language == 'auto' or not language:
                language = None
            
            logger.info(f"[JOB:{context.job_id}] Using language: {language or 'auto-detect'}")
            
            # 调用外部API
            result = self.external_api_transcriber.transcribe_audio_with_api(
                audio_path=audio_path,
                provider=provider,
                language=language
            )
            
            if progress_callback:
                progress_callback(80, "Processing API response")
            
            # 检查API转录结果
            if result.get('error', False):
                error_msg = result.get('error_message', 'Unknown API error')
                logger.error(f"[JOB:{context.job_id}] External API transcription failed: {error_msg}")
                raise RuntimeError(f"External API transcription failed: {error_msg}")
            
            # 处理成功结果
            segments = result.get('segments', [])
            logger.info(f"[JOB:{context.job_id}] External API transcription successful: {len(segments)} segments")
            
            if progress_callback:
                progress_callback(100, "Transcription completed")
            
            # 返回标准格式
            return [{
                'segments': segments,
                'language': result.get('language', 'unknown'),
                'duration': result.get('duration', 0.0),
                'api_provider': provider,
                'processing_mode': 'api_only'
            }]
            
        except Exception as e:
            logger.error(f"[JOB:{context.job_id}] External API transcription error: {str(e)}")
            raise RuntimeError(f"External API transcription failed: {str(e)}")
    
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_type": "api_only_transcription",
            "provider": self.config["api_provider"],
            "local_models": False,
            "gpu_required": False,
            "fallback_enabled": False,
            "supported_providers": self.external_api_transcriber.get_available_providers(),
            "config": {
                "force_api_only": self.config["force_api_only"],
                "enable_local_models": self.config["enable_local_models"],
                "enable_demucs": self.config["enable_demucs"],
                "enable_gpu": self.config["enable_gpu"]
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            provider = self.config["api_provider"]
            provider_info = self.external_api_transcriber.get_provider_info(provider)
            
            return {
                "status": "healthy",
                "service": "api_only_transcription",
                "provider": provider,
                "provider_available": bool(provider_info),
                "local_models": False,
                "gpu_dependencies": False
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "api_only_transcription"
            }