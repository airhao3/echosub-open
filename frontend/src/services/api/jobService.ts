import { apiClient } from './apiClient';
import { uploadFileInChunks } from '../../utils/fileUpload';

export interface Job {
  id: number;
  user_job_number: number;     // User-specific job number (1, 2, 3, ...)
  title: string;
  description: string;
  status: string;
  source_language: string;
  target_languages: string;
  source_video_url: string;
  original_video_url?: string;
  subtitled_video_urls?: { [key: string]: string };
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  owner_id: number;
  generate_subtitles: boolean;
  generate_dubbing: boolean;
  subtitle_languages?: string[];
  video_filename?: string;      // Original filename of the uploaded video
  // Added fields for processing visualization
  progress?: number;           // Overall progress percentage (0-100)
  current_step?: string;       // Current processing step identifier
  error_message?: string;      // Error message if processing failed
}

export interface JobResult {
  id: number;
  job_id: number;
  result_type: string;
  file_path: string;
  file_url: string;
  created_at: string;
}

export interface FileRegistry {
  job_id: number;
  files: {
    [key: string]: string[];
  };
}

export const getJobFileRegistry = async (jobId: number): Promise<FileRegistry> => {
  const response = await apiClient.get<FileRegistry>(`/api/v1/jobs/${jobId}/file-registry`);
  return response.data;
};

export interface CreateJobRequest {
  title: string;
  description?: string;
  source_language: string;
  target_languages: string;
  generate_subtitles: boolean;
  generate_dubbing: boolean;
  video_format?: string;
  resolution?: string;
  subtitle_style?: string; // Can be a preset string or a JSON string of a SubtitleStyle object
}

export const getJobs = async (): Promise<Job[]> => {
  const response = await apiClient.get<Job[]>('/api/v1/jobs/');
  return response.data;
};

export const getJob = async (id: number): Promise<Job> => {
  const response = await apiClient.get<Job>(`/api/v1/jobs/${id}`);
  return response.data;
};

// Job status response from the new granular status tracking API
export interface JobStatusResponse {
  // Overall job information
  job_id: number;
  status: string;  // "PENDING", "PROCESSING", "COMPLETED", "FAILED"
  progress: number; // 0-100 percentage
  message: string;
  status_message?: string; // Additional status message from the backend
  estimated_time?: string;
  
  // Individual step statuses
  steps: JobStepStatus[];
}

export interface JobStepStatus {
  step_name: string;  // UPLOAD, AUDIO_PROCESSING, TRANSCRIPTION, TEXT_PROCESSING, TRANSLATION, INTEGRATION, ALIGNMENT
  status: string;     // "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"
  progress: number;   // 0-100 percentage
  details?: string;   // Additional status information
  updated_at: string; // ISO timestamp
}

export const getJobStatus = async (id: number): Promise<JobStatusResponse> => {
  try {
    console.log(`Fetching job status for job ID: ${id}`);
    const response = await apiClient.get<JobStatusResponse>(`/api/v1/jobs/${id}/status`);
    console.log(`Job status response for job ${id}:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`Error fetching job status for job ${id}:`, error);
    // Return a default error response structure that matches the expected interface
    return {
      job_id: id,
      status: 'ERROR',
      progress: 0,
      message: error instanceof Error ? error.message : 'Unknown error fetching job status',
      steps: []
    };
  }
};

// Define the response type from video upload endpoint
export interface JobCreationResponse {
  job_id: number;
  user_job_number: number;  // User-specific job number for API routing
  status: string;
  message: string;
  // Fields for duplicate video handling
  duplicate?: boolean;
  original_job_id?: number;
  all_results_ready?: boolean;
  user_prompt?: string;
  available_languages?: string[];
  options?: {
    label: string;
    url: string;
    primary: boolean;
  }[];
}

export const createJob = async (data: CreateJobRequest, videoFile: File, reprocess: boolean = false): Promise<JobCreationResponse> => {
  const formData = new FormData();
  
  // Append job data
  formData.append('title', data.title);
  if (data.description) formData.append('description', data.description);
  formData.append('source_language', data.source_language);
  formData.append('target_languages', data.target_languages);
  formData.append('generate_subtitles', data.generate_subtitles.toString());
  formData.append('generate_dubbing', data.generate_dubbing.toString());

  // Append output settings if they exist
  if (data.video_format) formData.append('video_format', data.video_format);
  if (data.resolution) formData.append('resolution', data.resolution);
  if (data.subtitle_style) formData.append('subtitle_style', data.subtitle_style);
  
  // Append reprocess flag if true
  if (reprocess) {
    formData.append('reprocess', 'true');
  }

  // For small files (< 20MB), use regular upload
  if (videoFile.size < 20 * 1024 * 1024) {
    formData.append('file', videoFile);
    const response = await apiClient.post<JobCreationResponse>('/api/v1/uploads/video', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }
  
  // For larger files, use chunked upload
  try {
    const response = await uploadFileInChunks<JobCreationResponse>(
      videoFile,
      '/api/v1/uploads/video/chunked',
      formData,
      {
        chunkSize: 5 * 1024 * 1024, // 5MB chunks
        maxRetries: 3,
      }
    );
    return response;
  } catch (error) {
    console.error('Chunked upload failed, falling back to regular upload', error);
    
    // Fallback to regular upload if chunked upload fails
    formData.append('file', videoFile);
    const response = await apiClient.post<JobCreationResponse>('/api/v1/uploads/video', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 5 minutes
    });
    
    return response.data;
  }
};

// Version with progress callback for tracking upload progress
export const createJobWithProgress = async (
  data: CreateJobRequest, 
  videoFile: File,
  onProgressUpdate: (progress: { percentage: number; speed: number }) => void, // Changed signature
  reprocess: boolean = false
): Promise<JobCreationResponse> => {
  const formData = new FormData();
  
  // Append job data
  formData.append('title', data.title);
  if (data.description) formData.append('description', data.description);
  formData.append('source_language', data.source_language);
  formData.append('target_languages', data.target_languages);
  formData.append('generate_subtitles', data.generate_subtitles.toString());
  formData.append('generate_dubbing', data.generate_dubbing.toString());
  if (data.video_format) formData.append('video_format', data.video_format);
  if (data.resolution) formData.append('resolution', data.resolution);
  if (data.subtitle_style) formData.append('subtitle_style', data.subtitle_style);
  if (reprocess) formData.append('reprocess', 'true');

  // State for speed calculation for small files
  let lastLoadedBytes = 0;
  let lastTime = Date.now();

  // For small files (< 20MB), use regular upload
  if (videoFile.size < 20 * 1024 * 1024) {
    formData.append('file', videoFile);
    
    const response = await apiClient.post<JobCreationResponse>('/api/v1/uploads/video', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const currentTime = Date.now();
          const timeElapsed = (currentTime - lastTime) / 1000;
          const bytesSinceLast = progressEvent.loaded - lastLoadedBytes;
          const speed = timeElapsed > 0 ? bytesSinceLast / timeElapsed : 0;
          const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          
          onProgressUpdate({ percentage, speed });

          lastLoadedBytes = progressEvent.loaded;
          lastTime = currentTime;
        }
      },
      timeout: 300000, // 5 minutes
    });
    
    return response.data;
  }
  
  // For larger files, use chunked upload
  try {
    const response = await uploadFileInChunks<JobCreationResponse>(
      videoFile,
      '/api/v1/uploads/video/chunked',
      formData,
      {
        chunkSize: 5 * 1024 * 1024, // 5MB chunks
        maxRetries: 3,
        onProgress: onProgressUpdate, // Directly pass the callback
      }
    );
    return response;
  } catch (error) {
    console.error('Chunked upload failed, falling back to regular upload', error);
    
    // Fallback to regular upload if chunked upload fails
    formData.append('file', videoFile);
    const response = await apiClient.post<JobCreationResponse>('/api/v1/uploads/video', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => { // Re-add progress here for fallback
        if (progressEvent.total) {
          const currentTime = Date.now();
          const timeElapsed = (currentTime - lastTime) / 1000;
          const bytesSinceLast = progressEvent.loaded - lastLoadedBytes;
          const speed = timeElapsed > 0 ? bytesSinceLast / timeElapsed : 0;
          const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          
          onProgressUpdate({ percentage, speed });

          lastLoadedBytes = progressEvent.loaded;
          lastTime = currentTime;
        }
      },
      timeout: 300000, // 5 minutes
    });
    
    return response.data;
  }
};

export const cancelJob = async (jobId: number): Promise<Job> => {
  try {
    const response = await apiClient.post<Job>(`/api/v1/jobs/${jobId}/cancel`);
    return response.data;
  } catch (error) {
    console.error('Error canceling job:', error);
    throw error;
  }
};

export interface ReprocessResponse {
  job_id: number;
  status: string;
  message: string;
}

export const reprocessJob = async (jobId: number, forceReprocess: boolean = false): Promise<ReprocessResponse> => {
  try {
    const response = await apiClient.post<ReprocessResponse>(
      `/api/v1/jobs/${jobId}/reprocess`, 
      {},  // Empty request body
      { params: { force_reprocess: forceReprocess } }
    );
    return response.data;
  } catch (error) {
    console.error('Error reprocessing job:', error);
    throw error;
  }
};

export const deleteJob = async (id: number): Promise<void> => {
  await apiClient.delete(`/api/v1/jobs/${id}`);
};

export const deleteMultipleJobs = async (jobIds: number[]): Promise<void> => {
  await apiClient.post('/api/v1/jobs/bulk_delete', { job_ids: jobIds });
};

export const getJobResults = async (id: number): Promise<JobResult[]> => {
  const response = await apiClient.get<JobResult[]>(`/api/v1/jobs/${id}/results`);
  return response.data;
};

export const getJobDetails = async (id: number): Promise<Job> => {
  const response = await apiClient.get<Job>(`/api/v1/jobs/${id}/details`);
  return response.data;
};

export const downloadResult = async (jobId: number, resultType: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/downloads/results/${jobId}/${resultType}`, {
    responseType: 'blob',
  });
  return response.data as Blob;
};

export const downloadAllResults = async (jobId: number): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/downloads/zip/${jobId}`, {
    responseType: 'blob',
  });
  return response.data as Blob;
};

// User-specific API functions that work with user_job_number
// These functions provide user-friendly numbering while internally using global IDs

export const getUserJobs = async (): Promise<Job[]> => {
  const response = await apiClient.get<Job[]>('/api/v1/my/jobs/');
  return response.data;
};

export const getUserJob = async (userJobNumber: number): Promise<Job> => {
  const response = await apiClient.get<Job>(`/api/v1/my/jobs/${userJobNumber}`);
  return response.data;
};

export const getUserJobStatus = async (userJobNumber: number): Promise<JobStatusResponse> => {
  try {
    console.log(`Fetching job status for user job number: ${userJobNumber}`);
    const response = await apiClient.get<JobStatusResponse>(`/api/v1/my/jobs/${userJobNumber}/status`);
    console.log(`Job status response for user job ${userJobNumber}:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`Error fetching job status for user job ${userJobNumber}:`, error);
    return {
      job_id: userJobNumber,
      status: 'ERROR',
      progress: 0,
      message: error instanceof Error ? error.message : 'Unknown error fetching job status',
      steps: []
    };
  }
};

export const getUserJobFileRegistry = async (userJobNumber: number): Promise<FileRegistry> => {
  const response = await apiClient.get<FileRegistry>(`/api/v1/my/jobs/${userJobNumber}/file-registry`);
  return response.data;
};

export const cancelUserJob = async (userJobNumber: number): Promise<Job> => {
  try {
    const response = await apiClient.post<Job>(`/api/v1/my/jobs/${userJobNumber}/cancel`);
    return response.data;
  } catch (error) {
    console.error('Error canceling user job:', error);
    throw error;
  }
};

export const reprocessUserJob = async (userJobNumber: number, forceReprocess: boolean = false): Promise<ReprocessResponse> => {
  try {
    const response = await apiClient.post<ReprocessResponse>(
      `/api/v1/my/jobs/${userJobNumber}/reprocess`,
      {},
      { params: { force_reprocess: forceReprocess } }
    );
    return response.data;
  } catch (error) {
    console.error('Error reprocessing user job:', error);
    throw error;
  }
};

export const deleteUserJob = async (userJobNumber: number): Promise<void> => {
  await apiClient.delete(`/api/v1/my/jobs/${userJobNumber}`);
};

export const deleteMultipleUserJobs = async (userJobNumbers: number[]): Promise<void> => {
  await apiClient.post('/api/v1/my/jobs/bulk_delete', { user_job_numbers: userJobNumbers });
};

export const getUserJobResults = async (userJobNumber: number): Promise<JobResult[]> => {
  const response = await apiClient.get<JobResult[]>(`/api/v1/my/jobs/${userJobNumber}/results`);
  return response.data;
};

export const getUserJobDetails = async (userJobNumber: number): Promise<Job> => {
  const response = await apiClient.get<Job>(`/api/v1/my/jobs/${userJobNumber}/details`);
  return response.data;
};

export const downloadUserJobResult = async (userJobNumber: number, resultType: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/downloads/user-results/${userJobNumber}/${resultType}`, {
    responseType: 'blob',
  });
  return response.data as Blob;
};

export const downloadAllUserJobResults = async (userJobNumber: number): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/downloads/user-zip/${userJobNumber}`, {
    responseType: 'blob',
  });
  return response.data as Blob;
};
