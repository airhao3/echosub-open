import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '../../services/api/apiClient';
import type { JobCreationResponse, JobStatusResponse } from '../../services/api/jobService';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert as MuiAlert,
  Paper as MuiPaper,
  Container,
  LinearProgress,
  Snackbar,
  AlertTitle,
  AlertProps as MuiAlertProps,
  LinearProgressProps,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  HourglassEmpty as HourglassEmptyIcon,
  ArrowBack as ArrowBackIcon,
  Timer as TimerIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import { formatDuration } from '../../types';

// --- TYPE DEFINITIONS ---

type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
type StepStatus = 'pending' | 'processing' | 'completed' | 'failed';

interface ProcessingStep {
  id: string;
  name: string;
  status: StepStatus;
  progress: number;
  details?: string;
}

interface JobProcessingState {
  videoTitle: string;
  status: JobStatus;
  steps: ProcessingStep[];
  overallProgress: number;
  statusMessage: string;
  videoUrl?: string;
  estimatedTimeRemaining?: number;
}

interface PendingUpload {
  file: File | null;
  videoUrl: string | null;
  fileUrl?: string;
  formData: any;
}

// --- STYLED COMPONENTS (Unchanged, for brevity) ---
const ProcessingPageContainer = styled(Container)(({ theme }) => ({ /* ... */ }));
const StyledPaper = styled(MuiPaper)(({ theme }) => ({ /* ... */ }));
const ProgressContainer = styled(Box)(({ theme }) => ({ /* ... */ }));
const StyledLinearProgress = styled(LinearProgress)<LinearProgressProps>(({ theme }) => ({ /* ... */ }));
const StepIconContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'active' && prop !== 'completed' && prop !== 'error',
})<{ active?: boolean; completed?: boolean; error?: boolean }>(({ theme, active, completed, error }) => ({ /* ... */ }));

const StyledAlert = React.forwardRef<HTMLDivElement, MuiAlertProps>((props, ref) => {
  return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});
StyledAlert.displayName = 'StyledAlert';

// --- HELPER FUNCTIONS ---

const mapStepStatus = (status: string | undefined): StepStatus => {
  if (!status) return 'pending';
  const normalizedStatus = status.toLowerCase();
  if (['completed', 'succeeded'].includes(normalizedStatus)) return 'completed';
  if (['failed', 'error'].includes(normalizedStatus)) return 'failed';
  if (['in_progress', 'processing', 'started'].includes(normalizedStatus)) return 'processing';
  return 'pending';
};

const getDefaultSteps = (): ProcessingStep[] => [
  { id: 'UPLOADING', name: '上传中', status: 'pending', progress: 0 },
  { id: 'TRANSCRIBING', name: '语音识别', status: 'pending', progress: 0 },
  { id: 'ANALYZING', name: '内容分析', status: 'pending', progress: 0 },
  { id: 'TRANSLATING', name: '翻译中', status: 'pending', progress: 0 },
  { id: 'GENERATING', name: '生成字幕', status: 'pending', progress: 0 },
  { id: 'FINALIZING', name: '完成处理', status: 'pending', progress: 0 },
];

const JOB_STEPS_CONFIG = getDefaultSteps();

// --- MAIN COMPONENT ---

const JobProcessingPage: React.FC = () => {
  const { jobId: paramJobId } = useParams<{ jobId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const [currentJobId, setCurrentJobId] = useState<number | 'new'>(() => {
    if (!paramJobId || paramJobId === 'new') {
      return 'new';
    }
    const id = parseInt(paramJobId, 10);
    return isNaN(id) ? 'new' : id;
  });

  const [jobStatus, setJobStatus] = useState<JobProcessingState>({
    status: 'pending',
    overallProgress: 0,
    statusMessage: 'Initializing...',
    videoTitle: '处理中',
    steps: JOB_STEPS_CONFIG,
  });

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
    open: false, message: '', severity: 'info'
  });
  
  const [pageError, setPageError] = useState<string | null>(null);

  // Refs to manage component lifecycle and prevent race conditions
  const jobCreationInProgress = useRef(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isMounted = useRef(true);

  // --- API AND STATE LOGIC ---

  const handleJobFailure = useCallback((errorMessage: string, failedStepId?: string) => {
    setPageError(errorMessage);
    setJobStatus(prev => ({
      ...prev,
      status: 'failed',
      statusMessage: `Job failed: ${errorMessage}`,
      steps: prev.steps.map(step =>
        failedStepId && step.id === failedStepId ? { ...step, status: 'failed', details: errorMessage } : step
      )
    }));
    setSnackbar({ open: true, message: errorMessage, severity: 'error' });
  }, []);

  const updateJobStateFromResponse = useCallback((statusData: JobStatusResponse) => {
    const stepNameMapping: Record<string, string> = {
      // Direct mappings
      'UPLOAD': 'UPLOADING',
      'TRANSLATING': 'TRANSLATING',
      
      // TRANSCRIBING step group (新规划)
      'AUDIO_PROCESSING': 'TRANSCRIBING',     // 视频分离音频 + 音频处理
      'TRANSCRIBING': 'TRANSCRIBING',         // 语音转录
      'SEGMENTING': 'TRANSCRIBING',           // 文本分割
      'TEXT_REFINEMENT': 'TRANSCRIBING',      // 文本精炼
      
      // ANALYZING step group (新规划)
      'ANALYZING': 'ANALYZING',               // 直接映射
      'SEMANTIC_ANALYSIS': 'ANALYZING',       // 语义分析/Summary
      'TERMINOLOGY_EXTRACTION': 'ANALYZING', // 术语提取
      
      // Backend-to-Frontend mappings (保持原有)
      'ALIGNING_SUBTITLES': 'GENERATING',     // 字幕生成
      'ALIGNING_TIMESTAMPS': 'GENERATING',    // 时间戳对齐
      'INTEGRATING': 'FINALIZING',            // 最终集成
      'VIDEO_COMPRESSING': 'FINALIZING',      // 视频压缩
      
      // Fallback mappings for consistency  
      'UPLOADING': 'UPLOADING',
      'GENERATING': 'GENERATING', 
      'FINALIZING': 'FINALIZING'
    };
  
    setJobStatus(prev => {
      const updatedSteps = [...prev.steps];
      const backendSteps = statusData.steps || [];
  
      // Group backend steps by frontend step for aggregated progress calculation
      const frontendStepProgress: Record<string, {steps: any[], maxProgress: number, latestStatus: string, latestDetails: string}> = {};
      
      backendSteps.forEach(backendStep => {
        const frontendStepId = stepNameMapping[backendStep.step_name.toUpperCase()];
        if (frontendStepId) {
          if (!frontendStepProgress[frontendStepId]) {
            frontendStepProgress[frontendStepId] = {
              steps: [],
              maxProgress: 0,
              latestStatus: 'pending',
              latestDetails: ''
            };
          }
          
          frontendStepProgress[frontendStepId].steps.push(backendStep);
          frontendStepProgress[frontendStepId].maxProgress = Math.max(
            frontendStepProgress[frontendStepId].maxProgress, 
            backendStep.progress ?? 0
          );
          
          // Use the most advanced status
          const currentStatus = mapStepStatus(backendStep.status);
          if (currentStatus === 'processing' || currentStatus === 'completed') {
            frontendStepProgress[frontendStepId].latestStatus = currentStatus;
            frontendStepProgress[frontendStepId].latestDetails = backendStep.details || frontendStepProgress[frontendStepId].latestDetails;
          }
        }
      });
      
      // Update frontend steps based on aggregated backend progress
      Object.entries(frontendStepProgress).forEach(([frontendStepId, aggregatedData]) => {
        const stepIndex = updatedSteps.findIndex(s => s.id === frontendStepId);
        
        if (stepIndex > -1) {
          // Don't override UPLOADING step if it's already completed from frontend upload
          if (frontendStepId === 'UPLOADING' && updatedSteps[stepIndex].status === 'completed') {
            return; // Skip updating this step
          }
          
          updatedSteps[stepIndex] = {
            ...updatedSteps[stepIndex],
            status: aggregatedData.latestStatus as StepStatus,
            progress: aggregatedData.maxProgress,
            details: aggregatedData.latestDetails || updatedSteps[stepIndex].details,
          };
        }
      });
  
      return {
        ...prev,
        videoTitle: `任务 #${statusData.job_id}`,
        status: statusData.status as JobStatus,
        overallProgress: statusData.progress ?? 0,
        statusMessage: statusData.status_message || statusData.message || prev.statusMessage,
        estimatedTimeRemaining: statusData.estimated_time ? parseInt(String(statusData.estimated_time), 10) : undefined,
        steps: updatedSteps,
      };
    });
  }, []);

  // --- PRIMARY LIFECYCLE EFFECT ---
  
  useEffect(() => {
    isMounted.current = true;
  
    const stopPolling = () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  
    const startPolling = (jobId: number) => {
      stopPolling(); // Ensure no multiple pollers
  
      let pollCount = 0;
      let consecutiveErrors = 0;
      const maxPolls = 360; // 30 minutes at 5-second intervals
      const maxConsecutiveErrors = 5;
      
      const poll = async () => {
        if (!isMounted.current) return;
        
        pollCount++;
        
        // Stop polling if we've exceeded maximum attempts
        if (pollCount > maxPolls) {
          stopPolling();
          handleJobFailure('Job polling timeout - processing took too long');
          return;
        }
        
        try {
          const response = await apiClient.get<JobStatusResponse>(`/api/v1/my/jobs/${jobId}/status`);
          if (!isMounted.current) return;
          
          // Reset error counter on successful request
          consecutiveErrors = 0;
          
          updateJobStateFromResponse(response.data);
  
          // Check completion criteria more strictly
          const steps = response.data.steps || [];
          const criticalSteps = steps.filter(s => ['TRANSCRIBING', 'TRANSLATING', 'GENERATING'].includes(s.step_name));
          const allCriticalStepsCompleted = criticalSteps.every(s => s.status === 'completed');
          const progressComplete = response.data.progress >= 100;
          const isReallyComplete = response.data.status === 'completed' && allCriticalStepsCompleted && progressComplete;
          
          const finalStatus = ['failed', 'cancelled'].includes(response.data.status) || isReallyComplete;
          if (finalStatus) {
            stopPolling();
            if (isReallyComplete) {
              setSnackbar({ open: true, message: 'Processing complete!', severity: 'success' });
              setTimeout(() => {
                if (isMounted.current) navigate(`/dashboard/preview/${jobId}`, { replace: true });
              }, 1500);
            } else if (['failed', 'cancelled'].includes(response.data.status)) {
              handleJobFailure(response.data.status_message || `Job ended with status: ${response.data.status}`);
            }
          }
        } catch (error: any) {
          console.error('Polling error:', error);
          
          // Check if it's an authentication error
          if (error.response?.status === 401) {
            stopPolling();
            console.warn('Authentication failed during job status polling');
            handleJobFailure('Authentication expired. Please log in again.');
            // The apiClient will automatically redirect to login page
            return;
          }
          
          // Check if it's a specific API error that we shouldn't retry
          if (error.response?.status === 404) {
            stopPolling();
            console.warn(`Job ${jobId} not found`);
            handleJobFailure('Job not found. It may have been deleted.');
            return;
          }
          
          consecutiveErrors++;
          console.warn(`Consecutive polling errors: ${consecutiveErrors}/${maxConsecutiveErrors}`);
          
          // Stop polling if too many consecutive errors
          if (consecutiveErrors >= maxConsecutiveErrors) {
            stopPolling();
            const errorMsg = error.response?.status 
              ? `Server error (${error.response.status}): Unable to check job status`
              : 'Too many polling errors - unable to check job status';
            handleJobFailure(errorMsg);
            return;
          }
        }
      };
  
      poll(); // Initial poll
      pollingIntervalRef.current = setInterval(poll, 5000);
    };
  
    const createNewJob = async (uploadData: PendingUpload) => {
      if (jobCreationInProgress.current) return;
      jobCreationInProgress.current = true;
  
      try {
        setJobStatus(prev => ({
          ...prev, statusMessage: 'Preparing to upload...',
          steps: prev.steps.map(s => s.id === 'UPLOADING' ? { ...s, status: 'processing', progress: 5 } : s)
        }));
  
        const formData = new FormData();
        Object.keys(uploadData.formData).forEach(key => {
            const value = uploadData.formData[key];
            if (value !== undefined && value !== null) {
                formData.append(key, typeof value === 'object' && !(value instanceof File) ? JSON.stringify(value) : value);
            }
        });
        if (uploadData.file) {
            formData.append('file', uploadData.file);
        }

        const response = await apiClient.post<JobCreationResponse>(
          '/api/v1/uploads/video',
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (event) => {
              const percent = event.total ? Math.round((event.loaded * 100) / event.total) : 0;
              setJobStatus(prev => ({
                ...prev,
                steps: prev.steps.map(s => s.id === 'UPLOADING' ? { ...s, progress: Math.min(percent, 99) } : s)
              }));
            },
            timeout: 300000, // 5 minutes
          }
        );
  
        if (!isMounted.current) return;
  
        if (response.data?.job_id && response.data?.user_job_number) {
          // Mark uploading as completed since upload finished successfully
          setJobStatus(prev => ({
            ...prev,
            statusMessage: 'Upload completed! Starting video processing...',
            steps: prev.steps.map(s => s.id === 'UPLOADING' ? { ...s, status: 'completed', progress: 100 } : s)
          }));
          
          setSnackbar({ open: true, message: 'Video processing has started.', severity: 'success' });
          // Use user_job_number for routing and polling (not job_id)
          navigate(`/dashboard/job-processing/${response.data.user_job_number}`, { replace: true, state: {} });
          setCurrentJobId(response.data.user_job_number);
          startPolling(response.data.user_job_number);
        } else {
          throw new Error('Server did not return a job ID or user job number.');
        }
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || err.message || 'An unknown error occurred during job creation.';
        if (isMounted.current) {
          handleJobFailure(errorMessage, 'UPLOADING');
        }
      } finally {
        jobCreationInProgress.current = false;
      }
    };
  
    if (currentJobId === 'new') {
      const pendingUpload = location.state?.pendingUpload as PendingUpload | undefined;
      if (pendingUpload) {
        createNewJob(pendingUpload);
      } else {
        setPageError("No job information found. Please start a new job from the dashboard.");
      }
    } else {
      startPolling(currentJobId);
    }
  
    return () => {
      isMounted.current = false;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentJobId, navigate, location.state]);
  
  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  if (pageError && jobStatus.status === 'failed') {
    return (
      <ProcessingPageContainer>
        <MuiAlert
          severity="error"
          sx={{ mb: 1.5, width: '100%', maxWidth: 'md' }}
          action={
            <Button color="inherit" size="small" onClick={() => navigate('/dashboard')} startIcon={<ArrowBackIcon />}>
              返回工作台
            </Button>
          }
        >
          <AlertTitle>任务失败</AlertTitle>
          {pageError}
        </MuiAlert>
      </ProcessingPageContainer>
    );
  }

  return (
    <Box
      sx={{
        background: (theme) => theme.palette.background.default,
        height: '100vh', overflow: 'auto',
        pb: 2,
        position: 'relative',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 50%)',
          zIndex: 0,
        }
      }}
    >
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1, pt: 1 }}>
        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleCloseSnackbar} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
          <StyledAlert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </StyledAlert>
        </Snackbar>
        
        <Box sx={{ width: '100%', mb: 1, textAlign: 'center' }}>
          <Typography 
            variant="h5" 
            component="h1" 
            gutterBottom 
            sx={{
              fontWeight: 700,
              color: 'text.primary',
              mb: 1
            }}
          >
            {jobStatus.videoTitle}
          </Typography>
          <Typography variant="body1" sx={{ color: 'text.secondary', mb: 2 }}>
            {jobStatus.statusMessage}
          </Typography>
        </Box>

        <Box
          sx={{
            background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
            backdropFilter: 'blur(20px)',
            borderRadius: '24px',
            border: '1px solid rgba(255,255,255,0.3)',
            overflow: 'hidden',
            position: 'relative',
            boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
            p: 2,
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'linear-gradient(135deg, rgba(0,122,255,0.05) 0%, rgba(77,163,255,0.05) 100%)',
              zIndex: 0,
            }
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700} sx={{ 
                  background: 'linear-gradient(45deg, #007AFF, #4DA3FF)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}>
                  处理进度
                </Typography>
                <Box sx={{
                  background: 'linear-gradient(135deg, #007AFF, #4DA3FF)',
                  borderRadius: '16px',
                  px: 3,
                  py: 1,
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '1.2rem',
                  boxShadow: '0 4px 12px rgba(0,122,255,0.3)',
                }}>
                  {Math.round(jobStatus.overallProgress)}%
                </Box>
              </Box>
              
              <Box sx={{ 
                height: 6,
                borderRadius: '12px',
                background: 'linear-gradient(90deg, rgba(0,122,255,0.1) 0%, rgba(77,163,255,0.1) 100%)',
                overflow: 'hidden',
                position: 'relative',
                border: '1px solid rgba(255,255,255,0.2)',
                boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.1)',
              }}>
                <Box sx={{
                  height: '100%',
                  width: `${jobStatus.overallProgress}%`,
                  background: 'linear-gradient(90deg, #007AFF 0%, #4DA3FF 100%)',
                  borderRadius: '12px',
                  transition: 'width 0.3s ease',
                  boxShadow: '0 0 12px rgba(0,122,255,0.4)',
                  position: 'relative',
                  '&::after': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'linear-gradient(90deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.3) 100%)',
                    borderRadius: '12px',
                  }
                }} />
              </Box>
              
              {jobStatus.estimatedTimeRemaining && (
                <Box sx={{ display: 'flex', alignItems: 'center', mt: 2, color: 'text.secondary', fontSize: '0.9rem' }}>
                  <TimerIcon fontSize="small" sx={{ mr: 1, color: '#007AFF' }} />
                  预计剩余时间: <strong style={{ marginLeft: '8px', color: '#007AFF' }}>{formatDuration(jobStatus.estimatedTimeRemaining)}</strong>
                </Box>
              )}
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="h6" sx={{ 
                mb: 1.5, 
                fontWeight: 700,
                color: 'text.primary',
                display: 'flex',
                alignItems: 'center',
                gap: 1
              }}>
                <Box sx={{
                  width: 4,
                  height: 24,
                  background: 'linear-gradient(135deg, #007AFF, #4DA3FF)',
                  borderRadius: '2px'
                }} />
                处理步骤
              </Typography>
              
              {jobStatus.steps.map((step, index) => {
                const isProcessing = step.status === 'processing';
                const isCompleted = step.status === 'completed';
                const isFailed = step.status === 'failed';
                const isActive = isProcessing || isCompleted;
                
                return (
                  <Box 
                    key={step.id} 
                    sx={{ 
                      mb: 1, 
                      display: 'flex', 
                      alignItems: 'flex-start',
                      p: 1.5,
                      borderRadius: '16px',
                      background: isActive 
                        ? 'linear-gradient(135deg, rgba(0,122,255,0.08), rgba(77,163,255,0.08))' 
                        : 'linear-gradient(135deg, rgba(0,0,0,0.02), rgba(0,0,0,0.01))',
                      border: '1px solid',
                      borderColor: isCompleted 
                        ? 'rgba(34,197,94,0.3)' 
                        : isProcessing 
                        ? 'rgba(0,122,255,0.3)' 
                        : isFailed 
                        ? 'rgba(239,68,68,0.3)'
                        : 'rgba(0,0,0,0.1)',
                      opacity: isActive || isProcessing ? 1 : 0.6,
                      position: 'relative',
                      '&::before': isActive ? {
                        content: '""',
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: 4,
                        background: isCompleted 
                          ? 'linear-gradient(135deg, #22c55e, #16a34a)'
                          : isProcessing 
                          ? 'linear-gradient(135deg, #007AFF, #4DA3FF)'
                          : 'linear-gradient(135deg, #ef4444, #dc2626)',
                        borderRadius: '0 2px 2px 0'
                      } : {},
                    }}
                  >
                    <Box sx={{
                      width: 48,
                      height: 32,
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      mr: 1.5,
                      background: isCompleted 
                        ? 'linear-gradient(135deg, #22c55e, #16a34a)'
                        : isProcessing 
                        ? 'linear-gradient(135deg, #007AFF, #4DA3FF)'
                        : isFailed 
                        ? 'linear-gradient(135deg, #ef4444, #dc2626)'
                        : 'linear-gradient(135deg, #e5e7eb, #d1d5db)',
                      color: isActive || isFailed ? 'white' : '#6b7280',
                      boxShadow: isActive ? '0 4px 12px rgba(0,0,0,0.15)' : '0 2px 4px rgba(0,0,0,0.1)',
                    }}>
                      {isCompleted ? <CheckCircleIcon fontSize="medium" /> :
                       isFailed ? <ErrorIcon fontSize="medium" /> :
                       isProcessing ? <CircularProgress size={24} color="inherit" sx={{ color: 'white' }} /> :
                       <HourglassEmptyIcon fontSize="medium" />}
                    </Box>
                    
                    <Box sx={{ flex: 1, pt: 0.5 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="h6" sx={{ 
                          fontWeight: isActive ? 700 : 500, 
                          color: isFailed ? '#ef4444' : 'text.primary'
                        }}>
                          {step.name}
                        </Typography>
                        <Box sx={{
                          px: 2,
                          py: 0.5,
                          borderRadius: '8px',
                          background: 'rgba(0,0,0,0.05)',
                          fontSize: '0.875rem',
                          fontWeight: 600,
                          color: 'text.secondary'
                        }}>
                          {Math.round(step.progress)}%
                        </Box>
                      </Box>
                      
                      {step.details && (
                        <Typography variant="body2" sx={{ 
                          mt: 1, 
                          color: isFailed ? '#dc2626' : 'text.secondary',
                          fontStyle: 'italic'
                        }}>
                          {step.details}
                        </Typography>
                      )}
                      
                      {isProcessing && (
                        <Box sx={{ mt: 2, width: '100%' }}>
                          <Box sx={{ 
                            height: 6,
                            borderRadius: '6px',
                            background: 'rgba(0,122,255,0.1)',
                            overflow: 'hidden',
                            position: 'relative'
                          }}>
                            <Box sx={{
                              height: '100%',
                              width: `${step.progress}%`,
                              background: 'linear-gradient(90deg, #007AFF 0%, #4DA3FF 100%)',
                              borderRadius: '6px',
                              transition: 'width 0.3s ease',
                            }} />
                          </Box>
                        </Box>
                      )}
                    </Box>
                  </Box>
                );
              })}
            </Box>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'center', gap: 1.5, mt: 2, width: '100%' }}>
          <Button 
            variant="outlined" 
            onClick={() => navigate('/dashboard')} 
            startIcon={<ArrowBackIcon />}
            sx={{
              borderRadius: '16px',
              px: 4,
              py: 1.5,
              fontSize: '1rem',
              fontWeight: 600,
              borderWidth: 2,
              borderColor: 'rgba(255,255,255,0.4)',
              color: 'white',
              backdropFilter: 'blur(10px)',
              background: 'rgba(255,255,255,0.1)',
              '&:hover': {
                borderWidth: 2,
                borderColor: 'rgba(255,255,255,0.6)',
                backgroundColor: 'rgba(255,255,255,0.2)',
                
                boxShadow: '0 8px 25px rgba(0,0,0,0.15)',
              },
            }}
          >
            Back to Dashboard
          </Button>
          {jobStatus.status === 'completed' && typeof currentJobId === 'number' && (
            <Button 
              variant="contained" 
              color="primary" 
              onClick={() => navigate(`/dashboard/preview/${currentJobId}`)} 
              startIcon={<VisibilityIcon />}
              sx={{
                borderRadius: '16px',
                px: 4,
                py: 1.5,
                fontSize: '1rem',
                fontWeight: 700,
                background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
                boxShadow: '0 8px 25px rgba(34,197,94,0.3)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)',
                  
                  boxShadow: '0 12px 35px rgba(34,197,94,0.4)',
                },
              }}
            >
              Preview Video
            </Button>
          )}
        </Box>
      </Container>
    </Box>
  );
};

export default JobProcessingPage;