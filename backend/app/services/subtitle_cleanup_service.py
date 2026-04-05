import os
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.crud_subtitle_edit import subtitle_version
from app.services.subtitle_version_service import subtitle_version_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class SubtitleCleanupService:
    """字幕清理和性能优化服务"""
    
    def __init__(self):
        self.cleanup_rules = {
            'auto_save_retention_days': 7,      # 自动保存版本保留7天
            'manual_save_retention_days': 30,   # 手动保存版本保留30天
            'max_versions_per_job': 100,        # 每个作业最多保留100个版本
            'cleanup_batch_size': 50,           # 批量清理大小
            'file_size_threshold_mb': 10,       # 文件大小阈值（MB）
        }
    
    def cleanup_old_versions(
        self,
        db: Session,
        days_threshold: int = 30
    ) -> Dict[str, Any]:
        """
        清理过期版本
        
        Args:
            db: 数据库会话
            days_threshold: 清理阈值天数
            
        Returns:
            清理统计信息
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            logger.info(f"开始清理 {cutoff_date} 之前的版本")
            
            # 获取过期版本
            expired_versions = subtitle_version.get_expired_versions(
                db=db,
                cutoff_date=cutoff_date
            )
            
            stats = {
                'total_found': len(expired_versions),
                'deleted_count': 0,
                'failed_count': 0,
                'freed_space_mb': 0,
                'errors': []
            }
            
            for version in expired_versions:
                try:
                    # 检查文件是否为当前版本
                    if version.is_current == "true":
                        continue
                    
                    # 获取文件大小
                    file_size = 0
                    if os.path.exists(version.file_path):
                        file_size = os.path.getsize(version.file_path)
                        stats['freed_space_mb'] += file_size / (1024 * 1024)
                        
                        # 删除文件
                        os.remove(version.file_path)
                    
                    # 删除数据库记录
                    subtitle_version.remove(db=db, id=version.id)
                    stats['deleted_count'] += 1
                    
                    logger.debug(f"删除版本 {version.id}: {version.file_path}")
                    
                except Exception as e:
                    stats['failed_count'] += 1
                    error_msg = f"删除版本 {version.id} 失败: {str(e)}"
                    stats['errors'].append(error_msg)
                    logger.warning(error_msg)
            
            logger.info(f"清理完成: 删除 {stats['deleted_count']} 个版本，释放 {stats['freed_space_mb']:.2f} MB")
            return stats
            
        except Exception as e:
            logger.error(f"清理过期版本失败: {str(e)}")
            raise
    
    def cleanup_auto_save_versions(
        self,
        db: Session,
        job_id: int = None
    ) -> Dict[str, Any]:
        """
        清理自动保存版本（保留最近的几个）
        
        Args:
            db: 数据库会话
            job_id: 作业ID，如果为None则清理所有作业
            
        Returns:
            清理统计信息
        """
        try:
            retention_days = self.cleanup_rules['auto_save_retention_days']
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # 获取旧的自动保存版本
            auto_save_versions = subtitle_version.get_auto_save_versions(
                db=db,
                job_id=job_id,
                cutoff_date=cutoff_date
            )
            
            stats = {
                'total_found': len(auto_save_versions),
                'deleted_count': 0,
                'failed_count': 0,
                'freed_space_mb': 0,
                'errors': []
            }
            
            # 按作业和语言分组，保留最新的几个自动保存版本
            grouped_versions = {}
            for version in auto_save_versions:
                key = f"{version.job_id}_{version.language}"
                if key not in grouped_versions:
                    grouped_versions[key] = []
                grouped_versions[key].append(version)
            
            for group_key, versions in grouped_versions.items():
                # 按创建时间排序，保留最新的5个
                versions.sort(key=lambda x: x.created_at, reverse=True)
                versions_to_delete = versions[5:]  # 删除除最新5个之外的所有版本
                
                for version in versions_to_delete:
                    try:
                        # 获取文件大小
                        file_size = 0
                        if os.path.exists(version.file_path):
                            file_size = os.path.getsize(version.file_path)
                            stats['freed_space_mb'] += file_size / (1024 * 1024)
                            
                            # 删除文件
                            os.remove(version.file_path)
                        
                        # 删除数据库记录
                        subtitle_version.remove(db=db, id=version.id)
                        stats['deleted_count'] += 1
                        
                    except Exception as e:
                        stats['failed_count'] += 1
                        error_msg = f"删除自动保存版本 {version.id} 失败: {str(e)}"
                        stats['errors'].append(error_msg)
                        logger.warning(error_msg)
            
            logger.info(f"自动保存清理完成: 删除 {stats['deleted_count']} 个版本")
            return stats
            
        except Exception as e:
            logger.error(f"清理自动保存版本失败: {str(e)}")
            raise
    
    def optimize_version_storage(
        self,
        db: Session,
        job_id: int
    ) -> Dict[str, Any]:
        """
        优化版本存储（压缩、去重等）
        
        Args:
            db: 数据库会话
            job_id: 作业ID
            
        Returns:
            优化统计信息
        """
        try:
            stats = {
                'checked_versions': 0,
                'duplicates_found': 0,
                'duplicates_removed': 0,
                'space_saved_mb': 0,
                'errors': []
            }
            
            # 获取该作业的所有版本
            all_versions = subtitle_version.get_versions_by_job(db=db, job_id=job_id)
            stats['checked_versions'] = len(all_versions)
            
            # 按语言分组检查重复内容
            language_groups = {}
            for version in all_versions:
                if version.language not in language_groups:
                    language_groups[version.language] = []
                language_groups[version.language].append(version)
            
            for language, versions in language_groups.items():
                # 检查内容重复的版本
                content_hashes = {}
                for version in versions:
                    try:
                        if not os.path.exists(version.file_path):
                            continue
                            
                        # 读取文件内容并计算哈希
                        with open(version.file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        import hashlib
                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        
                        if content_hash in content_hashes:
                            # 发现重复内容
                            stats['duplicates_found'] += 1
                            original_version = content_hashes[content_hash]
                            
                            # 保留较新的版本，删除较旧的版本
                            if version.created_at > original_version.created_at:
                                version_to_delete = original_version
                                content_hashes[content_hash] = version
                            else:
                                version_to_delete = version
                            
                            # 删除重复版本（但保留当前版本）
                            if version_to_delete.is_current != "true":
                                try:
                                    file_size = os.path.getsize(version_to_delete.file_path)
                                    os.remove(version_to_delete.file_path)
                                    subtitle_version.remove(db=db, id=version_to_delete.id)
                                    
                                    stats['duplicates_removed'] += 1
                                    stats['space_saved_mb'] += file_size / (1024 * 1024)
                                    
                                except Exception as e:
                                    error_msg = f"删除重复版本 {version_to_delete.id} 失败: {str(e)}"
                                    stats['errors'].append(error_msg)
                        else:
                            content_hashes[content_hash] = version
                            
                    except Exception as e:
                        error_msg = f"处理版本 {version.id} 时出错: {str(e)}"
                        stats['errors'].append(error_msg)
                        logger.warning(error_msg)
            
            logger.info(f"存储优化完成: 检查 {stats['checked_versions']} 个版本，删除 {stats['duplicates_removed']} 个重复版本")
            return stats
            
        except Exception as e:
            logger.error(f"优化版本存储失败: {str(e)}")
            raise
    
    def get_storage_statistics(
        self,
        db: Session,
        job_id: int = None
    ) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Args:
            db: 数据库会话
            job_id: 作业ID，如果为None则统计所有作业
            
        Returns:
            存储统计信息
        """
        try:
            if job_id:
                versions = subtitle_version.get_versions_by_job(db=db, job_id=job_id)
            else:
                versions = subtitle_version.get_all_versions(db=db)
            
            stats = {
                'total_versions': len(versions),
                'auto_save_count': 0,
                'manual_save_count': 0,
                'current_versions': 0,
                'total_size_mb': 0,
                'average_size_kb': 0,
                'language_breakdown': {},
                'age_breakdown': {
                    'less_than_1_day': 0,
                    'less_than_1_week': 0,
                    'less_than_1_month': 0,
                    'older_than_1_month': 0
                }
            }
            
            now = datetime.now()
            total_size_bytes = 0
            
            for version in versions:
                # 统计版本类型
                if version.is_current == "true":
                    stats['current_versions'] += 1
                
                # 读取文件判断是否为自动保存
                try:
                    if os.path.exists(version.file_path):
                        file_size = os.path.getsize(version.file_path)
                        total_size_bytes += file_size
                        
                        with open(version.file_path, 'r', encoding='utf-8') as f:
                            import json
                            data = json.load(f)
                            if data.get('auto_save', False):
                                stats['auto_save_count'] += 1
                            else:
                                stats['manual_save_count'] += 1
                except:
                    # 如果无法读取文件，根据描述判断
                    if 'auto' in version.description.lower() or '自动' in version.description:
                        stats['auto_save_count'] += 1
                    else:
                        stats['manual_save_count'] += 1
                
                # 语言统计
                if version.language not in stats['language_breakdown']:
                    stats['language_breakdown'][version.language] = 0
                stats['language_breakdown'][version.language] += 1
                
                # 年龄统计
                age_delta = now - version.created_at
                if age_delta.days < 1:
                    stats['age_breakdown']['less_than_1_day'] += 1
                elif age_delta.days < 7:
                    stats['age_breakdown']['less_than_1_week'] += 1
                elif age_delta.days < 30:
                    stats['age_breakdown']['less_than_1_month'] += 1
                else:
                    stats['age_breakdown']['older_than_1_month'] += 1
            
            stats['total_size_mb'] = total_size_bytes / (1024 * 1024)
            if stats['total_versions'] > 0:
                stats['average_size_kb'] = total_size_bytes / (1024 * stats['total_versions'])
            
            return stats
            
        except Exception as e:
            logger.error(f"获取存储统计失败: {str(e)}")
            raise
    
    def scheduled_cleanup(self, db: Session) -> Dict[str, Any]:
        """
        定期清理任务
        
        Args:
            db: 数据库会话
            
        Returns:
            清理统计信息
        """
        try:
            logger.info("开始执行定期清理任务")
            
            overall_stats = {
                'old_versions_cleanup': {},
                'auto_save_cleanup': {},
                'total_freed_space_mb': 0,
                'execution_time_seconds': 0
            }
            
            start_time = datetime.now()
            
            # 1. 清理过期版本
            old_versions_stats = self.cleanup_old_versions(
                db=db,
                days_threshold=self.cleanup_rules['manual_save_retention_days']
            )
            overall_stats['old_versions_cleanup'] = old_versions_stats
            overall_stats['total_freed_space_mb'] += old_versions_stats['freed_space_mb']
            
            # 2. 清理旧的自动保存版本
            auto_save_stats = self.cleanup_auto_save_versions(db=db)
            overall_stats['auto_save_cleanup'] = auto_save_stats
            overall_stats['total_freed_space_mb'] += auto_save_stats['freed_space_mb']
            
            end_time = datetime.now()
            overall_stats['execution_time_seconds'] = (end_time - start_time).total_seconds()
            
            logger.info(f"定期清理完成，总共释放 {overall_stats['total_freed_space_mb']:.2f} MB")
            return overall_stats
            
        except Exception as e:
            logger.error(f"定期清理任务失败: {str(e)}")
            raise


# 创建服务实例
subtitle_cleanup_service = SubtitleCleanupService()