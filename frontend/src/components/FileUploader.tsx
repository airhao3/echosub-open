import React, { useState } from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { CreateJobRequest, createJobWithProgress } from '../services/api/jobService';
import { SubtitleStyle } from './preview/SubtitleStyleControls';

// This interface defines the shape of the data coming from the Upload form
export interface FileUploadRequest {
  title: string;
  description?: string;
  source_language: string;
  target_languages: string;
  generate_subtitles: boolean | string;
  generate_dubbing: boolean | string;
  video_format: string;
  resolution: string;
  subtitle_style: string | SubtitleStyle;
}

interface FileUploaderProps {
  file: File;
  formData: FileUploadRequest;
  onUploadComplete: (jobId: number) => void;
  onUploadError: (errorMessage: string) => void;
}

// Helper to format bytes into a readable speed format (KB/s, MB/s)
const formatSpeed = (bytesPerSecond: number) => {
  if (bytesPerSecond < 1024) {
    return `${bytesPerSecond.toFixed(0)} B/s`;
  } else if (bytesPerSecond < 1024 * 1024) {
    return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
  } else {
    return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
  }
};

const FileUploader: React.FC<FileUploaderProps> = ({
  file,
  formData,
  onUploadComplete,
  onUploadError
}) => {
  // Updated state to hold both percentage and speed
  const [progress, setProgress] = useState({ percentage: 0, speed: 0 });

  React.useEffect(() => {
    const uploadFile = async () => {
      try {
        // Prepare the data for the API, ensuring correct types.
        const jobRequestData: CreateJobRequest = {
          ...formData,
          generate_subtitles: formData.generate_subtitles === true || formData.generate_subtitles === 'true',
          generate_dubbing: formData.generate_dubbing === true || formData.generate_dubbing === 'true',
          subtitle_style: typeof formData.subtitle_style === 'object'
            ? JSON.stringify(formData.subtitle_style)
            : formData.subtitle_style,
        };

        const response = await createJobWithProgress(
          jobRequestData,
          file,
          // Updated callback to handle the progress object
          (newProgress) => {
            setProgress(newProgress);
          }
        );

        // When upload is complete
        onUploadComplete(response.job_id);
      } catch (error: any) {
        console.error('Upload failed:', error);
        onUploadError(error.response?.data?.detail || error.message || 'File upload failed');
      }
    };

    // Start upload immediately
    uploadFile();
  }, [file, formData, onUploadComplete, onUploadError]); // Added dependencies to useEffect

  return (
    <Box sx={{ width: '100%', mt: 3, mb: 3 }}>
      <Typography variant="subtitle1" noWrap>Uploading: {file.name}</Typography>
      <LinearProgress 
        variant="determinate" 
        value={progress.percentage} 
        sx={{ 
          height: 10, 
          borderRadius: 5,
          mt: 1
        }}
      />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
        <Typography variant="body2" color="text.secondary">
          {formatSpeed(progress.speed)}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {progress.percentage}%
        </Typography>
      </Box>
    </Box>
  );
};

export default FileUploader;