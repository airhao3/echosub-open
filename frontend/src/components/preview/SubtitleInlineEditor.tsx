import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Divider,
  IconButton,
  Chip
} from '@mui/material';
import {
  Close as CloseIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Timer as TimerIcon,
  Translate as TranslateIcon
} from '@mui/icons-material';

interface SubtitleInlineEditorProps {
  subtitle: any | null;
  open: boolean;
  onClose: () => void;
  onSave: (editedSubtitle: any) => void;
  currentTime: number;
}

const SubtitleInlineEditor: React.FC<SubtitleInlineEditorProps> = ({
  subtitle,
  open,
  onClose,
  onSave,
  currentTime
}) => {
  const [editedText, setEditedText] = useState('');
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(0);
  const textFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (subtitle) {
      setEditedText(subtitle.text || '');
      setStartTime(subtitle.startTime || 0);
      setEndTime(subtitle.endTime || 0);
    }
  }, [subtitle]);

  useEffect(() => {
    if (open && textFieldRef.current) {
      // Delay focus to ensure the dialog is fully open
      setTimeout(() => {
        textFieldRef.current?.focus();
        textFieldRef.current?.select();
      }, 100);
    }
  }, [open]);

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
  };

  const parseTime = (timeString: string): number => {
    const [minutes, seconds] = timeString.split(':');
    const [secs, ms = '0'] = seconds.split('.');
    return parseInt(minutes) * 60 + parseInt(secs) + parseInt(ms.padEnd(3, '0')) / 1000;
  };

  const handleSave = () => {
    if (subtitle) {
      const updatedSubtitle = {
        ...subtitle,
        text: editedText,
        startTime: startTime,
        endTime: endTime
      };
      onSave(updatedSubtitle);
      onClose();
    }
  };

  const handleCancel = () => {
    if (subtitle) {
      setEditedText(subtitle.text || '');
      setStartTime(subtitle.startTime || 0);
      setEndTime(subtitle.endTime || 0);
    }
    onClose();
  };

  const handleSetCurrentTime = (type: 'start' | 'end') => {
    if (type === 'start') {
      setStartTime(currentTime);
    } else {
      setEndTime(currentTime);
    }
  };

  const isPlaying = currentTime >= startTime && currentTime <= endTime;

  if (!subtitle) {
    return null;
  }

  return (
    <Dialog 
      open={open} 
      onClose={handleCancel}
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
          <TranslateIcon color="primary" />
          <Typography variant="h6">Edit Subtitle</Typography>
          {isPlaying && (
            <Chip 
              label="Playing" 
              color="success" 
              size="small" 
              variant="outlined" 
            />
          )}
        </Box>
        <IconButton onClick={handleCancel} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2 }}>
        {/* Subtitle Text Edit */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: '#666' }}>
            Subtitle Content
          </Typography>
          <TextField
            ref={textFieldRef}
            fullWidth
            multiline
            rows={3}
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            placeholder="Enter subtitle content..."
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: '12px',
                background: '#f8f9fa'
              }
            }}
          />
        </Box>

        {/* Time Adjustment */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: '#666' }}>
              Start Time
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                size="small"
                value={formatTime(startTime)}
                onChange={(e) => {
                  try {
                    setStartTime(parseTime(e.target.value));
                  } catch (error) {
                    console.error('Invalid time format');
                  }
                }}
                sx={{ flex: 1 }}
              />
              <Button
                variant="outlined"
                size="small"
                startIcon={<TimerIcon />}
                onClick={() => handleSetCurrentTime('start')}
                sx={{ borderRadius: '8px' }}
              >
                Current
              </Button>
            </Box>
          </Box>

          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: '#666' }}>
              End Time
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                size="small"
                value={formatTime(endTime)}
                onChange={(e) => {
                  try {
                    setEndTime(parseTime(e.target.value));
                  } catch (error) {
                    console.error('Invalid time format');
                  }
                }}
                sx={{ flex: 1 }}
              />
              <Button
                variant="outlined"
                size="small"
                startIcon={<TimerIcon />}
                onClick={() => handleSetCurrentTime('end')}
                sx={{ borderRadius: '8px' }}
              >
                Current
              </Button>
            </Box>
          </Box>
        </Box>

        {/* Duration Display */}
        <Box sx={{ 
          p: 2, 
          background: '#f5f5f5', 
          borderRadius: '8px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <Typography variant="body2" color="text.secondary">
            Duration: <strong>{((endTime - startTime) || 0).toFixed(2)}s</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Characters: <strong>{editedText.length}</strong>
          </Typography>
        </Box>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          variant="outlined"
          startIcon={<CancelIcon />}
          onClick={handleCancel}
          sx={{ borderRadius: '8px' }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={!editedText.trim()}
          sx={{ borderRadius: '8px' }}
        >
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SubtitleInlineEditor;
