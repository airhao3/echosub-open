import { apiClient } from './apiClient';
import { Subtitle } from '../../utils/subtitleUtils';

export interface SubtitleVersion {
  id: string;
  version_number: number;
  description: string;
  created_at: string;
  is_current: boolean;
  is_auto_save: boolean;
  file_size: number;
  metadata: {
    total_subtitles: number;
    total_duration: number;
    edit_count?: number;
  };
  subtitle_count: number;
  timestamp: string;
}

export interface VersionComparison {
  version1: {
    id: string;
    version_number: number;
    description: string;
    created_at: string;
    subtitle_count: number;
  };
  version2: {
    id: string;
    version_number: number;
    description: string;
    created_at: string;
    subtitle_count: number;
  };
  differences: {
    added: Subtitle[];
    deleted: Subtitle[];
    modified: Array<{
      id: string;
      old: Subtitle;
      new: Subtitle;
    }>;
    total_changes: number;
  };
}

export interface SaveVersionResponse {
  success: boolean;
  version_id: string;
  message: string;
  timestamp?: string;
}

export interface RestoreVersionResponse {
  success: boolean;
  subtitles: Subtitle[];
  message: string;
}

export interface PublishVersionResponse {
  success: boolean;
  published_version: {
    id: string;
    version_number: number;
    description: string;
    created_at: string;
  };
  message: string;
}

/**
 * 字幕版本管理服务
 */
export const subtitleVersionService = {
  /**
   * 获取版本历史
   * @param jobId 作业ID
   * @param language 语言
   * @param includeAutoSaves 是否包含自动保存版本
   * @returns 版本历史列表
   */
  getVersionHistory: async (
    jobId: number,
    language: string,
    includeAutoSaves: boolean = true
  ): Promise<SubtitleVersion[]> => {
    try {
      const response = await apiClient.get<{ history: SubtitleVersion[] }>(
        `/api/v1/subtitles/version-history/${jobId}`,
        {
          params: { language, include_auto_saves: includeAutoSaves },
        }
      );
      
      return response.data.history || [];
    } catch (error) {
      console.error('获取版本历史失败:', error);
      return [];
    }
  },

  /**
   * 保存修改版本（简化版本）
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitles 字幕数据
   * @param description 版本描述（保持兼容性，实际不使用）
   * @param autoSave 是否为自动保存（保持兼容性，实际不使用）
   * @returns 保存结果
   */
  saveWorkingVersion: async (
    jobId: number,
    language: string,
    subtitles: Subtitle[],
    description: string = '手动保存版本',
    autoSave: boolean = false
  ): Promise<SaveVersionResponse> => {
    try {
      console.log('💾 保存修改版本:', {
        jobId,
        language,
        subtitleCount: subtitles.length
      });

      const response = await apiClient.post<SaveVersionResponse>(
        `/api/v1/preview/subtitles/save-modified/${jobId}`,
        subtitles,
        {
          params: {
            language
          },
        }
      );

      console.log('✅ 修改版本保存成功:', response.data);
      return {
        success: response.data.success,
        version_id: response.data.timestamp || 'modified',
        message: response.data.message
      };
    } catch (error: any) {
      console.error('❌ 修改版本保存失败:', error);
      throw new Error(
        error.response?.data?.detail || '保存修改版本失败'
      );
    }
  },

  /**
   * 发布版本
   * @param jobId 作业ID
   * @param language 语言
   * @param versionId 要发布的版本ID（可选，默认最新版本）
   * @param description 发布描述
   * @returns 发布结果
   */
  publishVersion: async (
    jobId: number,
    language: string,
    versionId?: string,
    description: string = '正式发布版本'
  ): Promise<PublishVersionResponse> => {
    try {
      console.log('🚀 发布版本:', {
        jobId,
        language,
        versionId,
        description
      });

      const response = await apiClient.post<PublishVersionResponse>(
        `/api/v1/subtitles/publish-version/${jobId}`,
        {},
        {
          params: {
            language,
            version_id: versionId,
            description,
          },
        }
      );

      console.log('✅ 版本发布成功:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ 版本发布失败:', error);
      throw new Error(
        error.response?.data?.detail || '发布版本失败'
      );
    }
  },

  /**
   * 恢复到指定版本
   * @param jobId 作业ID
   * @param language 语言
   * @param versionId 版本ID
   * @returns 恢复结果和字幕数据
   */
  restoreVersion: async (
    jobId: number,
    language: string,
    versionId: string
  ): Promise<RestoreVersionResponse> => {
    try {
      console.log('🔄 恢复版本:', {
        jobId,
        language,
        versionId
      });

      const response = await apiClient.post<RestoreVersionResponse>(
        `/api/v1/subtitles/restore-version/${jobId}`,
        {},
        {
          params: {
            language,
            version_id: versionId,
          },
        }
      );

      console.log('✅ 版本恢复成功:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ 版本恢复失败:', error);
      throw new Error(
        error.response?.data?.detail || '恢复版本失败'
      );
    }
  },

  /**
   * 比较两个版本
   * @param versionId1 版本1 ID
   * @param versionId2 版本2 ID
   * @returns 版本比较结果
   */
  compareVersions: async (
    versionId1: string,
    versionId2: string
  ): Promise<VersionComparison> => {
    try {
      console.log('🔍 比较版本:', { versionId1, versionId2 });

      const response = await apiClient.get<{ comparison: VersionComparison }>(
        '/api/v1/subtitles/compare-versions',
        {
          params: {
            version_id_1: versionId1,
            version_id_2: versionId2,
          },
        }
      );

      console.log('✅ 版本比较完成:', response.data.comparison);
      return response.data.comparison;
    } catch (error: any) {
      console.error('❌ 版本比较失败:', error);
      throw new Error(
        error.response?.data?.detail || '比较版本失败'
      );
    }
  },

  /**
   * 清理旧版本
   * @param jobId 作业ID
   * @param language 语言
   * @param keepCount 保留版本数量
   * @returns 清理结果
   */
  cleanupOldVersions: async (
    jobId: number,
    language: string,
    keepCount: number = 50
  ): Promise<{ success: boolean; deleted_count: number; message: string }> => {
    try {
      console.log('🧹 清理旧版本:', {
        jobId,
        language,
        keepCount
      });

      const response = await apiClient.delete<{
        success: boolean;
        deleted_count: number;
        message: string;
      }>(`/api/v1/subtitles/cleanup-versions/${jobId}`, {
        params: {
          language,
          keep_count: keepCount,
        },
      });

      console.log('✅ 版本清理完成:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ 版本清理失败:', error);
      throw new Error(
        error.response?.data?.detail || '清理版本失败'
      );
    }
  },

  /**
   * 自动保存当前编辑状态
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitles 字幕数据
   * @returns 自动保存结果
   */
  autoSave: async (
    jobId: number,
    language: string,
    subtitles: Subtitle[]
  ): Promise<void> => {
    try {
      // 静默自动保存，不抛出错误
      await subtitleVersionService.saveWorkingVersion(
        jobId,
        language,
        subtitles,
        '自动保存',
        true
      );
    } catch (error) {
      // 自动保存失败不影响用户操作，只记录日志
      console.warn('自动保存失败:', error);
    }
  },

  /**
   * 格式化版本创建时间
   * @param timestamp ISO时间戳
   * @returns 格式化后的时间字符串
   */
  formatVersionTime: (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffMins < 1) {
        return '刚刚';
      } else if (diffMins < 60) {
        return `${diffMins}分钟前`;
      } else if (diffHours < 24) {
        return `${diffHours}小时前`;
      } else if (diffDays < 7) {
        return `${diffDays}天前`;
      } else {
        return date.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
      }
    } catch (error) {
      return timestamp;
    }
  },

  /**
   * 获取版本大小描述
   * @param fileSize 文件大小（字节）
   * @returns 格式化后的大小字符串
   */
  formatFileSize: (fileSize: number): string => {
    if (fileSize < 1024) {
      return `${fileSize} B`;
    } else if (fileSize < 1024 * 1024) {
      return `${(fileSize / 1024).toFixed(1)} KB`;
    } else {
      return `${(fileSize / (1024 * 1024)).toFixed(1)} MB`;
    }
  },

  /**
   * 获取存储统计信息
   * @param jobId 作业ID（可选）
   * @returns 存储统计信息
   */
  getStorageStats: async (jobId?: number): Promise<any> => {
    try {
      const response = await apiClient.get<{ stats: any }>('/api/v1/subtitles/storage-stats', {
        params: jobId ? { job_id: jobId } : {},
      });
      return response.data.stats;
    } catch (error) {
      console.error('获取存储统计失败:', error);
      throw error;
    }
  },

  /**
   * 清理存储空间
   * @param cleanupType 清理类型
   * @param jobId 作业ID（可选）
   * @param daysThreshold 天数阈值
   * @returns 清理结果
   */
  cleanupStorage: async (
    cleanupType: 'auto_save' | 'old_versions' | 'optimize' | 'full' = 'auto_save',
    jobId?: number,
    daysThreshold: number = 30
  ): Promise<any> => {
    try {
      const response = await apiClient.post('/api/v1/subtitles/cleanup-storage', {}, {
        params: {
          job_id: jobId,
          cleanup_type: cleanupType,
          days_threshold: daysThreshold,
        },
      });
      return response.data;
    } catch (error) {
      console.error('存储清理失败:', error);
      throw error;
    }
  },

  /**
   * 执行自动保存到后端
   * @param jobId 作业ID
   * @param language 语言
   * @param subtitles 字幕数据
   * @returns 自动保存结果
   */
  performAutoSave: async (
    jobId: number,
    language: string,
    subtitles: Subtitle[]
  ): Promise<any> => {
    try {
      const response = await apiClient.post(`/api/v1/subtitles/auto-save/${jobId}`, 
        subtitles,
        {
          params: { language },
        }
      );
      return response.data;
    } catch (error) {
      // 自动保存失败不应该中断用户操作
      console.warn('自动保存到后端失败:', error);
      return { success: false, error };
    }
  },
};

export default subtitleVersionService;