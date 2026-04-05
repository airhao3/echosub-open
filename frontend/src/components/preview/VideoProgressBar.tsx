import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, Slider } from '@mui/material';

interface VideoProgressBarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  subtitles?: Array<{
    id: string;
    startTime: number;
    endTime: number;
    text: string;
  }>;
  onSubtitleClick?: (subtitle: any) => void;
}

const VideoProgressBar: React.FC<VideoProgressBarProps> = ({
  currentTime,
  duration,
  onSeek,
  subtitles = [],
  onSubtitleClick
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragValue, setDragValue] = useState(0);

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSliderChange = (event: Event | React.SyntheticEvent, newValue: number | number[]) => {
    const value = Array.isArray(newValue) ? newValue[0] : newValue;
    setDragValue(value);
    setIsDragging(true);
  };

  const handleSliderCommit = (event: Event | React.SyntheticEvent, newValue: number | number[]) => {
    const value = Array.isArray(newValue) ? newValue[0] : newValue;
    onSeek(value);
    setIsDragging(false);
  };

  const displayTime = isDragging ? dragValue : currentTime;
  const progress = duration > 0 ? (displayTime / duration) * 100 : 0;

  // 根据当前时间获取活跃字幕
  const getActiveSubtitle = (time: number) => {
    return subtitles.find(sub => time >= sub.startTime && time <= sub.endTime);
  };

  const activeSubtitle = getActiveSubtitle(displayTime);

  return (
    <Box sx={{ 
      px: 2, 
      py: 1.5, 
      background: 'background.paper', 
      borderTop: (theme) => `1px solid ${theme.palette.divider}`,
      borderRadius: '0 0 16px 16px'
    }}>
      
      {/* 时间显示 */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        mb: 1 
      }}>
        <Typography variant="body2" sx={{ color: '#666', fontWeight: 500 }}>
          {formatTime(displayTime)} / {formatTime(duration)}
        </Typography>
      </Box>

      {/* 进度条 */}
      <Box sx={{ position: 'relative' }}>
        {/* 字幕区间标记 */}
        <Box sx={{ 
          position: 'absolute', 
          top: -8, 
          left: 0, 
          right: 0, 
          height: '4px',
          zIndex: 1
        }}>
          {subtitles.map((subtitle, index) => {
            const startPercent = duration > 0 ? (subtitle.startTime / duration) * 100 : 0;
            const widthPercent = duration > 0 ? ((subtitle.endTime - subtitle.startTime) / duration) * 100 : 0;
            const isActive = displayTime >= subtitle.startTime && displayTime <= subtitle.endTime;
            
            return (
              <Box
                key={subtitle.id}
                onClick={() => onSubtitleClick?.(subtitle)}
                sx={{
                  position: 'absolute',
                  left: `${startPercent}%`,
                  width: `${widthPercent}%`,
                  height: '4px',
                  background: isActive ? '#1976d2' : '#bbdefb',
                  borderRadius: '2px',
                  cursor: 'pointer',
                  border: '1px solid rgba(255, 255, 255, 0.8)',
                  '&:hover': {
                    background: isActive ? '#1565c0' : '#90caf9',
                    transform: 'scaleY(1.5)',
                    zIndex: 10
                  },
                  transition: 'all 0.2s ease',
                  minWidth: '2px'
                }}
                title={subtitle.text}
              />
            );
          })}
        </Box>

        {/* 主进度条 */}
        <Slider
          value={displayTime}
          onChange={handleSliderChange}
          onChangeCommitted={handleSliderCommit}
          min={0}
          max={duration}
          step={0.1}
          sx={{
            mt: 1,
            '& .MuiSlider-track': {
              background: 'linear-gradient(90deg, #1976d2 0%, #42a5f5 100%)',
              border: 'none',
              height: '6px'
            },
            '& .MuiSlider-rail': {
              background: '#e0e0e0',
              height: '6px'
            },
            '& .MuiSlider-thumb': {
              width: 20,
              height: 20,
              background: 'background.paper',
              border: '2px solid #1976d2',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
              '&:hover': {
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
                transform: 'scale(1.1)'
              },
              '&.Mui-focusVisible': {
                boxShadow: '0 0 0 8px rgba(25, 118, 210, 0.16)'
              }
            }
          }}
        />
      </Box>
    </Box>
  );
};

export default VideoProgressBar;