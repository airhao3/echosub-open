import { apiClient } from '../services/api/apiClient';

// Updated to pass a progress object with percentage and speed
export interface UploadOptions {
  onProgress?: (progress: { percentage: number; speed: number; }) => void;
  chunkSize?: number;
  maxRetries?: number;
}

interface UploadResponse {
  success: boolean;
  message?: string;
  data?: any;
  jobId?: string | number;
}

const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
const DEFAULT_MAX_RETRIES = 3;

// Helper function to copy FormData entries
const copyFormData = (source: FormData, target: FormData): void => {
  // @ts-ignore - entries() exists on FormData but TypeScript types are incomplete
  for (const [key, value] of source.entries()) {
    if (value instanceof File) {
      target.append(key, value, value.name);
    } else {
      target.append(key, value);
    }
  }
};

export const uploadFileInChunks = async <T>(
  file: File,
  url: string,
  formData: FormData,
  options: UploadOptions = {}
): Promise<T> => {
  const {
    onProgress,
    chunkSize = DEFAULT_CHUNK_SIZE,
    maxRetries = DEFAULT_MAX_RETRIES,
  } = options;

  const totalChunks = Math.ceil(file.size / chunkSize);
  const fileId = Math.random().toString(36).substring(2, 15);
  const uploadId = Math.random().toString(36).substring(2, 15);

  // State for speed calculation
  let totalLoadedBytes = 0;
  let lastTime = Date.now();

  // Upload each chunk with retry logic
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const chunk = file.slice(start, end);
    
    const chunkFormData = new FormData();
    copyFormData(formData, chunkFormData);
    
    chunkFormData.append('file', chunk, file.name);
    chunkFormData.append('chunkIndex', chunkIndex.toString());
    chunkFormData.append('totalChunks', totalChunks.toString());
    chunkFormData.append('fileId', fileId);
    chunkFormData.append('uploadId', uploadId);
    chunkFormData.append('originalFilename', file.name);
    chunkFormData.append('fileSize', file.size.toString());
    chunkFormData.append('mimeType', file.type);

    let retryCount = 0;
    let success = false;

    while (retryCount <= maxRetries && !success) {
      try {
        await apiClient.post<UploadResponse>(url, chunkFormData, {
          headers: {
            'X-Chunk-Index': chunkIndex.toString(),
            'X-Total-Chunks': totalChunks.toString(),
            'X-File-Id': fileId,
            'X-Upload-Id': uploadId,
          },
          timeout: 300000, // 5 minutes per chunk
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const chunkLoadedBytes = progressEvent.loaded;
              const currentTotalLoaded = (chunkIndex * chunkSize) + chunkLoadedBytes;

              const currentTime = Date.now();
              const timeElapsed = (currentTime - lastTime) / 1000; // in seconds
              const bytesSinceLast = currentTotalLoaded - totalLoadedBytes;
              
              // Calculate speed in bytes per second
              const speed = timeElapsed > 0 ? bytesSinceLast / timeElapsed : 0;

              const percentage = Math.min(99, Math.round((currentTotalLoaded / file.size) * 100));
              
              if (onProgress) {
                onProgress({ percentage, speed });
              }

              // Update for next calculation - only update if time has passed to avoid jerky speed calcs
              if (timeElapsed > 0.5) { // Update every half second
                totalLoadedBytes = currentTotalLoaded;
                lastTime = currentTime;
              }
            }
          },
        });

        success = true;

      } catch (error: any) {
        retryCount++;
        if (retryCount > maxRetries) {
          throw new Error(`Failed to upload chunk ${chunkIndex + 1}/${totalChunks} after ${maxRetries} retries: ${error.message}`);
        }
        const backoffTime = 1000 * Math.pow(2, retryCount) + Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, backoffTime));
      }
    }
  }

  // Finalize the upload after all chunks are sent
  try {
    const response = await apiClient.post<T>(
      `${url}/complete`, 
      {
        fileId,
        uploadId,
        originalFilename: file.name,
        fileSize: file.size,
        mimeType: file.type,
        totalChunks,
      },
      {
        headers: { 'Content-Type': 'application/json', 'X-File-Id': fileId, 'X-Upload-Id': uploadId },
      }
    );

    if (onProgress) {
      onProgress({ percentage: 100, speed: 0 });
    }
    return response.data as T;
  } catch (error: any) {
    throw new Error(`Failed to finalize upload: ${error.message}`);
  }
};