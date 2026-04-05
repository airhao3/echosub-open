import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Typography,
  Paper,
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Grid,
  Alert,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Movie as MovieIcon,
  Cancel as CancelIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Videocam as VideocamIcon,
  Timer as TimerIcon,
  Speed as SpeedIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';

interface UploadStats {
  uploadSpeed: number; // bytes per second
  remainingTime: number; // seconds
  elapsedTime: number; // seconds
  averageSpeed: number; // bytes per second
}

interface EnhancedUploaderProps {
  onFileSelected: (file: File) => void;
  onUploadProgress?: (progress: number) => void;
  onUploadComplete?: () => void;
  onUploadFailed?: (error: Error) => void;
  onUploadCancelled?: () => void;
  maxSizeMB?: number;
  allowedFormats?: string[];
  simulateUpload?: boolean; // For demo/testing purposes
}

const DEFAULT_ALLOWED_FORMATS = ['video/mp4', 'video/mov', 'video/avi', 'video/mkv', 'video/webm'];

// Default max size from environment variable or fallback to 500MB
const DEFAULT_MAX_UPLOAD_SIZE_MB = process.env.REACT_APP_MAX_UPLOAD_SIZE_MB 
  ? parseInt(process.env.REACT_APP_MAX_UPLOAD_SIZE_MB, 10)
  : 500;

const EnhancedUploader: React.FC<EnhancedUploaderProps> = ({
  onFileSelected,
  onUploadProgress,
  onUploadComplete,
  onUploadFailed,
  onUploadCancelled,
  maxSizeMB = DEFAULT_MAX_UPLOAD_SIZE_MB,
  allowedFormats = DEFAULT_ALLOWED_FORMATS,
  simulateUpload = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadStats, setUploadStats] = useState<UploadStats>({
    uploadSpeed: 0,
    remainingTime: 0,
    elapsedTime: 0,
    averageSpeed: 0,
  });
  const [uploadStartTime, setUploadStartTime] = useState<number | null>(null);
  const [lastUploadedBytes, setLastUploadedBytes] = useState<number>(0);
  const [totalUploadedBytes, setTotalUploadedBytes] = useState<number>(0);
  const [uploadController, setUploadController] = useState<AbortController | null>(null);

  // File selection and validation
  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError(null);
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];

    // Validate file size
    if (file.size > maxSizeMB * 1024 * 1024) {
      setError(`File size exceeds the maximum limit of ${maxSizeMB} MB`);
      return;
    }

    // Validate file format
    if (allowedFormats.length > 0 && !allowedFormats.includes(file.type)) {
      setError(`File format not supported. Please upload: ${allowedFormats.join(', ')}`);
      return;
    }

    // Create a preview for video
    const objectUrl = URL.createObjectURL(file);
    setFilePreview(objectUrl);
    setSelectedFile(file);
    onFileSelected(file);

    // Clean up preview URL when component unmounts
    return () => URL.revokeObjectURL(objectUrl);
  }, [maxSizeMB, allowedFormats, onFileSelected]);

  // Dropzone configuration
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'video/*': allowedFormats,
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  // Format bytes to human-readable
  const formatBytes = (bytes: number, decimals: number = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  // Format time to human-readable
  const formatTime = (seconds: number) => {
    if (!seconds || !isFinite(seconds)) return 'Calculating...';
    if (seconds < 60) return `${Math.round(seconds)} seconds`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Simulate upload for demo purposes
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (simulateUpload && selectedFile && !isUploading && uploadProgress === 0) {
      setIsUploading(true);
      setUploadStartTime(Date.now());
      setTotalUploadedBytes(0);
      setLastUploadedBytes(0);
      
      const totalSize = selectedFile.size;
      const simulationDuration = 15000; // 15 seconds for complete simulation
      const updateInterval = 100; // 100ms updates
      const stepsCount = simulationDuration / updateInterval;
      const bytesPerStep = totalSize / stepsCount;
      
      let step = 0;
      
      interval = setInterval(() => {
        step++;
        const simProgress = Math.min(100, (step / stepsCount) * 100);
        const uploadedBytes = Math.min(totalSize, step * bytesPerStep);
        
        // Calculate upload stats
        const elapsedMs = Date.now() - (uploadStartTime || Date.now());
        const elapsedSeconds = elapsedMs / 1000;
        const bytesPerSecond = uploadedBytes / elapsedSeconds;
        const remainingBytes = totalSize - uploadedBytes;
        const remainingTime = bytesPerSecond > 0 ? remainingBytes / bytesPerSecond : 0;

        const bytesSinceLastUpdate = uploadedBytes - lastUploadedBytes;
        const instantSpeed = bytesSinceLastUpdate / (updateInterval / 1000);
        
        setUploadProgress(simProgress);
        setTotalUploadedBytes(uploadedBytes);
        setLastUploadedBytes(uploadedBytes);
        
        setUploadStats({
          uploadSpeed: instantSpeed,
          remainingTime,
          elapsedTime: elapsedSeconds,
          averageSpeed: bytesPerSecond,
        });
        
        if (onUploadProgress) {
          onUploadProgress(simProgress);
        }
        
        if (simProgress >= 100) {
          setIsUploading(false);
          if (onUploadComplete) onUploadComplete();
          clearInterval(interval);
        }
      }, updateInterval);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [simulateUpload, selectedFile, isUploading, uploadProgress, uploadStartTime, onUploadProgress, onUploadComplete]);

  // Real upload implementation (to be replaced with actual upload code)
  const startUpload = useCallback(() => {
    if (!selectedFile || isUploading) return;
    
    // Initialize upload metrics
    setIsUploading(true);
    setUploadProgress(0);
    setUploadStartTime(Date.now());
    setTotalUploadedBytes(0);
    setLastUploadedBytes(0);
    
    if (simulateUpload) return; // Skip actual upload if in simulation mode
    
    // Create abort controller for cancellation
    const controller = new AbortController();
    setUploadController(controller);
    
    // Implement your actual upload logic here
    // This is a placeholder for demonstration
    // In a real implementation, you would use the API client to upload the file
    
    // For now, let's simulate progress with a timer
    let progress = 0;
    const interval = setInterval(() => {
      progress += 5;
      const simulatedBytes = (progress / 100) * selectedFile.size;
      
      // Calculate upload stats
      const elapsedMs = Date.now() - (uploadStartTime || Date.now());
      const elapsedSeconds = elapsedMs / 1000;
      const bytesPerSecond = simulatedBytes / elapsedSeconds;
      const remainingBytes = selectedFile.size - simulatedBytes;
      const remainingTime = bytesPerSecond > 0 ? remainingBytes / bytesPerSecond : 0;

      const bytesSinceLastUpdate = simulatedBytes - lastUploadedBytes;
      const instantSpeed = bytesSinceLastUpdate / 0.5; // 500ms update interval
      
      setUploadProgress(progress);
      setTotalUploadedBytes(simulatedBytes);
      setLastUploadedBytes(simulatedBytes);
      
      setUploadStats({
        uploadSpeed: instantSpeed,
        remainingTime,
        elapsedTime: elapsedSeconds,
        averageSpeed: bytesPerSecond,
      });
      
      if (onUploadProgress) {
        onUploadProgress(progress);
      }
      
      if (progress >= 100) {
        clearInterval(interval);
        setIsUploading(false);
        if (onUploadComplete) onUploadComplete();
      }
    }, 500);
    
    // Handle cancellation
    controller.signal.addEventListener('abort', () => {
      clearInterval(interval);
      setIsUploading(false);
      setUploadProgress(0);
      setError('Upload cancelled');
      if (onUploadCancelled) onUploadCancelled();
    });
    
    return () => {
      clearInterval(interval);
      controller.abort();
    };
  }, [selectedFile, isUploading, simulateUpload, uploadStartTime, onUploadProgress, onUploadComplete, onUploadCancelled]);

  const cancelUpload = useCallback(() => {
    if (uploadController) {
      uploadController.abort();
      setUploadController(null);
    }
  }, [uploadController]);

  const resetUpload = useCallback(() => {
    setSelectedFile(null);
    setFilePreview(null);
    setUploadProgress(0);
    setError(null);
    setIsUploading(false);
    setUploadStats({
      uploadSpeed: 0,
      remainingTime: 0,
      elapsedTime: 0,
      averageSpeed: 0,
    });
    setUploadStartTime(null);
    setTotalUploadedBytes(0);
    setLastUploadedBytes(0);
    if (uploadController) {
      uploadController.abort();
      setUploadController(null);
    }
  }, [uploadController]);

  return (
    <Paper elevation={3} className="p-5 mb-4">
      <Typography variant="h6" gutterBottom className="flex items-center">
        <VideocamIcon className="mr-2" /> Video Uploader
      </Typography>
      
      {!selectedFile ? (
        <div
          {...getRootProps()}
          className={`mt-4 border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}
            ${isDragReject ? 'border-red-500 bg-red-50' : ''}
            ${error ? 'border-red-500' : ''}
          `}
        >
          <input {...getInputProps()} />
          <CloudUploadIcon sx={{ fontSize: 48 }} className="text-gray-400 mb-2" />
          
          {isDragActive ? (
            <Typography variant="body1" className="text-blue-600">
              Drop the video file here ...
            </Typography>
          ) : (
            <>
              <Typography variant="body1">
                Drag & drop your video file here, or click to select
              </Typography>
              <Typography variant="body2" color="textSecondary" className="mt-2">
                Supported formats: {allowedFormats.join(', ')}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Maximum size: {maxSizeMB} MB
              </Typography>
            </>
          )}
          
          {error && (
            <Alert severity="error" className="mt-4">
              {error}
            </Alert>
          )}
        </div>
      ) : (
        <Box className="mt-4">
          {/* File preview */}
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} sm={4} md={3}>
              <Box className="relative bg-gray-900 rounded-lg overflow-hidden aspect-video">
                <video
                  src={filePreview || undefined}
                  className="w-full h-full object-cover"
                  controls={false}
                />
                <Box 
                  className="absolute inset-0 flex items-center justify-center"
                  sx={{ backgroundColor: 'rgba(0,0,0,0.3)' }}
                >
                  <MovieIcon sx={{ fontSize: 40 }} className="text-white opacity-80" />
                </Box>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={8} md={9}>
              <Typography variant="subtitle1" className="font-medium truncate mb-1">
                {selectedFile.name}
              </Typography>
              
              <Typography variant="body2" color="textSecondary" className="mb-2">
                {formatBytes(selectedFile.size)} • {selectedFile.type || 'Unknown format'}
              </Typography>
              
              {/* Upload progress and controls */}
              <Box className="mt-3">
                {isUploading ? (
                  <>
                    <Box className="flex justify-between mb-1">
                      <Typography variant="body2">
                        Uploading: {Math.round(uploadProgress)}%
                      </Typography>
                      <Typography variant="body2">
                        {formatBytes(totalUploadedBytes)} of {formatBytes(selectedFile.size)}
                      </Typography>
                    </Box>
                    
                    <LinearProgress 
                      variant="determinate" 
                      value={uploadProgress} 
                      className="h-2 rounded-full mb-3" 
                    />
                    
                    <Box className="grid grid-cols-3 gap-3 mb-3">
                      <Box className="flex items-center">
                        <Tooltip title="Upload Speed">
                          <SpeedIcon fontSize="small" className="text-blue-500 mr-2" />
                        </Tooltip>
                        <Typography variant="body2">
                          {formatBytes(uploadStats.uploadSpeed)}/s
                        </Typography>
                      </Box>
                      
                      <Box className="flex items-center">
                        <Tooltip title="Remaining Time">
                          <TimerIcon fontSize="small" className="text-orange-500 mr-2" />
                        </Tooltip>
                        <Typography variant="body2">
                          {formatTime(uploadStats.remainingTime)}
                        </Typography>
                      </Box>
                      
                      <Box className="flex items-center">
                        <Tooltip title="Elapsed Time">
                          <AnalyticsIcon fontSize="small" className="text-green-500 mr-2" />
                        </Tooltip>
                        <Typography variant="body2">
                          {formatTime(uploadStats.elapsedTime)}
                        </Typography>
                      </Box>
                    </Box>
                    
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={<CancelIcon />}
                      onClick={cancelUpload}
                      className="mt-2"
                    >
                      Cancel Upload
                    </Button>
                  </>
                ) : uploadProgress === 100 ? (
                  <Box className="flex items-center">
                    <CheckCircleIcon className="text-green-500 mr-2" />
                    <Typography variant="body1" className="text-green-700">
                      Upload complete!
                    </Typography>
                    <Button
                      variant="text"
                      size="small"
                      onClick={resetUpload}
                      className="ml-auto"
                    >
                      Upload another file
                    </Button>
                  </Box>
                ) : (
                  <Box className="flex flex-wrap gap-2">
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<CloudUploadIcon />}
                      onClick={startUpload}
                    >
                      Start Upload
                    </Button>
                    
                    <Button
                      variant="outlined"
                      onClick={resetUpload}
                    >
                      Remove File
                    </Button>
                  </Box>
                )}
              </Box>
            </Grid>
          </Grid>
        </Box>
      )}
    </Paper>
  );
};

export default EnhancedUploader;
