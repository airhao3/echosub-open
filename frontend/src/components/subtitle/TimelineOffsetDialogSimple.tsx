import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  TextField,
  Alert,
  Chip,
} from '@mui/material';

interface Subtitle {
  id: string;
  text: string;
  startTime: number;
  endTime: number;
}

interface TimelineOffsetDialogProps {
  open: boolean;
  subtitles: Subtitle[];
  language: string;
  onClose: () => void;
  onApplyOffset: (offsetSeconds: number, language: string) => void;
  onSeekTo?: (time: number) => void;
}

const TimelineOffsetDialogSimple: React.FC<TimelineOffsetDialogProps> = ({
  open,
  subtitles,
  language,
  onClose,
  onApplyOffset,
}) => {
  const [offsetSeconds, setOffsetSeconds] = useState(0);

  // Format time display
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(Math.abs(timeInSeconds) / 60);
    const seconds = Math.floor(Math.abs(timeInSeconds) % 60);
    const milliseconds = Math.floor((Math.abs(timeInSeconds) % 1) * 1000);
    const sign = timeInSeconds < 0 ? '-' : '';
    
    return `${sign}${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  // Handle applying offset
  const handleApplyOffset = () => {
    onApplyOffset(offsetSeconds, language);
    onClose();
  };

  // Preset offset values
  const presetOffsets = [
    { label: '-2s', value: -2 },
    { label: '-1s', value: -1 },
    { label: '-0.5s', value: -0.5 },
    { label: '+0.5s', value: 0.5 },
    { label: '+1s', value: 1 },
    { label: '+2s', value: 2 },
  ];

  const languageDisplay = language === 'auto' ? 'Auto' :
                          language === 'zh' ? 'Chinese' :
                          language === 'en' ? 'English' : language;

  // Get example
  const example = subtitles.length > 0 ? {
    original: { start: subtitles[0].startTime, end: subtitles[0].endTime },
    offset: { 
      start: Math.max(0, subtitles[0].startTime + offsetSeconds), 
      end: Math.max(0, subtitles[0].endTime + offsetSeconds) 
    },
    text: subtitles[0].text
  } : null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Timeline Offset Adjustment - <Chip label={languageDisplay} size="small" color="primary" />
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
          Adjust the display time for all {subtitles.length} subtitles in the {languageDisplay} language.
          Positive values delay subtitles, negative values show them earlier.
        </Typography>

        {/* Preset offset values */}
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Quick Select Offset
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
          {presetOffsets.map((preset) => (
            <Button
              key={preset.value}
              variant={offsetSeconds === preset.value ? 'contained' : 'outlined'}
              size="small"
              onClick={() => setOffsetSeconds(preset.value)}
              sx={{ borderRadius: '12px' }}
            >
              {preset.label}
            </Button>
          ))}
        </Box>

        {/* Custom Offset */}
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Custom Offset
        </Typography>
        <TextField
          label="Offset (seconds)"
          value={offsetSeconds}
          onChange={(e) => setOffsetSeconds(parseFloat(e.target.value) || 0)}
          type="number"
          size="small"
          fullWidth
          sx={{ mb: 3 }}
          inputProps={{ step: 0.1 }}
        />

        {/* Current Offset Display */}
        <Box sx={{ 
          p: 2, 
          bgcolor: 'info.light', 
          borderRadius: 2,
          mb: 3,
          textAlign: 'center'
        }}>
          <Typography variant="h6" sx={{ color: 'info.contrastText' }}>
            Current Offset: {formatTime(offsetSeconds)}
          </Typography>
          <Typography variant="body2" sx={{ color: 'info.contrastText', opacity: 0.9 }}>
            {offsetSeconds > 0 ? 'Subtitles will be delayed' : offsetSeconds < 0 ? 'Subtitles will be shown earlier' : 'No offset'}
          </Typography>
        </Box>

        {/* Offset Preview (First Subtitle) */}
        {example && offsetSeconds !== 0 && (
          <>
            <Typography variant="subtitle2" sx={{ mb: 2 }}>
              Offset Preview (First Subtitle)
            </Typography>
            <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 2, mb: 2 }}>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Original:</strong> {formatTime(example.original.start)} - {formatTime(example.original.end)}
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>With Offset:</strong> {formatTime(example.offset.start)} - {formatTime(example.offset.end)}
              </Typography>
              <Typography variant="body2" sx={{ 
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {example.text}
              </Typography>
            </Box>
          </>
        )}

        {/* Warnings */}
        {Math.abs(offsetSeconds) > 5 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            The offset is large ({Math.abs(offsetSeconds).toFixed(1)}s), please confirm this is the desired adjustment.
          </Alert>
        )}

        {offsetSeconds < 0 && subtitles.some(sub => sub.startTime + offsetSeconds < 0) && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Warning: Some subtitles will have a start time less than 0 after the offset. Their start times will be set to 0.
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleApplyOffset} variant="contained" disabled={offsetSeconds === 0}>
          Apply Offset
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TimelineOffsetDialogSimple;
