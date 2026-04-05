import React, { useState } from 'react';
import { Box, Slider, Typography, IconButton } from '@mui/material';
import { AccessTime as AccessTimeIcon } from '@mui/icons-material';

interface LocalSubtitle {
  id: string;
  text: string;
  startTime: number;
  endTime: number;
}

interface InlineTimeRangeSliderProps {
  startTime: number;
  endTime: number;
  onTimeChange: (newStartTime: number, newEndTime: number) => void;
  onSeekTo: (time: number) => void;
  languagesInGroup: string[];
  subtitlesByLanguage: { [language: string]: LocalSubtitle };
  onOpenTimeDialog: (subtitle: LocalSubtitle, language: string) => void;
}

const InlineTimeRangeSlider: React.FC<InlineTimeRangeSliderProps> = ({
  startTime,
  endTime,
  onTimeChange,
  onSeekTo,
  languagesInGroup,
  subtitlesByLanguage,
  onOpenTimeDialog
}) => {
  const [value, setValue] = useState<number[]>([startTime, endTime]);
  const [isDragging, setIsDragging] = useState(false);

  // 当外部时间变化时同步更新内部状态，但不在拖拽时更新
  React.useEffect(() => {
    if (!isDragging) {
      setValue([startTime, endTime]);
    }
  }, [startTime, endTime, isDragging]);

  // 格式化时间显示
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  const handleSliderChange = (event: Event, newValue: number | number[]) => {
    const range = newValue as number[];
    setValue(range);
    setIsDragging(true);
  };

  const handleSliderChangeCommitted = (event: React.SyntheticEvent | Event, newValue: number | number[]) => {
    const range = newValue as number[];
    setIsDragging(false);
    
    if (range[0] !== startTime || range[1] !== endTime) {
      console.log('⏱️ 时间轴滑块调整完成:', { 
        from: `${startTime.toFixed(2)}-${endTime.toFixed(2)}`,
        to: `${range[0].toFixed(2)}-${range[1].toFixed(2)}`
      });
      onTimeChange(range[0], range[1]);
    }
  };

  const handleOpenTimeDialog = () => {
    // 获取第一个可用的字幕用于时间调整
    const firstLanguage = languagesInGroup[0];
    if (firstLanguage && subtitlesByLanguage[firstLanguage]) {
      onOpenTimeDialog(subtitlesByLanguage[firstLanguage], firstLanguage);
    }
  };

  // 按照句子持续时间计算范围：前1/3 + 句子时间 + 后1/3
  const subtitleDuration = endTime - startTime;
  const bufferTime = subtitleDuration / 2; // 前后各50%的句子时长作为缓冲
  const minTime = Math.max(0, startTime - bufferTime);
  const maxTime = endTime + bufferTime;

  return (
    <Box sx={{ 
      width: '100%', 
      height: '40px', // 固定一行高度
      display: 'flex',
      alignItems: 'center',
      gap: 1.5,
      px: 1,
      py: 0.5
    }}>
      {/* 开始时间显示 */}
      <Typography 
        variant="caption" 
        sx={{ 
          fontSize: '0.75rem',
          fontFamily: 'monospace',
          fontWeight: 600,
          color: '#2e7d32',
          minWidth: '65px',
          textAlign: 'center'
        }}
      >
        {formatTime(value[0])}
      </Typography>
      
      {/* 扩展的滑块 - 占据更多空间让控制点分开 */}
      <Box sx={{ flex: 1, mx: 1 }}>
        <Slider
          value={value}
          onChange={handleSliderChange}
          onChangeCommitted={handleSliderChangeCommitted}
          valueLabelDisplay="auto"
          valueLabelFormat={formatTime}
          min={minTime}
          max={maxTime}
          step={0.02}
          sx={{
            height: 8,
            '& .MuiSlider-thumb': {
              width: 20,
              height: 20,
              border: '2px solid #fff',
              boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
              // 移除跳动效果，简化样式
              '&:hover': {
                boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
              },
              '&:first-of-type': {
                backgroundColor: '#2e7d32', // 绿色 - 开始时间
              },
              '&:last-of-type': {
                backgroundColor: '#1976d2', // 蓝色 - 结束时间
              },
            },
            '& .MuiSlider-track': {
              height: 6,
              border: 'none',
              backgroundColor: '#1976d2',
            },
            '& .MuiSlider-rail': {
              height: 6,
              opacity: 0.3,
              backgroundColor: '#e0e0e0',
            },
            '& .MuiSlider-valueLabel': {
              fontSize: '0.7rem',
              fontFamily: 'monospace',
              background: 'rgba(0, 0, 0, 0.8)',
              color: 'white',
              padding: '2px 6px',
              borderRadius: '4px',
            },
          }}
        />
      </Box>
      
      {/* 结束时间显示 */}
      <Typography 
        variant="caption" 
        sx={{ 
          fontSize: '0.75rem',
          fontFamily: 'monospace',
          fontWeight: 600,
          color: '#1976d2',
          minWidth: '65px',
          textAlign: 'center'
        }}
      >
        {formatTime(value[1])}
      </Typography>
      
      {/* 时间调整按钮 */}
      <IconButton 
        size="small" 
        onClick={handleOpenTimeDialog}
        sx={{ 
          width: 28,
          height: 28,
          ml: 0.5,
          color: 'text.secondary',
          '&:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.04)',
            color: 'primary.main'
          }
        }}
      >
        <AccessTimeIcon fontSize="small" />
      </IconButton>
    </Box>
  );
};

export default InlineTimeRangeSlider;