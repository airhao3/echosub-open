import { apiClient } from './apiClient';
import { Subtitle } from '../../utils/subtitleUtils';

export interface SubtitleEdit {
  job_id: number;
  language: string;
  subtitle_id: string;
  old_text?: string;
  new_text?: string;
  old_start_time?: number;
  new_start_time?: number;
  old_end_time?: number;
  new_end_time?: number;
  edit_type: 'TEXT' | 'TIMING' | 'SPLIT' | 'MERGE' | 'CREATE' | 'DELETE';
  metadata?: {
    [key: string]: any;
  };
}

export interface SubtitleBatchEdit {
  job_id: number;
  language: string;
  edits: SubtitleEdit[];
}

export interface SubtitleSaveResponse {
  success: boolean;
  message: string;
  updatedSubtitle?: Subtitle | Subtitle[];
  errors?: string[];
}

interface ApiResponse {
  success?: boolean;
  subtitle?: Subtitle;
  subtitles?: Subtitle[];
  edits?: SubtitleEdit[];
  message?: string;
  errors?: string[];
}

/**
 * 字幕编辑服务 - 处理字幕的增删改查操作
 */
export const subtitleEditService = {
  /**
   * 保存单个字幕的修改
   * @param edit 字幕编辑对象
   * @returns 保存结果
   */
  saveSubtitleEdit: async (edit: SubtitleEdit): Promise<SubtitleSaveResponse> => {
    try {
      console.log('📡 发送字幕编辑请求:', edit);
      
      const response = await apiClient.post<ApiResponse>('/api/v1/subtitles/edit', edit);
      
      console.log('📩 字幕编辑API响应:', response.data);
      
      // 检查后端响应中的success字段
      if (response.data.success) {
        console.log('✅ 字幕编辑成功:', response.data.message);
        return {
          success: true,
          message: response.data.message || 'Subtitle saved successfully',
          updatedSubtitle: response.data.subtitle,
        };
      } else {
        console.log('❌ 字幕编辑失败:', response.data.message);
        return {
          success: false,
          message: response.data.message || 'Failed to save subtitle',
          errors: response.data.errors || [],
        };
      }
    } catch (error: any) {
      console.error('❌ 字幕编辑请求失败:', error);
      console.error('错误详情:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        message: error.message
      });
      
      return {
        success: false,
        message: error.response?.data?.message || 'Failed to save subtitle',
        errors: error.response?.data?.errors || [error.message],
      };
    }
  },

  /**
   * 批量保存字幕修改
   * @param batchEdit 批量编辑对象
   * @returns 保存结果
   */
  saveBatchSubtitleEdits: async (batchEdit: SubtitleBatchEdit): Promise<SubtitleSaveResponse> => {
    try {
      console.log('Saving batch subtitle edits:', batchEdit);
      
      const response = await apiClient.post<ApiResponse>('/api/v1/subtitles/batch-edit', batchEdit);
      
      return {
        success: true,
        message: `Successfully saved ${batchEdit.edits.length} subtitle edits`,
        updatedSubtitle: response.data.subtitles,
      };
    } catch (error: any) {
      console.error('Failed to save batch subtitle edits:', error);
      
      return {
        success: false,
        message: error.response?.data?.message || 'Failed to save subtitles',
        errors: error.response?.data?.errors || [error.message],
      };
    }
  },

  /**
   * 创建新字幕
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitle 新字幕
   * @returns 创建结果
   */
  createSubtitle: async (jobId: number, language: string, subtitle: Subtitle): Promise<SubtitleSaveResponse> => {
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: subtitle.id, // 使用客户端生成的临时ID
      new_text: subtitle.text,
      new_start_time: subtitle.startTime,
      new_end_time: subtitle.endTime,
      edit_type: 'CREATE',
    };

    return subtitleEditService.saveSubtitleEdit(edit);
  },

  /**
   * 更新字幕文本
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitleId 字幕ID
   * @param oldText 旧文本
   * @param newText 新文本
   * @returns 保存结果
   */
  updateSubtitleText: async (
    jobId: number, 
    language: string, 
    subtitleId: string, 
    oldText: string, 
    newText: string
  ): Promise<SubtitleSaveResponse> => {
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: subtitleId,
      old_text: oldText,
      new_text: newText,
      edit_type: 'TEXT',
    };

    return subtitleEditService.saveSubtitleEdit(edit);
  },

  /**
   * 更新字幕时间
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitleId 字幕ID
   * @param oldStartTime 旧开始时间
   * @param newStartTime 新开始时间
   * @param oldEndTime 旧结束时间
   * @param newEndTime 新结束时间
   * @returns 保存结果
   */
  updateSubtitleTiming: async (
    jobId: number,
    language: string,
    subtitleId: string,
    oldStartTime: number,
    newStartTime: number,
    oldEndTime: number,
    newEndTime: number
  ): Promise<SubtitleSaveResponse> => {
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: subtitleId,
      old_start_time: oldStartTime,
      new_start_time: newStartTime,
      old_end_time: oldEndTime,
      new_end_time: newEndTime,
      edit_type: 'TIMING',
    };

    return subtitleEditService.saveSubtitleEdit(edit);
  },

  /**
   * 分割字幕
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitleId 原字幕ID
   * @param splitPoint 分割位置
   * @param splitTime 分割时间
   * @param firstText 第一部分文本
   * @param secondText 第二部分文本
   * @param originalStartTime 原开始时间
   * @param originalEndTime 原结束时间
   * @returns 保存结果
   */
  splitSubtitle: async (
    jobId: number,
    language: string,
    subtitleId: string,
    splitPoint: number,
    splitTime: number,
    firstText: string,
    secondText: string,
    originalStartTime: number,
    originalEndTime: number
  ): Promise<SubtitleSaveResponse> => {
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: subtitleId,
      old_text: firstText + secondText, // 原始完整文本
      new_text: firstText, // 第一部分文本
      old_start_time: originalStartTime,
      new_start_time: originalStartTime,
      old_end_time: originalEndTime,
      new_end_time: splitTime,
      edit_type: 'SPLIT',
      metadata: {
        splitPoint,
        splitTime,
        secondText,
        secondStartTime: splitTime,
        secondEndTime: originalEndTime,
      },
    };

    return subtitleEditService.saveSubtitleEdit(edit);
  },

  /**
   * 合并字幕
   * @param jobId 作业ID
   * @param language 语言
   * @param currentSubtitleId 当前字幕ID
   * @param nextSubtitleId 下一个字幕ID
   * @param mergedText 合并后的文本
   * @param newEndTime 合并后的结束时间
   * @param currentStartTime 当前字幕开始时间
   * @returns 合并结果
   */
  mergeSubtitles: async (
    jobId: number,
    language: string,
    currentSubtitleId: string,
    nextSubtitleId: string,
    mergedText: string,
    newEndTime: number,
    currentStartTime: number
  ): Promise<SubtitleSaveResponse> => {
    console.log('🔗 subtitleEditService.mergeSubtitles 调用参数:', {
      jobId,
      language,
      currentSubtitleId,
      nextSubtitleId,
      mergedText,
      newEndTime,
      currentStartTime
    });
    
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: currentSubtitleId,
      new_text: mergedText,
      new_end_time: newEndTime,
      new_start_time: currentStartTime,
      edit_type: 'MERGE',
      metadata: {
        nextSubtitleId,
        mergedText,
        newEndTime,
      },
    };

    console.log('🔗 构建的编辑对象:', edit);
    const result = await subtitleEditService.saveSubtitleEdit(edit);
    console.log('🔗 合并API返回结果:', result);
    return result;
  },

  /**
   * 删除字幕
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitleId 字幕ID
   * @returns 删除结果
   */
  deleteSubtitle: async (jobId: number, language: string, subtitleId: string): Promise<SubtitleSaveResponse> => {
    const edit: SubtitleEdit = {
      job_id: jobId,
      language,
      subtitle_id: subtitleId,
      edit_type: 'DELETE',
    };

    return subtitleEditService.saveSubtitleEdit(edit);
  },

  /**
   * 获取字幕编辑历史
   * @param jobId 作业ID
   * @param language 语言
   * @returns 编辑历史
   */
  getEditHistory: async (jobId: number, language: string): Promise<SubtitleEdit[]> => {
    try {
      const response = await apiClient.get<ApiResponse>(`/api/v1/subtitles/edit-history/${jobId}`, {
        params: { language },
      });
      
      return response.data.edits || [];
    } catch (error) {
      console.error('Failed to get edit history:', error);
      return [];
    }
  },

  /**
   * 撤销字幕编辑
   * @param jobId 作业ID
   * @param language 语言
   * @param editId 编辑ID
   * @returns 撤销结果
   */
  undoSubtitleEdit: async (jobId: number, language: string, editId: string): Promise<SubtitleSaveResponse> => {
    try {
      const response = await apiClient.post<ApiResponse>(`/api/v1/subtitles/undo-edit/${editId}`, {
        jobId,
        language,
      });
      
      return {
        success: true,
        message: 'Edit undone successfully',
        updatedSubtitle: response.data.subtitle,
      };
    } catch (error: any) {
      console.error('Failed to undo edit:', error);
      
      return {
        success: false,
        message: error.response?.data?.message || 'Failed to undo edit',
        errors: error.response?.data?.errors || [error.message],
      };
    }
  },

  /**
   * 导出编辑后的字幕文件
   * @param jobId 作业ID
   * @param language 语言
   * @param format 导出格式 (srt, vtt, ass)
   * @returns 文件下载URL
   */
  exportEditedSubtitles: async (jobId: number, language: string, format: 'srt' | 'vtt' | 'ass' = 'srt'): Promise<string> => {
    try {
      const response = await apiClient.get(`/api/v1/subtitles/export/${jobId}`, {
        params: { language, format },
        responseType: 'blob',
      });
      
      // 创建下载链接
      const blob = new Blob([response.data as BlobPart], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      
      return url;
    } catch (error) {
      console.error('Failed to export subtitles:', error);
      throw error;
    }
  },
};

export default subtitleEditService;