import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  Box,
  Typography,
  Slider,
  IconButton,
  Tooltip,
  Chip,
  Alert,
  Divider,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Timer as TimerIcon,
  RestoreFromTrash as ResetIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  SlowMotionVideo as SlowMotionIcon,
  Speed as SpeedIcon,
  Pause as PauseIcon,
} from '@mui/icons-material';

interface TimeAdjustmentDialogProps {
  open: boolean;
  subtitle: {
    id: string;
    text: string;
    startTime: number;
    endTime: number;
  } | null;
  currentVideoTime: number;
  videoDuration?: number;
  onClose: () => void;
  onSave: (newStartTime: number, newEndTime: number) => void;
  onSeekTo: (time: number) => void;
  onPlaySpeedChange?: (speed: number) => void;
  onPlayPause?: () => void;
  isPlaying?: boolean;
}

const TimeAdjustmentDialog: React.FC<TimeAdjustmentDialogProps> = ({
  open,
  subtitle,
  currentVideoTime,
  videoDuration,
  onClose,
  onSave,
  onSeekTo,
  onPlaySpeedChange,
  onPlayPause,
  isPlaying = false,
}) => {
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(0);
  const [startTimeInput, setStartTimeInput] = useState('');
  const [endTimeInput, setEndTimeInput] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  
  // Validate time range
  const validateTimes = (start: number, end: number): string | null => {
    if (start < 0) {
      return 'Start time cannot be less than 0';
    }
    if (start >= end) {
      return 'Start time must be less than end time';
    }
    if (videoDuration && end > videoDuration) {
      return `End time cannot exceed video duration ${formatTimeForDisplay(videoDuration)}`;
    }
    if (videoDuration && start > videoDuration) {
      return `Start time cannot exceed video duration ${formatTimeForDisplay(videoDuration)}`;
    }
    if (end - start < 0.1) {
      return 'Subtitle duration must be at least 0.1 seconds';
    }
    return null;
  };

  // Initialize times
  useEffect(() => {
    if (subtitle) {
      setStartTime(subtitle.startTime);
      setEndTime(subtitle.endTime);
      setStartTimeInput(formatTimeForInput(subtitle.startTime));
      setEndTimeInput(formatTimeForInput(subtitle.endTime));
      setValidationError(null);
    }
  }, [subtitle]);

  // Format time for input fields (HH:MM:SS.mmm)
  const formatTimeForInput = (timeInSeconds: number): string => {
    const hours = Math.floor(timeInSeconds / 3600);
    const minutes = Math.floor((timeInSeconds % 3600) / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  // Format time for display (MM:SS.mmm)
  const formatTimeForDisplay = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  // Parse time from input
  const parseTimeInput = (timeStr: string): number | null => {
    try {
      const pattern = /^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$/;
      const match = timeStr.match(pattern);
      
      if (!match) return null;
      
      const hours = parseInt(match[1], 10);
      const minutes = parseInt(match[2], 10);
      const seconds = parseInt(match[3], 10);
      const milliseconds = parseInt(match[4], 10);
      
      return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000;
    } catch (e) {
      return null;
    }
  };


  // Handle start time change
  const handleStartTimeChange = (value: number) => {
    setStartTime(value);
    setStartTimeInput(formatTimeForInput(value));
    
    // If new start time exceeds end time, adjust end time automatically
    let newEndTime = endTime;
    if (value >= endTime) {
      newEndTime = value + 1; // Default to 1 second duration
      setEndTime(newEndTime);
      setEndTimeInput(formatTimeForInput(newEndTime));
    }
    
    const error = validateTimes(value, newEndTime);
    setValidationError(error);
  };

  // Handle end time change
  const handleEndTimeChange = (value: number) => {
    setEndTime(value);
    setEndTimeInput(formatTimeForInput(value));
    const error = validateTimes(startTime, value);
    setValidationError(error);
  };

  // Handle input field changes
  const handleStartTimeInputChange = (value: string) => {
    setStartTimeInput(value);
    const parsed = parseTimeInput(value);
    if (parsed !== null) {
      setStartTime(parsed);
      const error = validateTimes(parsed, endTime);
      setValidationError(error);
    }
  };

  const handleEndTimeInputChange = (value: string) => {
    setEndTimeInput(value);
    const parsed = parseTimeInput(value);
    if (parsed !== null) {
      setEndTime(parsed);
      const error = validateTimes(startTime, parsed);
      setValidationError(error);
    }
  };

  // Set to current video time
  const setToCurrentTime = (type: 'start' | 'end') => {
    if (type === 'start') {
      handleStartTimeChange(currentVideoTime);
    } else {
      handleEndTimeChange(currentVideoTime);
    }
  };

  // Reset times
  const resetTimes = () => {
    if (subtitle) {
      handleStartTimeChange(subtitle.startTime);
      handleEndTimeChange(subtitle.endTime);
    }
  };

  // Save changes
  const handleSave = () => {
    if (!validationError) {
      onSave(startTime, endTime);
      onClose();
    }
  };

  // Preview playback
  const handlePreview = () => {
    onSeekTo(startTime);
  };

  // Playback speed control
  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (onPlaySpeedChange) {
      onPlaySpeedChange(speed);
    }
  };

  // Toggle play/pause
  const handlePlayPause = () => {
    if (onPlayPause) {
      onPlayPause();
    }
  };

  // Slow preview for a specific time point
  const handleSlowPreview = (time: number) => {
    // Set to slow speed first
    handleSpeedChange(0.5);
    // Then seek to the time point
    onSeekTo(time);
    // If playback control is available, start playing
    if (onPlayPause && !isPlaying) {
      setTimeout(() => onPlayPause(), 100);
    }
  };

  if (!subtitle) return null;

  const duration = endTime - startTime;
  const maxTime = videoDuration 
    ? Math.min(videoDuration, Math.max(subtitle.endTime + 10, currentVideoTime + 10))
    : Math.max(subtitle.endTime + 10, currentVideoTime + 10); // Consider video duration limit

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: '16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)'
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        pb: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TimerIcon color="primary" />
          <Typography variant="h6">Adjust Subtitle Time</Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2 }}>
        {/* Subtitle Content Preview */}
        <Box sx={{ 
          mb: 3, 
          p: 2, 
          bgcolor: 'grey.50', 
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'grey.200'
        }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
            Subtitle Content
          </Typography>
          <Typography variant="body1" sx={{ fontWeight: 500 }}>
            {subtitle.text}
          </Typography>
        </Box>

        {/* Time Adjustment Controls */}
        <Grid container spacing={3}>
          {/* Start Time */}
          <Grid item xs={6}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
              Start Time
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                value={startTimeInput}
                onChange={(e) => handleStartTimeInputChange(e.target.value)}
                placeholder="00:00:00.000"
                sx={{ flex: 1 }}
              />
              <Tooltip title="Set to current playback time">
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setToCurrentTime('start')}
                  sx={{ borderRadius: '8px', minWidth: 'auto', px: 1 }}
                >
                  <TimerIcon fontSize="small" />
                </Button>
              </Tooltip>
            </Box>
            <Slider
              value={startTime}
              onChange={(_, value) => handleStartTimeChange(value as number)}
              min={0}
              max={maxTime}
              step={0.1}
              marks={[
                { value: 0, label: '0:00' },
                { value: currentVideoTime, label: 'Current' },
              ]}
              sx={{ mb: 1 }}
            />
            <Typography variant="caption" color="text.secondary">
              Current: {formatTimeForDisplay(startTime)}
            </Typography>
          </Grid>

          {/* End Time */}
          <Grid item xs={6}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
              End Time
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                value={endTimeInput}
                onChange={(e) => handleEndTimeInputChange(e.target.value)}
                placeholder="00:00:00.000"
                sx={{ flex: 1 }}
              />
              <Tooltip title="Set to current playback time">
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setToCurrentTime('end')}
                  sx={{ borderRadius: '8px', minWidth: 'auto', px: 1 }}
                >
                  <TimerIcon fontSize="small" />
                </Button>
              </Tooltip>
            </Box>
            <Slider
              value={endTime}
              onChange={(_, value) => handleEndTimeChange(value as number)}
              min={Math.max(0, startTime + 0.1)}
              max={maxTime}
              step={0.1}
              marks={[
                { value: Math.max(0, startTime + 0.1), label: 'Min' },
                { value: currentVideoTime, label: 'Current' },
              ]}
              sx={{ mb: 1 }}
            />
            <Typography variant="caption" color="text.secondary">
              Current: {formatTimeForDisplay(endTime)}
            </Typography>
          </Grid>
        </Grid>

        {/* Playback Control Area */}
        <Box sx={{ 
          mt: 3,
          p: 2, 
          bgcolor: 'secondary.light', 
          borderRadius: 2,
        }}>
          <Typography variant="subtitle2" sx={{ mb: 2, color: 'secondary.contrastText', fontWeight: 600 }}>
            Fine-tuning Playback Controls
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
            {/* Play/Pause Button */}
            <Tooltip title={isPlaying ? "Pause" : "Play"}>
              <IconButton
                onClick={handlePlayPause}
                disabled={!onPlayPause}
                sx={{ 
                  bgcolor: 'secondary.dark',
                  color: 'secondary.contrastText',
                  '&:hover': { bgcolor: 'secondary.main' }
                }}
              >
                {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
              </IconButton>
            </Tooltip>

            {/* Playback Speed Control */}
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ color: 'secondary.contrastText', mb: 1 }}>
                Playback Speed: {playbackSpeed}x
              </Typography>
              <Slider
                value={playbackSpeed}
                onChange={(_, value) => handleSpeedChange(value as number)}
                min={0.25}
                max={2}
                step={0.25}
                marks={[
                  { value: 0.25, label: '0.25x' },
                  { value: 0.5, label: '0.5x' },
                  { value: 1, label: '1x' },
                  { value: 1.5, label: '1.5x' },
                  { value: 2, label: '2x' },
                ]}
                disabled={!onPlaySpeedChange}
                sx={{
                  color: 'secondary.contrastText',
                  '& .MuiSlider-mark': {
                    color: 'secondary.contrastText',
                  },
                  '& .MuiSlider-markLabel': {
                    color: 'secondary.contrastText',
                    fontSize: '0.75rem',
                  },
                }}
              />
            </Box>
          </Box>

          {/* Quick Slow Preview Buttons */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Tooltip title="Slow preview from start time">
              <Button
                variant="contained"
                size="small"
                startIcon={<SlowMotionIcon />}
                onClick={() => handleSlowPreview(startTime)}
                sx={{ borderRadius: '8px', bgcolor: 'secondary.dark' }}
              >
                Slow Preview Start
              </Button>
            </Tooltip>
            <Tooltip title="Slow preview from end time">
              <Button
                variant="contained"
                size="small"
                startIcon={<SlowMotionIcon />}
                onClick={() => handleSlowPreview(endTime)}
                sx={{ borderRadius: '8px', bgcolor: 'secondary.dark' }}
              >
                Slow Preview End
              </Button>
            </Tooltip>
            <Tooltip title="Resume normal speed">
              <Button
                variant="outlined"
                size="small"
                startIcon={<SpeedIcon />}
                onClick={() => handleSpeedChange(1)}
                sx={{ 
                  borderRadius: '8px',
                  borderColor: 'secondary.contrastText',
                  color: 'secondary.contrastText',
                  '&:hover': {
                    borderColor: 'secondary.dark',
                    bgcolor: 'secondary.dark',
                  }
                }}
              >
                Normal Speed
              </Button>
            </Tooltip>
          </Box>
        </Box>

        {/* Statistics */}
        <Box sx={{ 
          mt: 3,
          p: 2, 
          bgcolor: 'primary.light', 
          borderRadius: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <Box>
            <Typography variant="body2" sx={{ color: 'primary.contrastText', opacity: 0.9 }}>
              Subtitle Duration
            </Typography>
            <Typography variant="h6" sx={{ color: 'primary.contrastText' }}>
              {duration.toFixed(2)}s
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: 'primary.contrastText', opacity: 0.9 }}>
              Character Count
            </Typography>
            <Typography variant="h6" sx={{ color: 'primary.contrastText' }}>
              {subtitle.text.length}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="body2" sx={{ color: 'primary.contrastText', opacity: 0.9 }}>
              Reading Speed
            </Typography>
            <Typography variant="h6" sx={{ color: 'primary.contrastText' }}>
              {duration > 0 ? Math.round(subtitle.text.length / duration) : 0} chars/sec
            </Typography>
          </Box>
        </Box>

        {/* Validation Error */}
        {validationError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {validationError}
          </Alert>
        )}

        {/* Current Playback Time Hint */}
        <Box sx={{ 
          mt: 2, 
          p: 1.5, 
          bgcolor: 'info.light', 
          borderRadius: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 1
        }}>
          <TimerIcon fontSize="small" sx={{ color: 'info.contrastText' }} />
          <Typography variant="body2" sx={{ color: 'info.contrastText' }}>
            Current Playback Time: {formatTimeForDisplay(currentVideoTime)}
          </Typography>
        </Box>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          variant="outlined"
          startIcon={<ResetIcon />}
          onClick={resetTimes}
          sx={{ borderRadius: '8px' }}
        >
          Reset
        </Button>
        <Button
          variant="outlined"
          startIcon={<PlayArrowIcon />}
          onClick={handlePreview}
          sx={{ borderRadius: '8px' }}
        >
          Preview
        </Button>
        <Box sx={{ flex: 1 }} />
        <Button
          variant="outlined"
          startIcon={<CloseIcon />}
          onClick={onClose}
          sx={{ borderRadius: '8px' }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          startIcon={<CheckIcon />}
          onClick={handleSave}
          disabled={!!validationError}
          sx={{ borderRadius: '8px' }}
        >
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TimeAdjustmentDialog;
