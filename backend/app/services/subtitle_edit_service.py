import os
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.crud.crud_subtitle_edit import subtitle_edit, subtitle_version
from app.models.subtitle_edit import EditType
from app.services.subtitle_version_service import subtitle_version_service
from app.schemas.subtitle_edit import (
    SubtitleEditCreate, SubtitleBatchEditCreate, SubtitleEditResponse,
    SubtitleVersionCreate
)
from app.utils.file_path_manager import FilePathManager, FileType, get_file_path_manager
from app.models.job_context import JobContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class SubtitleEditService:
    """字幕编辑服务"""
    
    def __init__(self):
        self.file_manager = get_file_path_manager()
    
    def process_edit(
        self,
        db: Session,
        *,
        edit_data: SubtitleEditCreate,
        user_id: int
    ) -> SubtitleEditResponse:
        """处理单个字幕编辑操作"""
        try:
            # 创建编辑记录
            edit_record = subtitle_edit.create_edit(
                db=db, edit_data=edit_data, user_id=user_id
            )
            
            # 获取当前字幕数据
            current_subtitles = self._load_subtitle_file(
                job_id=edit_data.job_id,
                language=edit_data.language,
                user_id=user_id
            )
            
            # 应用编辑操作
            updated_subtitles = self._apply_edit(
                subtitles=current_subtitles,
                edit_data=edit_data
            )
            
            # 保存更新后的字幕文件
            self._save_subtitle_file(
                job_id=edit_data.job_id,
                language=edit_data.language,
                subtitles=updated_subtitles,
                user_id=user_id
            )
            
            # 使用版本管理服务自动保存工作版本
            try:
                subtitle_version_service.save_modified_version(
                    db=db,
                    job_id=edit_data.job_id,
                    language=edit_data.language,
                    subtitles=updated_subtitles
                )
            except Exception as e:
                logger.warning(f"Failed to auto-save version: {str(e)}")
            
            # 保留原版本记录逻辑作为备份
            self._create_version_record(
                db=db,
                job_id=edit_data.job_id,
                language=edit_data.language,
                description=f"{edit_data.edit_type.value} edit - {edit_record.id}",
                user_id=user_id
            )
            
            # 返回更新的字幕数据
            if edit_data.edit_type == EditType.CREATE:
                # 对于创建操作，返回新创建的字幕（ID已经被更新）
                updated_subtitle = None
                for subtitle in updated_subtitles:
                    if (subtitle.get("text") == edit_data.new_text and 
                        subtitle.get("startTime") == edit_data.new_start_time and
                        subtitle.get("endTime") == edit_data.new_end_time):
                        updated_subtitle = subtitle
                        break
            else:
                # 对于其他操作，按ID查找
                updated_subtitle = self._find_subtitle_by_id(
                    subtitles=updated_subtitles,
                    subtitle_id=edit_data.subtitle_id
                )
            
            return SubtitleEditResponse(
                success=True,
                message="Subtitle edited successfully",
                subtitle=updated_subtitle
            )
            
        except Exception as e:
            logger.error(f"Error processing subtitle edit: {str(e)}")
            return SubtitleEditResponse(
                success=False,
                message=f"Failed to edit subtitle: {str(e)}",
                errors=[str(e)]
            )
    
    def process_batch_edit(
        self,
        db: Session,
        *,
        batch_data: SubtitleBatchEditCreate,
        user_id: int
    ) -> SubtitleEditResponse:
        """处理批量字幕编辑操作"""
        try:
            # 创建批量编辑记录
            edit_records = subtitle_edit.batch_create_edits(
                db=db, edits_data=batch_data.edits, user_id=user_id
            )
            
            # 获取当前字幕数据
            current_subtitles = self._load_subtitle_file(
                job_id=batch_data.job_id,
                language=batch_data.language,
                user_id=user_id
            )
            
            # 应用所有编辑操作
            updated_subtitles = current_subtitles
            for edit_data in batch_data.edits:
                updated_subtitles = self._apply_edit(
                    subtitles=updated_subtitles,
                    edit_data=edit_data
                )
            
            # 保存更新后的字幕文件
            self._save_subtitle_file(
                job_id=batch_data.job_id,
                language=batch_data.language,
                subtitles=updated_subtitles,
                user_id=user_id
            )
            
            # 使用版本管理服务自动保存工作版本
            try:
                subtitle_version_service.save_modified_version(
                    db=db,
                    job_id=batch_data.job_id,
                    language=batch_data.language,
                    subtitles=updated_subtitles
                )
            except Exception as e:
                logger.warning(f"Failed to auto-save version: {str(e)}")
            
            # 保留原版本记录逻辑作为备份
            self._create_version_record(
                db=db,
                job_id=batch_data.job_id,
                language=batch_data.language,
                description=f"Batch edit - {len(batch_data.edits)} operations",
                user_id=user_id
            )
            
            return SubtitleEditResponse(
                success=True,
                message=f"Successfully processed {len(batch_data.edits)} edits",
                subtitles=updated_subtitles
            )
            
        except Exception as e:
            logger.error(f"Error processing batch subtitle edit: {str(e)}")
            return SubtitleEditResponse(
                success=False,
                message=f"Failed to process batch edit: {str(e)}",
                errors=[str(e)]
            )
    
    def get_edit_history(
        self,
        db: Session,
        *,
        job_id: int,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取编辑历史"""
        edits = subtitle_edit.get_edit_history(
            db=db, job_id=job_id, language=language
        )
        
        return [
            {
                "id": edit.id,
                "subtitle_id": edit.subtitle_id,
                "edit_type": edit.edit_type.value,
                "old_text": edit.old_text,
                "new_text": edit.new_text,
                "old_start_time": edit.old_start_time,
                "new_start_time": edit.new_start_time,
                "old_end_time": edit.old_end_time,
                "new_end_time": edit.new_end_time,
                "metadata": edit.metadata_,
                "created_at": edit.created_at.isoformat(),
                "user_id": edit.user_id
            }
            for edit in edits
        ]
    
    def export_subtitles(
        self,
        job_id: int,
        language: str,
        user_id: int,
        format: str = "srt"
    ) -> str:
        """导出字幕文件"""
        try:
            subtitles = self._load_subtitle_file(job_id=job_id, language=language, user_id=user_id)
            
            if format.lower() == "srt":
                return self._export_as_srt(subtitles)
            elif format.lower() == "vtt":
                return self._export_as_vtt(subtitles)
            elif format.lower() == "ass":
                return self._export_as_ass(subtitles)
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting subtitles: {str(e)}")
            raise
    
    def _load_subtitle_file(self, job_id: int, language: str, user_id: int) -> List[Dict[str, Any]]:
        """
        智能加载字幕文件：
        1. 优先加载修改版本（modified.json）
        2. 没有修改则加载原始版本
        3. 支持用户要求：有修改导出修改版本，无修改导出原始版本
        """
        try:
            # Create job context for file path management
            context = JobContext(user_id=user_id, job_id=job_id, content_hash=None)
            
            # 1. 优先检查修改版本 (versions/language/modified.json)
            modified_file = self.file_manager.get_file_path(
                context, FileType.MODIFIED_SUBTITLE, language=language
            )
            if self.file_manager.exists(modified_file):
                logger.info(f"Loading modified version: {modified_file}")
                try:
                    modified_data = self.file_manager.read_json(modified_file)
                    # 处理版本文件格式
                    if isinstance(modified_data, dict) and "subtitles" in modified_data:
                        logger.info(f"Successfully loaded {len(modified_data['subtitles'])} subtitles from modified version")
                        return modified_data["subtitles"]
                    elif isinstance(modified_data, list):
                        logger.info(f"Successfully loaded {len(modified_data)} subtitles from modified version (array format)")
                        return modified_data
                    else:
                        logger.warning(f"Unexpected modified file format: {modified_file}")
                except Exception as e:
                    logger.error(f"Error reading modified file {modified_file}: {str(e)}")
            
            # 2. 加载原始版本 (subtitles/subtitle_language.json)
            subtitle_file = self.file_manager.get_file_path(
                context, FileType.SUBTITLE_LANG_JSON, language=language
            )
            if self.file_manager.exists(subtitle_file):
                logger.info(f"Loading original version: {subtitle_file}")
                try:
                    original_data = self.file_manager.read_json(subtitle_file)
                    logger.info(f"Successfully loaded {len(original_data)} subtitles from original version")
                    return original_data
                except Exception as e:
                    logger.error(f"Error reading original file {subtitle_file}: {str(e)}")
            
            # 3. 如果JSON文件不存在，尝试加载SRT文件
            srt_file = self.file_manager.get_file_path(
                context, FileType.SUBTITLE_SRT, language=language
            )
            if self.file_manager.exists(srt_file):
                logger.info(f"Loading SRT file: {srt_file}")
                try:
                    srt_data = self._convert_srt_to_json(srt_file)
                    logger.info(f"Successfully converted {len(srt_data)} subtitles from SRT")
                    return srt_data
                except Exception as e:
                    logger.error(f"Error converting SRT file {srt_file}: {str(e)}")
            
            logger.warning(f"No subtitle file found for job {job_id}, language {language}")
            return []
            
        except Exception as e:
            logger.error(f"Error loading subtitle file: {str(e)}")
            return []
    
    def _save_subtitle_file(
        self, 
        job_id: int, 
        language: str, 
        subtitles: List[Dict[str, Any]],
        user_id: int
    ) -> None:
        """保存字幕文件到modified.json（简化版本）"""
        try:
            # Create job context for file path management
            context = JobContext(user_id=user_id, job_id=job_id, content_hash=None)
            
            # 获取修改版本文件路径
            modified_file = self.file_manager.get_file_path(
                context, FileType.MODIFIED_SUBTITLE, language=language
            )
            
            # 确保目录存在
            os.makedirs(os.path.dirname(modified_file), exist_ok=True)
            
            # 直接保存字幕数组，不需要额外的包装
            with open(modified_file, 'w', encoding='utf-8') as f:
                json.dump(subtitles, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved {len(subtitles)} subtitles to modified file: {modified_file}")
            
            # Auto-sync the modified subtitle file to remote storage (S3)
            self.file_manager.auto_sync_file_to_remote(modified_file, logger.info)
                
        except Exception as e:
            logger.error(f"Error saving subtitle file: {str(e)}")
            raise
    
    def _apply_edit(
        self, 
        subtitles: List[Dict[str, Any]], 
        edit_data: SubtitleEditCreate
    ) -> List[Dict[str, Any]]:
        """应用编辑操作"""
        result = subtitles.copy()
        
        if edit_data.edit_type == EditType.CREATE:
            # 创建新字幕 - 生成新的序列ID
            # 找到最大的现有ID，生成下一个ID
            existing_ids = []
            for subtitle in result:
                try:
                    # 尝试解析数字ID
                    id_str = str(subtitle.get("id", "0"))
                    if id_str.isdigit():
                        existing_ids.append(int(id_str))
                    elif id_str.startswith('new-') or id_str.startswith('split-'):
                        # 跳过临时ID
                        continue
                    else:
                        # 尝试从其他格式ID中提取数字
                        import re
                        numbers = re.findall(r'\d+', id_str)
                        if numbers:
                            existing_ids.append(int(numbers[-1]))
                except (ValueError, TypeError):
                    continue
            
            # 生成新ID
            new_id = str(max(existing_ids) + 1) if existing_ids else "1"
            
            new_subtitle = {
                "id": new_id,
                "text": edit_data.new_text,
                "startTime": edit_data.new_start_time,
                "endTime": edit_data.new_end_time
            }
            result.append(new_subtitle)
            # 按时间排序
            result.sort(key=lambda x: x.get("startTime", 0))
            
        elif edit_data.edit_type == EditType.DELETE:
            # 删除字幕
            result = [s for s in result if s.get("id") != edit_data.subtitle_id]
            
        elif edit_data.edit_type == EditType.TEXT:
            # 更新文本
            for subtitle in result:
                if subtitle.get("id") == edit_data.subtitle_id:
                    subtitle["text"] = edit_data.new_text
                    break
                    
        elif edit_data.edit_type == EditType.TIMING:
            # 更新时间
            for subtitle in result:
                if subtitle.get("id") == edit_data.subtitle_id:
                    if edit_data.new_start_time is not None:
                        subtitle["startTime"] = edit_data.new_start_time
                    if edit_data.new_end_time is not None:
                        subtitle["endTime"] = edit_data.new_end_time
                    break
                    
        elif edit_data.edit_type == EditType.SPLIT:
            # 分割字幕
            self._apply_split_edit(result, edit_data)
            
        elif edit_data.edit_type == EditType.MERGE:
            # 合并字幕
            self._apply_merge_edit(result, edit_data)
        
        return result
    
    def _apply_split_edit(
        self, 
        subtitles: List[Dict[str, Any]], 
        edit_data: SubtitleEditCreate
    ) -> None:
        """应用分割操作"""
        metadata = edit_data.metadata or {}
        
        # 更新原字幕
        for subtitle in subtitles:
            if subtitle.get("id") == edit_data.subtitle_id:
                subtitle["text"] = edit_data.new_text
                subtitle["endTime"] = edit_data.new_end_time
                break
        
        # 创建新的第二部分字幕
        second_subtitle = {
            "id": f"{edit_data.subtitle_id}_split",
            "text": metadata.get("secondText", ""),
            "startTime": metadata.get("secondStartTime", edit_data.new_end_time),
            "endTime": metadata.get("secondEndTime", edit_data.old_end_time)
        }
        subtitles.append(second_subtitle)
        
        # 重新排序
        subtitles.sort(key=lambda x: x.get("startTime", 0))
    
    def _apply_merge_edit(
        self, 
        subtitles: List[Dict[str, Any]], 
        edit_data: SubtitleEditCreate
    ) -> None:
        """应用合并操作"""
        metadata = edit_data.metadata or {}
        next_subtitle_id = metadata.get("nextSubtitleId")
        
        # 更新当前字幕
        for subtitle in subtitles:
            if subtitle.get("id") == edit_data.subtitle_id:
                subtitle["text"] = edit_data.new_text
                subtitle["endTime"] = edit_data.new_end_time
                break
        
        # 删除下一个字幕
        if next_subtitle_id:
            subtitles[:] = [s for s in subtitles if s.get("id") != next_subtitle_id]
    
    def _find_subtitle_by_id(
        self, 
        subtitles: List[Dict[str, Any]], 
        subtitle_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据ID查找字幕"""
        for subtitle in subtitles:
            if subtitle.get("id") == subtitle_id:
                return subtitle
        return None
    
    def _create_version_record(
        self,
        db: Session,
        job_id: int,
        language: str,
        description: str,
        user_id: int
    ) -> None:
        """创建版本记录"""
        try:
            version_number = subtitle_version.get_next_version_number(
                db=db, job_id=job_id, language=language
            )
            
            # 使用file_path_manager获取实际文件路径
            context = JobContext(user_id=user_id, job_id=job_id, content_hash=None)
            file_path = self.file_manager.get_file_path(
                context, FileType.SUBTITLE_JSON, language=language
            )
            
            version_data = SubtitleVersionCreate(
                job_id=job_id,
                language=language,
                version_number=version_number,
                file_path=file_path,
                file_format="json",
                description=description,
                is_current="true"
            )
            
            subtitle_version.create_version(db=db, version_data=version_data)
            
        except Exception as e:
            logger.error(f"Error creating version record: {str(e)}")
    
    def _convert_srt_to_json(self, srt_file_path: str) -> List[Dict[str, Any]]:
        """将SRT文件转换为JSON格式"""
        subtitles = []
        try:
            content = self.file_manager.read_text(srt_file_path)
            
            # 简单的SRT解析（这里可以使用更复杂的SRT解析库）
            blocks = content.strip().split('\n\n')
            
            for i, block in enumerate(blocks):
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # 时间行
                    time_line = lines[1]
                    if ' --> ' in time_line:
                        start_time_str, end_time_str = time_line.split(' --> ')
                        start_time = self._parse_srt_time(start_time_str.strip())
                        end_time = self._parse_srt_time(end_time_str.strip())
                        
                        # 文本行
                        text = '\n'.join(lines[2:])
                        
                        subtitles.append({
                            "id": str(i + 1),
                            "text": text,
                            "startTime": start_time,
                            "endTime": end_time
                        })
            
        except Exception as e:
            logger.error(f"Error converting SRT to JSON: {str(e)}")
        
        return subtitles
    
    def _parse_srt_time(self, time_str: str) -> float:
        """解析SRT时间格式为秒数"""
        try:
            # 格式: 00:01:30,500
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0.0
    
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
    
    def _export_as_vtt(self, subtitles: List[Dict[str, Any]]) -> str:
        """导出为VTT格式"""
        vtt_content = ["WEBVTT", ""]
        
        for subtitle in subtitles:
            start_time = self._format_vtt_time(subtitle.get("startTime", 0))
            end_time = self._format_vtt_time(subtitle.get("endTime", 0))
            text = subtitle.get("text", "")
            
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(text)
            vtt_content.append("")
        
        return '\n'.join(vtt_content)
    
    def _format_vtt_time(self, seconds: float) -> str:
        """格式化时间为VTT格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    def _export_as_ass(self, subtitles: List[Dict[str, Any]]) -> str:
        """导出为ASS格式"""
        ass_header = """[Script Info]
Title: Exported Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        ass_content = [ass_header.strip()]
        
        for subtitle in subtitles:
            start_time = self._format_ass_time(subtitle.get("startTime", 0))
            end_time = self._format_ass_time(subtitle.get("endTime", 0))
            text = subtitle.get("text", "").replace('\n', '\\N')
            
            ass_content.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")
        
        return '\n'.join(ass_content)
    
    def _format_ass_time(self, seconds: float) -> str:
        """格式化时间为ASS格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


# 创建服务实例
subtitle_edit_service = SubtitleEditService()