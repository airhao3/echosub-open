import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Divider,
  IconButton,
  Alert,
  Slider,
  FormControlLabel,
  Switch,
  Paper,
} from '@mui/material';
import {
  ContentCut as SplitIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  PlayArrow as PlayArrowIcon,
  CallSplit as VerticalSplitIcon,
} from '@mui/icons-material';

interface SplitSubtitleDialogProps {
  open: boolean;
  subtitle: {
    id: string;
    text: string;
    startTime: number;
    endTime: number;
  } | null;
  onClose: () => void;
  onSplit: (splitPosition: number, splitTime: number, firstText: string, secondText: string) => void;
  onSeekTo: (time: number) => void;
}

const SplitSubtitleDialog: React.FC<SplitSubtitleDialogProps> = ({
  open,
  subtitle,
  onClose,
  onSplit,
  onSeekTo,
}) => {
  const [splitPosition, setSplitPosition] = useState(0);
  const [splitTime, setSplitTime] = useState(0);
  const [autoSplitTime, setAutoSplitTime] = useState(true);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (subtitle) {
      // Default split position is in the middle of the text
      const midPoint = Math.floor(subtitle.text.length / 2);
      setSplitPosition(midPoint);
      
      // Default split time is in the middle of the time range
      const midTime = subtitle.startTime + ((subtitle.endTime - subtitle.startTime) / 2);
      setSplitTime(midTime);
    }
  }, [subtitle]);

  // Format time display
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  // Handle text click to select split position
  const handleTextClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!subtitle) return;
    
    const range = document.caretRangeFromPoint(event.clientX, event.clientY);
    
    if (range && range.startContainer.nodeType === Node.TEXT_NODE) {
      const textNode = range.startContainer;
      const clickPosition = range.startOffset;
      
      // Calculate position in the entire text
      let totalOffset = 0;
      const walker = document.createTreeWalker(
        textRef.current!,
        NodeFilter.SHOW_TEXT,
        null
      );
      
      let currentNode;
      while ((currentNode = walker.nextNode())) {
        if (currentNode === textNode) {
          totalOffset += clickPosition;
          break;
        } else {
          totalOffset += currentNode.textContent?.length || 0;
        }
      }
      
      setSplitPosition(totalOffset);
      
      // If auto-adjust time is enabled, calculate time based on text position
      if (autoSplitTime) {
        const ratio = totalOffset / subtitle.text.length;
        const newSplitTime = subtitle.startTime + (subtitle.endTime - subtitle.startTime) * ratio;
        setSplitTime(newSplitTime);
      }
    }
  };

  // Smart split suggestions
  const getSmartSplitSuggestions = (): number[] => {
    if (!subtitle) return [];
    
    const text = subtitle.text;
    const suggestions: number[] = [];
    
    // Find punctuation
    const punctuation = /[.!?,,;:]/g;
    let match;
    while ((match = punctuation.exec(text)) !== null) {
      suggestions.push(match.index + 1);
    }
    
    // Find spaces
    const spaces = /\s+/g;
    while ((match = spaces.exec(text)) !== null) {
      suggestions.push(match.index);
    }
    
    // Add midpoint
    suggestions.push(Math.floor(text.length / 2));
    
    return suggestions.filter(pos => pos > 0 && pos < text.length).sort((a, b) => a - b);
  };

  // Render text with split position indicator
  const renderTextWithSplit = () => {
    if (!subtitle) return null;
    
    const text = subtitle.text;
    const beforeSplit = text.substring(0, splitPosition);
    const afterSplit = text.substring(splitPosition);
    
    return (
      <Box
        ref={textRef}
        onClick={handleTextClick}
        sx={{
          cursor: 'text',
          userSelect: 'text',
          p: 2,
          border: '2px dashed',
          borderColor: 'primary.main',
          borderRadius: 2,
          lineHeight: 1.8,
          fontSize: '1.1rem',
          fontFamily: 'monospace',
          position: 'relative',
          minHeight: '60px',
          '&:hover': {
            bgcolor: 'action.hover',
          }
        }}
      >
        <span style={{ color: '#2196f3', backgroundColor: 'rgba(33, 150, 243, 0.1)' }}>
          {beforeSplit}
        </span>
        {splitPosition < text.length && (
          <Box
            component="span"
            sx={{
              display: 'inline-block',
              width: '2px',
              height: '1.2em',
              bgcolor: 'error.main',
              animation: 'blink 1s infinite',
              '@keyframes blink': {
                '0%, 50%': { opacity: 1 },
                '51%, 100%': { opacity: 0 },
              }
            }}
          />
        )}
        <span style={{ color: '#ff9800', backgroundColor: 'rgba(255, 152, 0, 0.1)' }}>
          {afterSplit}
        </span>
      </Box>
    );
  };

  // Handle split action
  const handleSplit = () => {
    if (!subtitle) return;
    
    const firstText = subtitle.text.substring(0, splitPosition).trim();
    const secondText = subtitle.text.substring(splitPosition).trim();
    
    if (!firstText || !secondText) {
      return; // Do not allow empty text
    }
    
    onSplit(splitPosition, splitTime, firstText, secondText);
    onClose();
  };

  // Preview split point
  const handlePreview = () => {
    onSeekTo(splitTime);
  };

  if (!subtitle) return null;

  const suggestions = getSmartSplitSuggestions();
  const firstText = subtitle.text.substring(0, splitPosition).trim();
  const secondText = subtitle.text.substring(splitPosition).trim();
  const duration = subtitle.endTime - subtitle.startTime;
  const firstDuration = splitTime - subtitle.startTime;
  const secondDuration = subtitle.endTime - splitTime;

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
          <SplitIcon color="primary" />
          <Typography variant="h6">Split Subtitle</Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2 }}>
        {/* Original Subtitle Info */}
        <Box sx={{ 
          mb: 3, 
          p: 2, 
          bgcolor: 'grey.50', 
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'grey.200'
        }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
            Original Subtitle ({formatTime(subtitle.startTime)} - {formatTime(subtitle.endTime)})
          </Typography>
          <Typography variant="body1">
            {subtitle.text}
          </Typography>
        </Box>

        {/* Split Position Selection */}
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
          Select Split Position (Click on the text)
        </Typography>
        
        {renderTextWithSplit()}

        {/* Smart Split Suggestions */}
        {suggestions.length > 0 && (
          <Box sx={{ mt: 2, mb: 3 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
              Smart Split Suggestions
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {suggestions.slice(0, 5).map((pos, index) => (
                <Button
                  key={index}
                  variant={splitPosition === pos ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => {
                    setSplitPosition(pos);
                    if (autoSplitTime) {
                      const ratio = pos / subtitle.text.length;
                      const newSplitTime = subtitle.startTime + duration * ratio;
                      setSplitTime(newSplitTime);
                    }
                  }}
                  sx={{ borderRadius: '12px' }}
                >
                  Position {pos}
                </Button>
              ))}
            </Box>
          </Box>
        )}

        {/* Split Time Control */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Split Time
            </Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={autoSplitTime}
                  onChange={(e) => setAutoSplitTime(e.target.checked)}
                  size="small"
                />
              }
              label="Auto-adjust time"
            />
          </Box>
          
          <Slider
            value={splitTime}
            onChange={(_, value) => setSplitTime(value as number)}
            min={subtitle.startTime + 0.1}
            max={subtitle.endTime - 0.1}
            step={0.1}
            disabled={autoSplitTime}
            marks={[
              { value: subtitle.startTime, label: formatTime(subtitle.startTime) },
              { value: subtitle.endTime, label: formatTime(subtitle.endTime) },
            ]}
          />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>
            Split Time: {formatTime(splitTime)}
          </Typography>
        </Box>

        {/* Split Preview */}
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
          Split Preview - Will create two separate subtitles
        </Typography>
        
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
          {/* First Subtitle */}
          <Paper sx={{ p: 2, bgcolor: 'primary.light', border: '2px solid', borderColor: 'primary.main' }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'primary.contrastText', opacity: 0.9 }}>
              First Subtitle (Keeps original position) - {firstDuration.toFixed(1)}s
            </Typography>
            <Typography variant="body2" sx={{ color: 'primary.contrastText', mb: 1 }}>
              Time range: {formatTime(subtitle.startTime)} - {formatTime(splitTime)}
            </Typography>
            <Typography variant="body1" sx={{ color: 'primary.contrastText', fontWeight: 500 }}>
              {firstText || '(empty)'}
            </Typography>
          </Paper>

          {/* Split Indicator */}
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            py: 1
          }}>
            <VerticalSplitIcon color="action" sx={{ mr: 1 }} />
            <Typography variant="body2" color="text.secondary">
              Splits into two separate subtitles
            </Typography>
          </Box>

          {/* Second Subtitle */}
          <Paper sx={{ p: 2, bgcolor: 'secondary.light', border: '2px solid', borderColor: 'secondary.main' }}>
            <Typography variant="subtitle2" sx={{ mb: 1, color: 'secondary.contrastText', opacity: 0.9 }}>
              Second Subtitle (New) - {secondDuration.toFixed(1)}s
            </Typography>
            <Typography variant="body2" sx={{ color: 'secondary.contrastText', mb: 1 }}>
              Time range: {formatTime(splitTime)} - {formatTime(subtitle.endTime)}
            </Typography>
            <Typography variant="body1" sx={{ color: 'secondary.contrastText', fontWeight: 500 }}>
              {secondText || '(empty)'}
            </Typography>
          </Paper>
        </Box>

        {/* Explanation */}
        <Typography variant="caption" sx={{ color: 'info.main', display: 'block', mb: 2, textAlign: 'center' }}>
          ✓ After splitting, this will appear as two separate subtitle entries in the list.
        </Typography>

        {/* Validation Hints */}
        {(!firstText || !secondText) && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Text after splitting cannot be empty. Please adjust the split position.
          </Alert>
        )}

        {(firstDuration < 0.5 || secondDuration < 0.5) && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            It is recommended that each subtitle part has a duration of at least 0.5 seconds.
          </Alert>
        )}
      </DialogContent>

      <Divider />

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          variant="outlined"
          startIcon={<PlayArrowIcon />}
          onClick={handlePreview}
          sx={{ borderRadius: '8px' }}
        >
          Preview Split Point
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
          onClick={handleSplit}
          disabled={!firstText || !secondText}
          sx={{ borderRadius: '8px' }}
        >
          Confirm Split
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SplitSubtitleDialog;
