import os
import json
import shutil
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.crud.crud_subtitle_edit import subtitle_version
from app.models.subtitle_edit import SubtitleVersion
from app.schemas.subtitle_edit import SubtitleVersionCreate
from app.utils.file_path_manager import FilePathManager, FileType, get_file_path_manager
from app.models.job_context import JobContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class SubtitleVersionService:
    """字幕版本管理服务"""
    
    def __init__(self):
        self.file_manager = get_file_path_manager()
    
    def _get_job_context(self, job_id: int, user_id: int = 1) -> JobContext:
        """Create JobContext for file path operations"""
        return JobContext(user_id=user_id, job_id=job_id, content_hash=None)
    
    def save_modified_version(
        self,
        db: Session,
        job_id: int,
        language: str,
        subtitles: List[Dict[str, Any]],
        user_id: int = 1
    ) -> str:
        """
        保存修改版本（只保存两个版本：源文件和修改版本）
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            subtitles: 字幕数据
            user_id: 用户ID
            
        Returns:
            version_id: 版本ID
        """
        try:
            # Use file_path_manager for modified subtitle path
            context = self._get_job_context(job_id, user_id)
            file_path = self.file_manager.get_file_path(
                context, FileType.MODIFIED_SUBTITLE, language=language
            )
            
            # 保存字幕文件
            subtitle_data = {
                "version": "modified",
                "timestamp": datetime.now().isoformat(),
                "description": "用户修改版本",
                "language": language,
                "job_id": job_id,
                "subtitles": subtitles,
                "metadata": {
                    "total_subtitles": len(subtitles),
                    "total_duration": self._calculate_total_duration(subtitles)
                }
            }
            
            # Use file_path_manager for JSON writing
            self.file_manager.write_json(file_path, subtitle_data)
            
            # 删除所有旧的版本记录，只保留源文件和修改版本
            self._cleanup_old_versions(db, job_id, language)
            
            # 创建或更新修改版本记录
            existing_version = subtitle_version.get_version_by_type(db, job_id, language, "modified")
            if existing_version:
                # 更新现有记录
                existing_version.file_path = file_path
                existing_version.file_size = os.path.getsize(file_path)
                existing_version.created_at = datetime.now()
                db.commit()
                db_version = existing_version
            else:
                # 创建新记录
                version_record = SubtitleVersionCreate(
                    job_id=job_id,
                    language=language,
                    version_number=2,  # 固定版本号：1=源文件，2=修改版本
                    file_path=file_path,
                    file_format="json",
                    file_size=os.path.getsize(file_path),
                    description="用户修改版本",
                    is_current="true"  # 修改版本为当前版本
                )
                db_version = subtitle_version.create_version(db=db, version_data=version_record)
            
            logger.info(f"Saved modified version for job {job_id}, language {language}")
            return str(db_version.id)
            
        except Exception as e:
            logger.error(f"Error saving working version: {str(e)}")
            raise
    
    def save_working_version(
        self,
        db: Session,
        job_id: int,
        language: str,
        subtitles: List[Dict[str, Any]],
        description: str = "工作版本",
        auto_save: bool = False,
        user_id: int = 1
    ) -> str:
        """
        保存工作版本（与API端点兼容的方法）
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            subtitles: 字幕数据
            description: 版本描述
            auto_save: 是否为自动保存
            user_id: 用户ID
            
        Returns:
            version_id: 版本ID
        """
        try:
            # 保存工作文件
            self._save_current_working_files(job_id, language, subtitles, user_id)
            
            # 生成版本文件using file_path_manager
            context = self._get_job_context(job_id, user_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"working_{timestamp}.json" if not auto_save else f"auto_save_{timestamp}.json"
            
            # DEBUG LOGGING
            logger.info(f"[SAVE VERSION DEBUG] Preparing to get file path with:")
            logger.info(f"[SAVE VERSION DEBUG]   - context: user_id={context.user_id}, job_id={context.job_id}")
            logger.info(f"[SAVE VERSION DEBUG]   - file_type: {FileType.VERSION_FILE}")
            logger.info(f"[SAVE VERSION DEBUG]   - language: {language}")
            logger.info(f"[SAVE VERSION DEBUG]   - filename: {file_name}")
            
            file_path = self.file_manager.get_file_path(
                context, FileType.VERSION_FILE, language=language, filename=file_name
            )
            
            # 保存版本数据
            version_data = {
                "version": "working",
                "timestamp": datetime.now().isoformat(),
                "description": description,
                "language": language,
                "job_id": job_id,
                "auto_save": auto_save,
                "subtitles": subtitles,
                "metadata": {
                    "total_subtitles": len(subtitles),
                    "total_duration": self._calculate_total_duration(subtitles)
                }
            }
            
            # Use file_path_manager for JSON writing
            self.file_manager.write_json(file_path, version_data)
            
            # Auto-sync the version file to remote storage (S3)
            self.file_manager.auto_sync_file_to_remote(file_path, logger.info)
            
            # 创建数据库版本记录
            version_number = self._get_next_version_number(db, job_id, language)
            version_record = SubtitleVersionCreate(
                job_id=job_id,
                language=language,
                version_number=version_number,
                file_path=file_path,
                file_format="json",
                file_size=os.path.getsize(file_path),
                description=description,
                is_current="true" if not auto_save else "false"
            )
            
            db_version = subtitle_version.create_version(db=db, version_data=version_record)
            
            logger.info(f"Saved working version for job {job_id}, language {language}, auto_save={auto_save}")
            return str(db_version.id)
            
        except Exception as e:
            logger.error(f"Error saving working version: {str(e)}")
            raise
    
    def publish_version(
        self,
        db: Session,
        job_id: int,
        language: str,
        user_id: int,
        version_id: Optional[str] = None,
        description: str = "发布版本"
    ) -> SubtitleVersion:
        """
        发布版本（设为当前正式版本）
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            user_id: 用户ID
            version_id: 版本ID，如果不提供则使用最新版本
            description: 发布描述
            
        Returns:
            发布的版本记录
        """
        try:
            # 获取要发布的版本
            if version_id:
                version_to_publish = subtitle_version.get(db=db, id=int(version_id))
            else:
                versions = subtitle_version.get_versions(db=db, job_id=job_id, language=language)
                version_to_publish = versions[0] if versions else None
            
            if not version_to_publish:
                raise ValueError("No version found to publish")
            
            # 加载版本数据
            with open(version_to_publish.file_path, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
            
            subtitles = version_data.get("subtitles", [])
            
            # 保存为当前工作文件
            self._save_current_working_files(job_id, language, subtitles, user_id)
            
            # 创建发布版本记录
            publish_version_number = subtitle_version.get_next_version_number(
                db=db, job_id=job_id, language=language
            )
            
            publish_file_path = self._create_published_version_file(
                job_id, language, publish_version_number, subtitles, description, user_id
            )
            
            publish_record = SubtitleVersionCreate(
                job_id=job_id,
                language=language,
                version_number=publish_version_number,
                file_path=publish_file_path,
                file_format="json",
                file_size=os.path.getsize(publish_file_path),
                description=f"发布版本 - {description}",
                is_current="true"
            )
            
            published_version = subtitle_version.create_version(db=db, version_data=publish_record)
            
            logger.info(f"Published version {publish_version_number} for job {job_id}, language {language}")
            return published_version
            
        except Exception as e:
            logger.error(f"Error publishing version: {str(e)}")
            raise
    
    def restore_version(
        self,
        db: Session,
        job_id: int,
        language: str,
        version_id: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        恢复到指定版本
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            version_id: 要恢复的版本ID
            user_id: 用户ID
            
        Returns:
            恢复的字幕数据
        """
        try:
            # 特殊处理：如果要恢复的是最初源版本，直接加载源文件
            version_record = subtitle_version.get(db=db, id=int(version_id))
            if version_record and version_record.version_number == 1:
                # 这是源版本，直接加载 subtitle_src.json using file_path_manager
                context = self._get_job_context(job_id, user_id)
                src_file = self.file_manager.get_file_path(context, FileType.SUBTITLE_SRC_JSON)
                
                if os.path.exists(src_file):
                    logger.info(f"Loading original source subtitles from: {src_file}")
                    with open(src_file, 'r', encoding='utf-8') as f:
                        subtitles = json.load(f)
                else:
                    # 如果源文件不存在，尝试从版本记录加载
                    logger.warning(f"Source file not found: {src_file}, loading from version record")
                    if not version_record:
                        raise ValueError(f"Version {version_id} not found")
                    
                    with open(version_record.file_path, 'r', encoding='utf-8') as f:
                        version_data = json.load(f)
                    subtitles = version_data.get("subtitles", [])
            else:
                # 普通版本，从版本记录加载
                if not version_record:
                    raise ValueError(f"Version {version_id} not found")
                
                # 加载版本数据
                with open(version_record.file_path, 'r', encoding='utf-8') as f:
                    version_data = json.load(f)
                
                subtitles = version_data.get("subtitles", [])
            
            # 先保存当前版本作为备份
            current_subtitles = self._load_current_subtitles(job_id, language, user_id)
            if current_subtitles:
                self.save_modified_version(
                    db=db,
                    job_id=job_id,
                    language=language,
                    subtitles=current_subtitles,
                    user_id=user_id
                )
            
            # 恢复版本到当前工作文件
            self._save_current_working_files(job_id, language, subtitles, user_id)
            
            logger.info(f"Restored to version {version_id} for job {job_id}, language {language}")
            return subtitles
            
        except Exception as e:
            logger.error(f"Error restoring version: {str(e)}")
            raise
    
    def get_version_history(
        self,
        db: Session,
        job_id: int,
        language: str,
        include_auto_saves: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取版本历史
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            include_auto_saves: 是否包含自动保存版本
            
        Returns:
            版本历史列表
        """
        try:
            versions = subtitle_version.get_versions(db=db, job_id=job_id, language=language)
            
            history = []
            for version in versions:
                try:
                    # 读取版本文件获取详细信息
                    with open(version.file_path, 'r', encoding='utf-8') as f:
                        version_data = json.load(f)
                    
                    # 处理不同的文件格式
                    if isinstance(version_data, list):
                        # 纯字幕数组格式（旧格式或原始字幕文件）
                        is_auto_save = False
                        metadata = {}
                        subtitles = version_data
                        timestamp = None
                    else:
                        # 完整版本数据格式
                        is_auto_save = version_data.get("auto_save", False)
                        metadata = version_data.get("metadata", {})
                        subtitles = version_data.get("subtitles", [])
                        timestamp = version_data.get("timestamp")
                    
                    # 根据参数决定是否包含自动保存版本
                    if not include_auto_saves and is_auto_save:
                        continue
                    
                    history.append({
                        "id": version.id,
                        "version_number": version.version_number,
                        "description": version.description,
                        "created_at": version.created_at.isoformat(),
                        "is_current": version.is_current == "true",
                        "is_auto_save": is_auto_save,
                        "file_size": version.file_size,
                        "metadata": metadata,
                        "subtitle_count": len(subtitles),
                        "timestamp": timestamp
                    })
                except Exception as e:
                    logger.warning(f"Error reading version file {version.file_path}: {str(e)}")
                    continue
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return []
    
    def compare_versions(
        self,
        db: Session,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """
        比较两个版本的差异
        
        Args:
            db: 数据库会话
            version_id_1: 版本1 ID
            version_id_2: 版本2 ID
            
        Returns:
            版本差异信息
        """
        try:
            # 获取两个版本
            version1 = subtitle_version.get(db=db, id=int(version_id_1))
            version2 = subtitle_version.get(db=db, id=int(version_id_2))
            
            if not version1 or not version2:
                raise ValueError("One or both versions not found")
            
            # 加载版本数据
            with open(version1.file_path, 'r', encoding='utf-8') as f:
                data1 = json.load(f)
            
            with open(version2.file_path, 'r', encoding='utf-8') as f:
                data2 = json.load(f)
            
            subtitles1 = data1.get("subtitles", [])
            subtitles2 = data2.get("subtitles", [])
            
            # 计算差异
            differences = self._calculate_differences(subtitles1, subtitles2)
            
            return {
                "version1": {
                    "id": version1.id,
                    "version_number": version1.version_number,
                    "description": version1.description,
                    "created_at": version1.created_at.isoformat(),
                    "subtitle_count": len(subtitles1)
                },
                "version2": {
                    "id": version2.id,
                    "version_number": version2.version_number,
                    "description": version2.description,
                    "created_at": version2.created_at.isoformat(),
                    "subtitle_count": len(subtitles2)
                },
                "differences": differences
            }
            
        except Exception as e:
            logger.error(f"Error comparing versions: {str(e)}")
            raise
    
    def cleanup_old_versions(
        self,
        db: Session,
        job_id: int,
        language: str,
        keep_count: int = 50
    ) -> int:
        """
        清理旧版本（保留指定数量的版本）
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            language: 语言
            keep_count: 保留的版本数量
            
        Returns:
            删除的版本数量
        """
        try:
            versions = subtitle_version.get_versions(db=db, job_id=job_id, language=language)
            
            if len(versions) <= keep_count:
                return 0
            
            # 排序版本（保留最新的版本和当前版本）
            versions_to_delete = []
            current_versions = [v for v in versions if v.is_current == "true"]
            other_versions = [v for v in versions if v.is_current != "true"]
            
            # 按创建时间排序，删除最旧的版本
            other_versions.sort(key=lambda x: x.created_at, reverse=True)
            
            if len(other_versions) > keep_count - len(current_versions):
                versions_to_delete = other_versions[keep_count - len(current_versions):]
            
            deleted_count = 0
            for version in versions_to_delete:
                try:
                    # 删除文件
                    if os.path.exists(version.file_path):
                        os.remove(version.file_path)
                    
                    # 删除数据库记录
                    subtitle_version.remove(db=db, id=version.id)
                    deleted_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error deleting version {version.id}: {str(e)}")
            
            logger.info(f"Cleaned up {deleted_count} old versions for job {job_id}, language {language}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {str(e)}")
            return 0
    
    # 私有方法
    def _get_version_dir(self, job_id: int, language: str, user_id: int) -> str:
        """获取版本目录路径"""
        context = self._get_job_context(job_id, user_id)
        # Get the version directory for this language
        version_file_path = self.file_manager.get_file_path(
            context, FileType.VERSION_FILE, language=language, filename="temp.json"
        )
        # Return the directory part
        version_dir = os.path.dirname(version_file_path)
        os.makedirs(version_dir, exist_ok=True)
        return version_dir
    
    def _get_next_version_number(self, db: Session, job_id: int, language: str) -> int:
        """获取下一个版本号"""
        return subtitle_version.get_next_version_number(db=db, job_id=job_id, language=language)
    
    def _calculate_total_duration(self, subtitles: List[Dict[str, Any]]) -> float:
        """计算字幕总时长"""
        if not subtitles:
            return 0.0
        
        total_duration = 0.0
        for subtitle in subtitles:
            start_time = subtitle.get("startTime", 0)
            end_time = subtitle.get("endTime", 0)
            total_duration += max(0, end_time - start_time)
        
        return total_duration
    
    def _cleanup_old_versions(self, db: Session, job_id: int, language: str):
        """清理所有旧版本，只保留源文件和修改版本"""
        try:
            # 获取所有版本
            versions = subtitle_version.get_versions(db=db, job_id=job_id, language=language)
            
            for version in versions:
                # 删除除了源文件(version_number=1)和修改版本(version_number=2)之外的所有版本
                if version.version_number not in [1, 2]:
                    try:
                        # 删除文件
                        if os.path.exists(version.file_path):
                            os.remove(version.file_path)
                        # 删除数据库记录
                        db.delete(version)
                    except Exception as e:
                        logger.warning(f"Failed to delete version {version.id}: {str(e)}")
            
            db.commit()
            logger.info(f"Cleaned up old versions for job {job_id}, language {language}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {str(e)}")
            db.rollback()
    
    def _cleanup_auto_saves(self, db: Session, job_id: int, language: str, keep_count: int = 10):
        """清理自动保存版本"""
        versions = subtitle_version.get_versions(db=db, job_id=job_id, language=language)
        
        auto_save_versions = []
        for version in versions:
            try:
                with open(version.file_path, 'r', encoding='utf-8') as f:
                    version_data = json.load(f)
                if version_data.get("auto_save", False):
                    auto_save_versions.append(version)
            except:
                continue
        
        if len(auto_save_versions) > keep_count:
            auto_save_versions.sort(key=lambda x: x.created_at)
            for version in auto_save_versions[:-keep_count]:
                try:
                    if os.path.exists(version.file_path):
                        os.remove(version.file_path)
                    subtitle_version.remove(db=db, id=version.id)
                except Exception as e:
                    logger.warning(f"Error cleaning up auto-save version {version.id}: {str(e)}")
    
    def _save_current_working_files(self, job_id: int, language: str, subtitles: List[Dict[str, Any]], user_id: int):
        """保存当前工作文件（JSON格式）和修改版本"""
        try:
            context = self._get_job_context(job_id, user_id)
            
            # 1. 保存到主字幕目录（用于兼容性） - Per user request, this is disabled
            # json_file = self.file_manager.get_file_path(context, FileType.SUBTITLE_LANG_JSON, language=language)
            # self.file_manager.write_json(json_file, subtitles)
            
            # 2. 保存到版本目录的modified.json（优先加载）
            modified_file = self.file_manager.get_file_path(context, FileType.MODIFIED_SUBTITLE, language=language)
            
            # 创建修改版本数据结构
            modified_data = {
                "version": "modified",
                "timestamp": datetime.now().isoformat(),
                "language": language,
                "job_id": job_id,
                "user_id": user_id,
                "subtitles": subtitles,
                "metadata": {
                    "total_subtitles": len(subtitles),
                    "last_modified": datetime.now().isoformat()
                }
            }
            
            self.file_manager.write_json(modified_file, modified_data)
            
            # Auto-sync the modified subtitle file to remote storage (S3)
            self.file_manager.auto_sync_file_to_remote(modified_file, logger.info)
            
            logger.info(f"Saved working files for job {job_id}, language {language}: {len(subtitles)} subtitles")
            
        except Exception as e:
            logger.error(f"Error saving current working files: {str(e)}")
            raise
    
    def _create_published_version_file(
        self, 
        job_id: int, 
        language: str, 
        version_number: int, 
        subtitles: List[Dict[str, Any]], 
        description: str,
        user_id: int
    ) -> str:
        """创建发布版本文件"""
        version_dir = self._get_version_dir(job_id, language, user_id)
        os.makedirs(version_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"v{version_number:03d}_published_{timestamp}.json"
        context = self._get_job_context(job_id, user_id)
        file_path = self.file_manager.get_file_path(
            context, FileType.VERSION_FILE, language=language, filename=file_name
        )
        
        publish_data = {
            "version": version_number,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "language": language,
            "job_id": job_id,
            "published": True,
            "subtitles": subtitles,
            "metadata": {
                "total_subtitles": len(subtitles),
                "total_duration": self._calculate_total_duration(subtitles)
            }
        }
        
        self.file_manager.write_json(file_path, publish_data)
        
        # Auto-sync the published version file to remote storage (S3)
        self.file_manager.auto_sync_file_to_remote(file_path, logger.info)
        
        return file_path
    
    def _load_current_subtitles(self, job_id: int, language: str, user_id: int) -> List[Dict[str, Any]]:
        """加载当前字幕文件"""
        context = self._get_job_context(job_id, user_id)
        json_file = self.file_manager.get_file_path(context, FileType.SUBTITLE_JSON, language=language)
        
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return []
    
    def _calculate_differences(
        self, 
        subtitles1: List[Dict[str, Any]], 
        subtitles2: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算两个版本的差异"""
        # 创建字幕ID映射
        map1 = {sub.get("id"): sub for sub in subtitles1}
        map2 = {sub.get("id"): sub for sub in subtitles2}
        
        all_ids = set(map1.keys()) | set(map2.keys())
        
        added = []
        deleted = []
        modified = []
        
        for sub_id in all_ids:
            if sub_id in map1 and sub_id in map2:
                # 存在于两个版本中，检查是否修改
                sub1 = map1[sub_id]
                sub2 = map2[sub_id]
                
                if (sub1.get("text") != sub2.get("text") or 
                    sub1.get("startTime") != sub2.get("startTime") or 
                    sub1.get("endTime") != sub2.get("endTime")):
                    modified.append({
                        "id": sub_id,
                        "old": sub1,
                        "new": sub2
                    })
            elif sub_id in map1:
                # 只存在于版本1中，表示被删除
                deleted.append(map1[sub_id])
            else:
                # 只存在于版本2中，表示新增
                added.append(map2[sub_id])
        
        return {
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "total_changes": len(added) + len(deleted) + len(modified)
        }
    
    def _export_as_srt(self, subtitles: List[Dict[str, Any]]) -> str:
        """导出为SRT格式"""
        srt_content = []
        
        for i, subtitle in enumerate(subtitles, 1):
            start_time = self._format_srt_time(subtitle.get("startTime", 0))
            end_time = self._format_srt_time(subtitle.get("endTime", 0))
            text = subtitle.get("text", "")
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text)
            srt_content.append("")
        
        return '\n'.join(srt_content)
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化时间为SRT格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# 创建服务实例
subtitle_version_service = SubtitleVersionService()