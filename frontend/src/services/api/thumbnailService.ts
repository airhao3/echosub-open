/**
 * Thumbnail Service
 * 
 * Handles video thumbnail operations
 */

import { apiClient } from './apiClient';

export interface ThumbnailInfo {
  job_id: number;
  thumbnails: {
    [size: string]: {
      exists: boolean;
      path?: string;
      size_bytes?: number;
      modified?: number;
      url: string;
    };
  };
  total_available: number;
}

export class ThumbnailService {
  /**
   * Get thumbnail URL for a job
   */
  static getThumbnailUrl(jobId: number, size: 'small' | 'medium' | 'large' | 'poster' = 'medium'): string {
    const token = localStorage.getItem('token');
    const apiClientBaseUrl = (apiClient as any).client.defaults.baseURL || '';
    const apiPrefix = '/api/v1'; // Use consistent API prefix
    const baseUrl = `${apiClientBaseUrl}${apiPrefix}/thumbnails/${jobId}?size=${size}`;
    return token ? `${baseUrl}&token=${token}` : baseUrl;
  }

  /**
   * Get thumbnail information for a job
   */
  static async getThumbnailInfo(jobId: number): Promise<ThumbnailInfo> {
    const response = await apiClient.get(`/thumbnails/${jobId}/info`);
    return response.data as ThumbnailInfo;
  }

  /**
   * Generate thumbnails for a job
   */
  static async generateThumbnails(
    jobId: number, 
    sizes: string[] = ['small', 'medium', 'large']
  ): Promise<void> {
    const params = new URLSearchParams();
    sizes.forEach(size => params.append('sizes', size));
    
    await apiClient.post(`/thumbnails/${jobId}/generate?${params.toString()}`);
  }

  /**
   * Check if thumbnail exists by trying to load it
   */
  static checkThumbnailExists(jobId: number, size: string = 'medium'): Promise<boolean> {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = this.getThumbnailUrl(jobId, size as any);
    });
  }

  /**
   * Preload thumbnail images for better UX
   */
  static preloadThumbnails(jobIds: number[], size: string = 'medium'): void {
    jobIds.forEach(jobId => {
      const img = new Image();
      img.src = this.getThumbnailUrl(jobId, size as any);
    });
  }
}

export default ThumbnailService;