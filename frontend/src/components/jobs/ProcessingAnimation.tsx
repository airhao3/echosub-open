import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Step,
  Stepper,
  StepLabel,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  Movie as MovieIcon,
  AudioFile as AudioIcon,
  Subtitles as SubtitlesIcon,
  Translate as TranslateIcon,
  Splitscreen as SplitIcon,
  Done as DoneIcon,
  MergeType as MergeIcon,
  Analytics as AnalyzeIcon,
  Audiotrack as AudioTrackIcon,
  Save as SaveIcon,
} from '@mui/icons-material';

interface ProcessingStep {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  colorClass: string;
}

interface ProcessingAnimationProps {
  status: string;
  progress?: number; // Overall progress (0-100)
  currentStep?: string;
  startTime?: string;
  // Job details that might affect the animation
  hasSubtitles?: boolean;
  hasDubbing?: boolean;
  sourceLanguage?: string;
  targetLanguage?: string;
}

const ProcessingAnimation: React.FC<ProcessingAnimationProps> = ({
  status,
  progress = 0,
  currentStep = '',
  startTime = '',
  hasSubtitles = true,
  hasDubbing = false,
  sourceLanguage = 'en',
  targetLanguage = 'zh',
}) => {
  const [activeStep, setActiveStep] = useState<number>(0);

  // Define processing pipeline steps with simplified structure
  const processingSteps: ProcessingStep[] = [
    {
      id: 'initialize',
      label: 'Initialize',
      description: 'Preparing video',
      icon: <MovieIcon />,
      colorClass: 'text-blue-500',
    },
    {
      id: 'analyze',
      label: 'Analyze',
      description: 'Analyzing content',
      icon: <AnalyzeIcon />,
      colorClass: 'text-indigo-500',
    },
    {
      id: 'split',
      label: 'Extract',
      description: 'Extracting audio',
      icon: <SplitIcon />,
      colorClass: 'text-purple-500',
    },
    {
      id: 'transcribe',
      label: 'Transcribe',
      description: `Speech recognition (${sourceLanguage === 'auto' ? 'auto' : sourceLanguage})`,
      icon: <AudioTrackIcon />,
      colorClass: 'text-teal-500',
    },
    {
      id: 'translate',
      label: 'Translate',
      description: `Translating to ${targetLanguage}`,
      icon: <TranslateIcon />,
      colorClass: 'text-green-500',
    },
    {
      id: 'subtitle',
      label: 'Subtitles',
      description: 'Creating subtitles',
      icon: <SubtitlesIcon />,
      colorClass: 'text-amber-500',
    },
    {
      id: 'dubbing',
      label: 'Dubbing',
      description: 'Voice dubbing',
      icon: <AudioIcon />,
      colorClass: 'text-orange-500',
    },
    {
      id: 'embed',
      label: 'Embed',
      description: 'Adding subtitles',
      icon: <MergeIcon />,
      colorClass: 'text-red-500',
    },
    {
      id: 'save',
      label: 'Save',
      description: 'Saving files',
      icon: <SaveIcon />,
      colorClass: 'text-cyan-500',
    },
    {
      id: 'complete',
      label: 'Complete',
      description: 'Completed',
      icon: <DoneIcon />,
      colorClass: 'text-emerald-500',
    },
  ];

  // Filter out dubbing step if not needed
  const filteredSteps = hasDubbing 
    ? processingSteps 
    : processingSteps.filter(step => step.id !== 'dubbing');

  // Update active step when component mounts or when status/currentStep changes
  useEffect(() => {
    // Maps backend step names to our step IDs
    const stepMapping: Record<string, string> = {
      'INITIALIZING': 'initialize',
      'ANALYZING': 'analyze',
      'EXTRACTING_AUDIO': 'split',
      'TRANSCRIBING': 'transcribe',
      'TRANSLATING': 'translate',
      'GENERATING_SUBTITLES': 'subtitle',
      'GENERATING_DUBBING': 'dubbing',
      'EMBEDDING_SUBTITLES': 'embed',
      'SAVING': 'save',
      'COMPLETE': 'complete'
    };

    if (status === 'processing') {
      const currentStepId = stepMapping[currentStep] || 'initialize';
      const stepIndex = filteredSteps.findIndex(s => s.id === currentStepId);
      setActiveStep(stepIndex >= 0 ? stepIndex : 0);
    } else if (status === 'completed') {
      // Set to the last step when completed
      setActiveStep(filteredSteps.length - 1);
    }
  }, [status, currentStep, filteredSteps]);

  // Main render function
  return (
    <Paper elevation={1} className="p-4">
      {/* Simple progress indicator - no redundant labels */}
      <Box mb={3}>
        <Box display="flex" justifyContent="flex-end" mb={1}>
          <Typography variant="subtitle1" fontWeight="bold">
            {Math.round(progress)}%
          </Typography>
        </Box>
        <LinearProgress 
          variant="determinate" 
          value={progress} 
          className="h-2 rounded-full" 
          color={status === 'failed' ? 'error' : 'primary'}
        />
      </Box>

      {/* Processing pipeline visualization */}
      <Box position="relative" className="my-8">
        <Stepper activeStep={activeStep} alternativeLabel>
          {filteredSteps.map((step, index) => {
            const isActive = index === activeStep;
            const isCompleted = index < activeStep;
            
            return (
              <Step key={step.id}>
                <StepLabel
                  StepIconProps={{
                    icon: (
                      <Tooltip title={step.description}>
                        <Box 
                          className={`flex items-center justify-center rounded-full p-2 ${isActive ? step.colorClass : isCompleted ? 'text-green-500' : 'text-gray-400'}`}
                        >
                          {isCompleted ? <DoneIcon /> : step.icon}
                        </Box>
                      </Tooltip>
                    ),
                  }}
                >
                  <Typography 
                    variant="body2" 
                    className={isActive ? step.colorClass : isCompleted ? 'text-green-500' : 'text-gray-500'}
                    fontWeight={isActive ? 'bold' : 'normal'}
                  >
                    {step.label}
                  </Typography>
                </StepLabel>
              </Step>
            );
          })}
        </Stepper>
      </Box>

      {/* Display current step details */}
      {status === 'processing' && filteredSteps[activeStep] && (
        <Box className="border border-gray-200 rounded-lg p-3 bg-gray-50 mt-2">
          <Box display="flex" alignItems="center">
            <Box className={`mr-3 ${filteredSteps[activeStep].colorClass}`}>
              {filteredSteps[activeStep].icon}
            </Box>
            <Typography variant="body2" color="textSecondary">
              {filteredSteps[activeStep].description}
            </Typography>
          </Box>
        </Box>
      )}

      {status === 'failed' && (
        <Box className="border border-red-200 rounded-lg p-3 bg-red-50 text-red-700 mt-2">
          <Typography variant="subtitle1" fontWeight="bold">
            Failed
          </Typography>
          <Typography variant="body2">
            Error occurred. Please try again or contact support.
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default ProcessingAnimation;
