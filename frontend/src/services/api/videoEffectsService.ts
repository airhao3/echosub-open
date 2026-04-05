import { apiClient } from './apiClient';

// Types for video effects
export interface VideoEffects {
  brightness: number;
  contrast: number;
  saturation: number;
  hue: number;
  blur: number;
  opacity: number;
  rotation: number;
  scale: number;
  cropTop: number;
  cropBottom: number;
  cropLeft: number;
  cropRight: number;
  flipHorizontal: boolean;
  flipVertical: boolean;
  noise: number;
  sharpen: number;
  vignette: number;
  colorTint: string;
  grayscale: boolean;
  sepia: boolean;
  invert: boolean;
}

export interface ExportConfig {
  format: string;
  quality: string;
  resolution: string;
  framerate: string;
  includeAudio: boolean;
}

export interface ExportRequest {
  jobId: number;
  effects: VideoEffects;
  exportConfig: ExportConfig;
}

export interface ExportResponse {
  success: boolean;
  message: string;
  taskId?: string;
  estimatedTime?: number;
}

export interface FFmpegCommand {
  command: string;
  filters: string[];
  estimated_processing_time?: number;
}

export interface ExportStatus {
  state: 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE';
  progress?: number;
  status: string;
  result?: any;
}

class VideoEffectsService {
  private baseUrl = '/api/v1/video-effects';

  /**
   * Get FFmpeg command preview for given effects
   */
  async getCommandPreview(
    effects: VideoEffects,
    exportConfig?: Partial<ExportConfig>
  ): Promise<FFmpegCommand> {
    try {
      const response = await apiClient.post<FFmpegCommand>(
        `${this.baseUrl}/preview-command`,
        effects,
        {
          params: exportConfig ? { export_config: JSON.stringify(exportConfig) } : undefined,
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error getting command preview:', error);
      throw error;
    }
  }

  /**
   * Start video export with effects
   */
  async exportVideo(request: ExportRequest): Promise<ExportResponse> {
    try {
      const response = await apiClient.post<ExportResponse>(
        `${this.baseUrl}/export`,
        request
      );
      return response.data;
    } catch (error) {
      console.error('Error starting video export:', error);
      throw error;
    }
  }

  /**
   * Get export task status
   */
  async getExportStatus(taskId: string): Promise<ExportStatus> {
    try {
      const response = await apiClient.get<ExportStatus>(
        `${this.baseUrl}/export-status/${taskId}`
      );
      return response.data;
    } catch (error) {
      console.error('Error getting export status:', error);
      throw error;
    }
  }

  /**
   * Download processed video
   */
  async downloadProcessedVideo(jobId: number): Promise<Blob> {
    try {
      const response = await apiClient.get<Blob>(
        `${this.baseUrl}/download-result/${jobId}`,
        {
          responseType: 'blob',
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error downloading processed video:', error);
      throw error;
    }
  }

  /**
   * Get download URL for processed video
   */
  getDownloadUrl(jobId: number): string {
    const token = localStorage.getItem('token');
    const baseUrl = process.env.REACT_APP_API_URL || '';
    const url = `${baseUrl}${this.baseUrl}/download-result/${jobId}`;
    
    if (token) {
      return `${url}?token=${token}`;
    }
    return url;
  }

  /**
   * Poll export status until completion
   */
  async pollExportStatus(
    taskId: string,
    onProgress?: (status: ExportStatus) => void,
    pollInterval: number = 2000,
    maxPolls: number = 300 // 10 minutes max
  ): Promise<ExportStatus> {
    return new Promise((resolve, reject) => {
      let pollCount = 0;

      const poll = async () => {
        try {
          if (pollCount >= maxPolls) {
            reject(new Error('Export polling timeout'));
            return;
          }

          const status = await this.getExportStatus(taskId);
          
          if (onProgress) {
            onProgress(status);
          }

          if (status.state === 'SUCCESS' || status.state === 'FAILURE') {
            resolve(status);
            return;
          }

          pollCount++;
          setTimeout(poll, pollInterval);
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }

  /**
   * Generate CSS filter string from effects (for real-time preview)
   */
  generateCSSFilter(effects: VideoEffects): string {
    const filters = [];
    
    if (effects.brightness !== 1) filters.push(`brightness(${effects.brightness})`);
    if (effects.contrast !== 1) filters.push(`contrast(${effects.contrast})`);
    if (effects.saturation !== 1) filters.push(`saturate(${effects.saturation})`);
    if (effects.hue !== 0) filters.push(`hue-rotate(${effects.hue}deg)`);
    if (effects.blur > 0) filters.push(`blur(${effects.blur}px)`);
    if (effects.grayscale) filters.push('grayscale(100%)');
    if (effects.sepia) filters.push('sepia(100%)');
    if (effects.invert) filters.push('invert(100%)');
    
    return filters.join(' ');
  }

  /**
   * Generate CSS transform string from effects (for real-time preview)
   */
  generateCSSTransform(effects: VideoEffects): string {
    const transforms = [];
    
    if (effects.rotation !== 0) transforms.push(`rotate(${effects.rotation}deg)`);
    if (effects.scale !== 1) transforms.push(`scale(${effects.scale})`);
    if (effects.flipHorizontal) transforms.push('scaleX(-1)');
    if (effects.flipVertical) transforms.push('scaleY(-1)');
    
    return transforms.join(' ');
  }

  /**
   * Generate CSS clip-path for cropping (for real-time preview)
   */
  generateCSSClipPath(effects: VideoEffects): string | null {
    if (effects.cropTop > 0 || effects.cropBottom > 0 || 
        effects.cropLeft > 0 || effects.cropRight > 0) {
      const top = effects.cropTop;
      const right = 100 - effects.cropRight;
      const bottom = 100 - effects.cropBottom;
      const left = effects.cropLeft;
      
      return `inset(${top}% ${100 - right}% ${100 - bottom}% ${left}%)`;
    }
    return null;
  }

  /**
   * Get all CSS styles for real-time preview
   */
  getPreviewStyles(effects: VideoEffects): React.CSSProperties {
    const styles: React.CSSProperties = {};
    
    const filter = this.generateCSSFilter(effects);
    if (filter) styles.filter = filter;
    
    const transform = this.generateCSSTransform(effects);
    if (transform) styles.transform = transform;
    
    const clipPath = this.generateCSSClipPath(effects);
    if (clipPath) styles.clipPath = clipPath;
    
    if (effects.opacity !== 1) {
      styles.opacity = effects.opacity;
    }
    
    return {
      ...styles,
      transition: 'all 0.2s ease-in-out'
    };
  }

  /**
   * Validate effects values
   */
  validateEffects(effects: VideoEffects): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    // Validate ranges
    if (effects.brightness < 0.1 || effects.brightness > 3) {
      errors.push('Brightness must be between 0.1 and 3.0');
    }
    
    if (effects.contrast < 0.1 || effects.contrast > 3) {
      errors.push('Contrast must be between 0.1 and 3.0');
    }
    
    if (effects.saturation < 0 || effects.saturation > 3) {
      errors.push('Saturation must be between 0 and 3.0');
    }
    
    if (effects.hue < -180 || effects.hue > 180) {
      errors.push('Hue must be between -180 and 180 degrees');
    }
    
    if (effects.blur < 0 || effects.blur > 20) {
      errors.push('Blur must be between 0 and 20 pixels');
    }
    
    if (effects.opacity < 0 || effects.opacity > 1) {
      errors.push('Opacity must be between 0 and 1');
    }
    
    if (effects.scale < 0.1 || effects.scale > 5) {
      errors.push('Scale must be between 0.1 and 5.0');
    }
    
    // Validate crop percentages
    const totalCropH = effects.cropLeft + effects.cropRight;
    const totalCropV = effects.cropTop + effects.cropBottom;
    
    if (totalCropH >= 100) {
      errors.push('Total horizontal crop cannot be 100% or more');
    }
    
    if (totalCropV >= 100) {
      errors.push('Total vertical crop cannot be 100% or more');
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Get default effects
   */
  getDefaultEffects(): VideoEffects {
    return {
      brightness: 1,
      contrast: 1,
      saturation: 1,
      hue: 0,
      blur: 0,
      opacity: 1,
      rotation: 0,
      scale: 1,
      cropTop: 0,
      cropBottom: 0,
      cropLeft: 0,
      cropRight: 0,
      flipHorizontal: false,
      flipVertical: false,
      noise: 0,
      sharpen: 0,
      vignette: 0,
      colorTint: '#ffffff',
      grayscale: false,
      sepia: false,
      invert: false,
    };
  }

  /**
   * Create preset effects
   */
  getPresets(): { [key: string]: Partial<VideoEffects> } {
    return {
      'Vintage': {
        sepia: true,
        contrast: 1.2,
        saturation: 0.8,
        vignette: 30
      },
      'Black & White': {
        grayscale: true,
        contrast: 1.3
      },
      'Dramatic': {
        contrast: 1.5,
        saturation: 1.3,
        brightness: 0.9,
        vignette: 20
      },
      'Soft & Dreamy': {
        blur: 1,
        brightness: 1.1,
        contrast: 0.9,
        opacity: 0.95
      },
      'High Contrast': {
        contrast: 1.8,
        saturation: 1.4,
        sharpen: 5
      },
      'Cool Tone': {
        hue: 200,
        saturation: 1.1,
        brightness: 0.95
      },
      'Warm Tone': {
        hue: 30,
        saturation: 1.2,
        brightness: 1.05
      }
    };
  }
}

export const videoEffectsService = new VideoEffectsService();
export default videoEffectsService;