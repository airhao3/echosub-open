import React from 'react';
import { Box, Chip, Typography, Tooltip } from '@mui/material';
import { Speed as SpeedIcon, Cloud as CloudIcon } from '@mui/icons-material';

interface LightweightModeIndicatorProps {
  variant?: 'chip' | 'banner';
  showDetails?: boolean;
}

const LightweightModeIndicator: React.FC<LightweightModeIndicatorProps> = ({ 
  variant = 'chip', 
  showDetails = false 
}) => {
  if (variant === 'banner') {
    return (
      <Box 
        sx={{ 
          backgroundColor: 'primary.light', 
          color: 'white', 
          p: 2, 
          borderRadius: 1,
          mb: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 1
        }}
      >
        <CloudIcon />
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            云端处理模式
          </Typography>
          {showDetails && (
            <Typography variant="body2" sx={{ opacity: 0.9 }}>
              高效处理 • 云端计算 • 智能字幕生成
            </Typography>
          )}
        </Box>
      </Box>
    );
  }

  return (
    <Tooltip title="当前系统运行在云端处理模式：高效智能字幕生成">
      <Chip
        icon={<SpeedIcon />}
        label="云端模式"
        size="small"
        color="primary"
        variant="outlined"
        sx={{
          fontSize: '0.75rem',
          height: 24
        }}
      />
    </Tooltip>
  );
};

export default LightweightModeIndicator;