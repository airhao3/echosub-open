import { apiClient, API_BASE_URL, API_PREFIX } from './apiClient';
import { Subtitle, parseTime } from '../../utils/subtitleUtils';

interface SubtitleApiResponse {
  job_id: number;
  language: string;
  subtitles: string;
  format: 'srt' | 'vtt';
}

export interface PreviewUrls {
  originalVideo: string;
  subtitledVideo?: string;
}

export interface VideoMetadata {
  width?: number;
  height?: number;
  codec?: string;
  fps?: number;
  duration?: number;
  bitrate?: number;
  size?: number;
}

export interface PreviewOption {
  type: string;
  language?: string;
  file_name: string;
  file_size?: number;
  mime_type?: string;
  preview_url: string;
  metadata?: VideoMetadata;
}

export interface PreviewOptions {
  job_id: number;
  job_status: string;
  available_previews: PreviewOption[];
}

interface Job {
  id: number;
  status: string;
  title: string;
  created_at: string;
  completed_at?: string;
  source_language: string;
  target_languages: string[] | string;  // Can be array or comma-separated string
  generate_subtitles: boolean;
  generate_dubbing: boolean;
  subtitle_languages?: string[];
}

/**
 * Video Preview Service - Provides methods for getting preview URLs and handling preview-related logic
 */
export const previewService = {
  /**
   * Get preview URL for the original video
   * @param jobId Job ID
   * @returns Video preview URL that can be used directly in a video player
   */
  getOriginalVideoPreviewUrl: (jobId: number): string => {
    // 先尝试直接路径获取原始视频，这似乎是正常工作的路径
    // 直接使用下载端点，而不是兼容性端点
    return `${API_BASE_URL}${API_PREFIX}/downloads/results/${jobId}/original_video?streamable=true`;
  },

  /**
   * Get preview URL for the processed video
   * @param jobId Job ID
   * @returns Processed video preview URL that can be used directly in a video player
   */
  getProcessedVideoPreviewUrl: (jobId: number): string => {
    return `/api/v1/results/${jobId}/video?streamable=true`;
  },

  /**
   * Get direct preview URL for a subtitled video
   * @param jobId Job ID
   * @param language Language code (e.g., 'en', 'zh')
   * @returns Direct URL to the subtitled video that can be used in a video player
   */
  getSubtitledVideoPreviewUrl: (jobId: number, language: string): string => {
    // Make sure to match the exact backend API path
    return `${API_BASE_URL}${API_PREFIX}/downloads/results/${jobId}/subtitled_video?language=${encodeURIComponent(language)}&streamable=true`;
  },

  /**
   * Get video URL with smart fallback strategy
   * @param jobId Job ID
   * @param preferSubtitled Whether to prefer subtitled video over original
   * @param language Language code for subtitled video (defaults to 'zh')
   * @returns Object with primary and fallback video URLs
   */
  getSmartVideoUrls: (jobId: number, preferSubtitled: boolean = false, language: string = 'zh') => {
    const originalUrl = previewService.getOriginalVideoPreviewUrl(jobId);
    const subtitledUrl = previewService.getSubtitledVideoPreviewUrl(jobId, language);
    
    return {
      primary: preferSubtitled ? subtitledUrl : originalUrl,
      fallback: preferSubtitled ? originalUrl : subtitledUrl,
      original: originalUrl,
      subtitled: subtitledUrl
    };
  },

  /**
   * Get preview URL for subtitle file
   * @param jobId Job ID
   * @returns Subtitle file URL
   */
  getSubtitlePreviewUrl: (jobId: number): string => {
    return `/api/v1/results/${jobId}/subtitle`;
  },

  /**
   * Check if job results can be previewed
   * @param jobId Job ID
   * @returns Whether results can be previewed
   */
  canPreviewResults: async (jobId: number): Promise<boolean> => {
    try {
      const response = await apiClient.get(`/api/v1/jobs/${jobId}`);
      const job = response.data as Job;
      return job.status === 'COMPLETED';
    } catch (error) {
      console.error('Error checking preview availability:', error);
      return false;
    }
  },

  canPreviewUserResults: async (userJobNumber: number): Promise<boolean> => {
    try {
      const response = await apiClient.get(`/api/v1/my/jobs/${userJobNumber}`);
      const job = response.data as Job;
      return job.status === 'COMPLETED';
    } catch (error) {
      console.error('Error checking user preview availability:', error);
      return false;
    }
  },

  /**
   * Get preview URLs for a job
   * @param jobId Job ID
   * @returns Original and subtitled video URLs
   */
  getPreviewUrls: async (jobId: number, language?: string): Promise<PreviewUrls> => {
    console.log('PreviewService: ======= GET PREVIEW URLS =======');
    console.log('PreviewService: Fetching preview URLs for job ID:', jobId);
    if (language) {
      console.log('PreviewService: Language specified:', language);
    }
    
    try {
      // Verify the job exists and can be previewed
      console.log('PreviewService: Checking job status...');
      const jobUrl = `/api/v1/jobs/${jobId}`;
      console.log('PreviewService: Fetching job from:', jobUrl);
      
      const response = await apiClient.get(jobUrl);
      console.log('PreviewService: Job API response status:', response.status);
      
      const job = response.data as Job;
      console.log('PreviewService: Job data retrieved:', JSON.stringify(job, null, 2));
      console.log('PreviewService: Job status:', job.status);
      
      // If the job isn't complete, throw an error
      if (job.status !== 'completed' && job.status !== 'COMPLETED') {
        console.error(`PreviewService: [ERROR] Job is not in completed state (status: ${job.status})`);
        throw new Error(`Job is not completed (status: ${job.status}). Cannot generate preview URLs.`);
      }
      
      // Get available preview options from the backend
      try {
        console.log('PreviewService: Fetching preview options...');
        const previewOptions = await previewService.getPreviewOptions(jobId);
        console.log('PreviewService: Preview options found:', previewOptions.available_previews?.length || 0);
        
        // Try to find original and subtitled video options
        const originalOption = previewOptions.available_previews.find((option: PreviewOption) => 
          option.type === 'original_video');
        
        // Find subtitled option with matching language
        const subtitledOption = previewOptions.available_previews.find((option: PreviewOption) => 
          option.type === 'subtitled_video' && (!language || option.language === language));
        
        console.log('PreviewService: Found options:', { 
          originalOption: originalOption?.type || 'not found', 
          subtitledOption: subtitledOption?.type || 'not found',
          subtitledLanguage: subtitledOption?.language || 'not specified'
        });
        
        // Use compatibility endpoint for original video to handle potential missing files
        const originalUrl = previewService.getOriginalVideoPreviewUrl(jobId);
        
        // Use direct endpoint for subtitled video with specific language
        let subtitledUrl: string | undefined = undefined;
        if (subtitledOption && subtitledOption.preview_url) {
          subtitledUrl = subtitledOption.preview_url;
        } else if (language) {
          subtitledUrl = previewService.getSubtitledVideoPreviewUrl(jobId, language);
        }
        
        console.log('PreviewService: Created preview URLs:');
        console.log('PreviewService: Original video URL:', originalUrl);
        console.log('PreviewService: Subtitled video URL:', subtitledUrl);
        console.log('PreviewService: ======= PREVIEW URLS COMPLETE =======');
        
        return {
          originalVideo: originalUrl,
          subtitledVideo: subtitledUrl
        };
      } catch (optionsError) {
        // Fallback to direct URLs if preview options API fails
        console.warn('PreviewService: [WARNING] Failed to get preview options, using direct URLs');
        console.warn('PreviewService: [WARNING] Error:', optionsError);
        
        // Use compatibility endpoint for original video
        const originalUrl = previewService.getOriginalVideoPreviewUrl(jobId);
        
        // Use direct URL for subtitled video
        let subtitledUrl: string | undefined = undefined;
        if (language) {
          subtitledUrl = previewService.getSubtitledVideoPreviewUrl(jobId, language);
        }
        
        console.log('PreviewService: Created fallback preview URLs:');
        console.log('PreviewService: Original video URL:', originalUrl);
        console.log('PreviewService: Subtitled video URL:', subtitledUrl);
        
        return {
          originalVideo: originalUrl,
          subtitledVideo: subtitledUrl
        };
      }
    } catch (error) {
      console.error('PreviewService: [ERROR] Failed to get preview URLs:', error);
      if (error instanceof Error) {
        console.error('PreviewService: [ERROR] Error details:', error.message);
        console.error('PreviewService: [ERROR] Stack trace:', error.stack);
      }
      throw error; // Re-throw to allow component to handle it
    }
  },
  
  /**
   * Get all available preview options for a job
   * @param jobId Job ID
   * @returns Object containing available preview options
   */
  getPreviewOptions: async (jobId: number): Promise<PreviewOptions> => {
    console.log('PreviewService: ======= GET PREVIEW OPTIONS =======');
    console.log('PreviewService: Requesting preview options for job ID:', jobId);
    
    try {
      const optionsUrl = `/api/v1/preview/options/${jobId}`;
      console.log('PreviewService: Making request to:', optionsUrl);
      
      const response = await apiClient.get(optionsUrl);
      console.log('PreviewService: Preview options API response status:', response.status);
      
      // Log the available preview options in a more readable format
      const previewData = response.data as PreviewOptions;
      console.group('Preview Options Details:');
      console.log('Job ID:', previewData.job_id);
      console.log('Job Status:', previewData.job_status);
      console.log('Available Previews:');
      previewData.available_previews.forEach((preview, index) => {
        console.group(`Preview ${index + 1}:`);
        console.log('Type:', preview.type);
        console.log('Language:', preview.language || 'N/A');
        console.log('File Name:', preview.file_name);
        console.log('MIME Type:', preview.mime_type || 'N/A');
        console.log('Preview URL:', preview.preview_url);
        console.groupEnd();
      });
      console.groupEnd();
      
      console.log('PreviewService: ======= PREVIEW OPTIONS COMPLETE =======');
      
      return previewData;
    } catch (optionsError) {
      console.error('PreviewService: [ERROR] Failed to fetch preview options');
      if (optionsError instanceof Error) {
        console.error('PreviewService: [ERROR] Error details:', optionsError.message);
        console.error('PreviewService: [ERROR] Stack trace:', optionsError.stack);
      } else {
        console.error('PreviewService: [ERROR] Unknown error type:', optionsError);
      }
      
      // Be explicit about the error to help with debugging
      throw new Error(`Preview options not available for job ${jobId}. The endpoint /api/v1/preview/options/${jobId} may not exist or returned an error.`);
    }
  },

  /**
   * Fetches and parses subtitles for a given job and language.
   * @param jobId The ID of the job.
   * @param language The language of the subtitles to fetch.
   * @returns A promise that resolves to an array of Subtitle objects.
   */
  getSubtitles: async (jobId: number, language: string): Promise<Subtitle[]> => {
    // Handle 'auto' and 'src' language mappings
    let effectiveLanguage = language;
    if (language === 'auto' || language === 'src') {
      effectiveLanguage = 'src'; // Always use 'src' for source language
      console.log(`Language '${language}' mapped to 'src' for subtitle fetching`);
    }
    console.log(`=== Fetching subtitles for job ${jobId} in ${effectiveLanguage} (original: ${language}) ===`);
    try {
      // First try the direct subtitle API (now returns JSON format)
      try {
        // Try to get JSON working file first (contains latest edits)
        try {
          const response = await apiClient.get<Subtitle[]>(`/api/v1/preview/subtitles/${jobId}`, {
            params: { language: effectiveLanguage }
          });
          
          console.log('Received JSON subtitle data');
          console.log('Response headers:', response.headers);
          console.log('Response data type:', typeof response.data);
          console.log('Response data:', response.data);
          
          // Check if we got JSON array directly
          if (Array.isArray(response.data)) {
            console.log('Successfully loaded JSON subtitles:', response.data.length);
            return response.data;
          }
          
          // Check if data is wrapped in an object
          if (response.data && typeof response.data === 'object') {
            // If it's an object, try to find the subtitles array
            const data = response.data as any;
            if (Array.isArray(data.subtitles)) {
              console.log('Found subtitles array in object:', data.subtitles.length);
              return data.subtitles;
            }
            // If the whole object is a single subtitle-like object, wrap it in array
            if (data.id && data.text !== undefined) {
              console.log('Converting single subtitle object to array');
              return [data];
            }
          }
          
          console.warn('Unexpected JSON response format:', response.data);
          return [];
        } catch (jsonError) {
          console.log('JSON subtitle fetch failed, trying raw text format:', jsonError);
          
          // Fallback to raw text format (SRT/VTT files)
          const response = await apiClient.get<string>(`/api/v1/preview/subtitles/${jobId}`, {
            params: { language: effectiveLanguage },
            responseType: 'text',
            transformResponse: [(data: string) => data]
          });
          
          console.log('Received raw subtitle content, parsing...');
          console.log('Response headers:', response.headers);
          console.log('First 200 chars of subtitle content:', response.data.substring(0, 200));
          
          // Determine format from content type
          const contentType = response.headers?.['content-type'] || '';
          const isVtt = contentType.includes('vtt');
          
          let parsedSubtitles: Subtitle[] = [];
          try {
            if (isVtt) {
              parsedSubtitles = previewService.parseVtt(response.data);
              console.log('Successfully parsed VTT subtitles:', parsedSubtitles.length);
            } else {
              parsedSubtitles = previewService.parseSrt(response.data);
              console.log('Successfully parsed SRT subtitles:', parsedSubtitles.length);
            }
            
            if (parsedSubtitles.length === 0) {
              console.warn('Parsed subtitles array is empty');
            }
            
            return parsedSubtitles;
          } catch (parseError) {
            console.error('Error parsing subtitles:', parseError);
            console.error('Subtitle content that failed to parse:', response.data);
            return [];
          }
        }
      } catch (directError) {
        console.warn('Direct subtitle API failed, falling back to preview options:', directError);
        // Fall back to the old method if direct API fails
      }
      
      // Fallback to getting subtitles via preview options
      console.log('Getting preview options...');
      const options = await previewService.getPreviewOptions(jobId);
      console.log('Available preview options:', options.available_previews);
      
      const subtitleOption = options.available_previews.find(
        (p) => (p.type === 'subtitles' || p.type === 'subtitles_file') && 
               (p.language === effectiveLanguage || p.language === language)
      );
      
      console.log('Looking for subtitle with language:', effectiveLanguage, 'or', language);

      if (!subtitleOption || !subtitleOption.preview_url) {
        console.warn(`Subtitles for language '${language}' not found in preview options.`);
        console.warn('Available languages:', options.available_previews.map(p => ({
          type: p.type,
          language: p.language,
          file: p.file_name
        })));
        return []; // Not an error, just no subtitles available
      }

      const response = await apiClient.get(subtitleOption.preview_url, {
        responseType: 'text',
      });

      const subtitleContent = response.data as string;
      const fileName = subtitleOption.file_name.toLowerCase();

      if (fileName.endsWith('.srt')) {
        console.log('Parsing SRT file:', subtitleOption.file_name);
        return previewService.parseSrt(subtitleContent);
      } else if (fileName.endsWith('.vtt')) {
        console.log('Parsing VTT file:', subtitleOption.file_name);
        return previewService.parseVtt(subtitleContent);
      } else {
        console.warn(`Unsupported subtitle format for file: ${subtitleOption.file_name}. Attempting to parse as VTT.`);
        return previewService.parseVtt(subtitleContent); // Default fallback
      }
    } catch (error) {
      console.error('Error fetching or parsing subtitles:', error);
      return [];
    }
  },

  /**
   * Parses a VTT file content into an array of Subtitle objects.
   * @param vttContent The string content of the VTT file.
   * @returns An array of Subtitle objects.
   */
  parseVtt: (vttContent: string): Subtitle[] => {
    console.log('Starting VTT parsing');
    const lines = vttContent.split(/\r?\n/);
    console.log(`Total lines in VTT: ${lines.length}`);
    const subtitles: Subtitle[] = [];
    let i = 0;
    let lineCount = 0;

    while (i < lines.length) {
      lineCount++;
      if (lineCount > 1000) { // Safety check to prevent infinite loops
        console.error('Excessive lines processed, possible infinite loop');
        break;
      }
      
      const currentLine = lines[i];
      // Skip empty lines
      if (!currentLine.trim()) {
        i++;
        continue;
      }
      
      // Handle WEBVTT header
      if (currentLine.includes('WEBVTT')) {
        console.log('Found WEBVTT header');
        i++;
        // Skip any header metadata
        while (i < lines.length && lines[i] && lines[i].includes(':')) {
          i++;
        }
        continue;
      }

      // A cue identifier is optional
      let id = (subtitles.length + 1).toString();
      let lineAfterId = currentLine;
      let nextLine = i + 1 < lines.length ? lines[i + 1] : '';

      // Check for timecodes - try current line or next line
      let timeMatch = lineAfterId.match(/(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})/);
      
      // If no match on current line, try next line (might be cue ID on this line)
      if (!timeMatch && nextLine) {
        timeMatch = nextLine.match(/(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})/);
        if (timeMatch) {
          i++; // Skip the ID line
        }
      }

      if (timeMatch) {
        console.log(`Found timecode at line ${i + 1}:`, timeMatch[0]);
        const startTimeStr = timeMatch[1].replace(',', '.');
        const endTimeStr = timeMatch[2].replace(',', '.');
        const startTime = parseTime(startTimeStr);
        const endTime = parseTime(endTimeStr);
        i++; // Move past the timecode line

        // Skip any cue settings (text after timecode on same line)
        // Note: cue settings would be handled here if needed
        
        // Collect text lines until empty line or end of file
        let text = '';
        while (i < lines.length && lines[i].trim()) {
          if (text) text += '\n';
          text += lines[i].trim();
          i++;
        }

        if (text) {
          console.log(`Added subtitle ${id}: ${text.substring(0, 30)}...`);
          subtitles.push({ id, startTime, endTime, text });
        } else {
          console.warn('Empty text for subtitle at line', i);
        }
      } else {
        console.warn('No valid timecode found at line', i + 1, 'content:', currentLine);
        i++; // Skip this line and try the next one
      }
    }

    return subtitles;
  },

  /**
   * Parses an SRT file content into an array of Subtitle objects.
   * @param srtContent The string content of the SRT file.
   * @returns An array of Subtitle objects.
   */
  parseSrt: (srtContent: string): Subtitle[] => {
    const subtitles: Subtitle[] = [];
    // Trim and normalize line endings, then split into blocks
    const blocks = srtContent.trim().replace(/\r\n/g, '\n').split('\n\n');

    for (const block of blocks) {
      const lines = block.split('\n');
      if (lines.length < 2) continue;

      let id = '';
      let timeLineIndex = -1;

      // Find the line with the timecode, as the sequence number is optional
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('-->')) {
          timeLineIndex = i;
          break;
        }
      }

      if (timeLineIndex === -1) continue; // No timecode found

      // ID is the line before the timecode, if it exists and is numeric
      if (timeLineIndex > 0 && !isNaN(parseInt(lines[timeLineIndex - 1], 10))) {
        id = lines[timeLineIndex - 1];
      } else {
        id = (subtitles.length + 1).toString(); // Fallback ID
      }

      const timeMatch = lines[timeLineIndex].match(/(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/);
      if (timeMatch) {
        const startTime = parseTime(timeMatch[1]);
        const endTime = parseTime(timeMatch[2]);
        const text = lines.slice(timeLineIndex + 1).join('\n');

        if (text) { // Ensure there is text content
          subtitles.push({ id, startTime, endTime, text });
        }
      }
    }
    return subtitles;
  },

  // User-specific preview functions that work with user_job_number
  // Note: These are kept for API consistency but internally use global IDs
  getUserOriginalVideoPreviewUrl: (globalJobId: number): string => {
    console.log('PreviewService: Getting original video URL for global job ID:', globalJobId);
    return previewService.getOriginalVideoPreviewUrl(globalJobId);
  },

  getUserSubtitledVideoPreviewUrl: (globalJobId: number, language: string): string => {
    console.log('PreviewService: Getting subtitled video URL for global job ID:', globalJobId);
    return previewService.getSubtitledVideoPreviewUrl(globalJobId, language);
  },

  getUserPreviewOptions: async (userJobNumber: number): Promise<PreviewOptions> => {
    console.log('PreviewService: ======= GET USER PREVIEW OPTIONS =======');
    console.log('PreviewService: Requesting preview options for user job number:', userJobNumber);
    
    try {
      const optionsUrl = `/api/v1/my/jobs/${userJobNumber}/preview/options`;
      console.log('PreviewService: Making request to:', optionsUrl);
      
      const response = await apiClient.get(optionsUrl);
      console.log('PreviewService: Preview options API response status:', response.status);
      
      const previewData = response.data as PreviewOptions;
      console.group('User Preview Options Details:');
      console.log('User Job Number:', userJobNumber);
      console.log('Job Status:', previewData.job_status);
      console.log('Available Previews:');
      previewData.available_previews.forEach((preview, index) => {
        console.group(`Preview ${index + 1}:`);
        console.log('Type:', preview.type);
        console.log('Language:', preview.language || 'N/A');
        console.log('File Name:', preview.file_name);
        console.log('MIME Type:', preview.mime_type || 'N/A');
        console.log('Preview URL:', preview.preview_url);
        console.groupEnd();
      });
      console.groupEnd();
      
      console.log('PreviewService: ======= USER PREVIEW OPTIONS COMPLETE =======');
      
      return previewData;
    } catch (optionsError) {
      console.error('PreviewService: [ERROR] Failed to fetch user preview options');
      if (optionsError instanceof Error) {
        console.error('PreviewService: [ERROR] Error details:', optionsError.message);
        console.error('PreviewService: [ERROR] Stack trace:', optionsError.stack);
      } else {
        console.error('PreviewService: [ERROR] Unknown error type:', optionsError);
      }
      
      throw new Error(`User preview options not available for job ${userJobNumber}. The endpoint /api/v1/my/jobs/${userJobNumber}/preview/options may not exist or returned an error.`);
    }
  },

  
};
