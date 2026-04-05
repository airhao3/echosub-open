import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Divider,
  Stack,
  Button,
} from '@mui/material';
import { Visibility as VisibilityIcon, Movie as MovieIcon } from '@mui/icons-material';
import { PreviewOption } from '../../services/api/previewService';

interface ProcessedVideoCardProps {
  preview: PreviewOption;
  onSelect: (preview: PreviewOption) => void;
  formatDuration: (seconds?: number) => string;
  formatFileSize: (bytes?: number) => string;
}

const ProcessedVideoCard: React.FC<ProcessedVideoCardProps> = ({
  preview,
  onSelect,
  formatDuration,
  formatFileSize,
}) => {
  // Get the display name based on the preview type (Lightweight Mode)
  const getPreviewTypeName = (type: string) => {
    switch (type) {
      case 'original_video': return '原始视频';
      case 'subtitled_video': return '原始视频 + 字幕';
      case 'subtitle': return '字幕文件';
      case 'transcript': return '转录文本';
      case 'dubbed_video': return '原始视频 (配音模式)';
      // Handle any type that contains 'video'
      default: return type.includes('video') ? '视频文件' : type;
    }
  };

  return (
    <Paper
      elevation={3}
      sx={{
        p: 0,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'transform 0.2s',
        '&:hover': { 
          transform: 'translateY(-4px)',
          boxShadow: 6
        },
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
      onClick={() => onSelect(preview)}
    >
      {/* Preview thumbnail area */}
      <Box 
        sx={{ 
          bgcolor: 'primary.dark', 
          p: 2, 
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          gap: 1
        }}
      >
        <MovieIcon />
        <Typography variant="subtitle1" fontWeight="bold">
          {getPreviewTypeName(preview.type)}
          {preview.language && (
            <Chip 
              size="small" 
              label={preview.language} 
              sx={{ ml: 1, bgcolor: 'primary.light', color: 'white' }} 
            />
          )}
        </Typography>
      </Box>

      {/* Content area */}
      <Box sx={{ p: 2, flexGrow: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {preview.type === 'subtitled_video' || preview.type.includes('video') 
            ? '云端处理：智能字幕生成' 
            : '云端处理结果文件'}
        </Typography>

        {preview.metadata && (
          <Box>
            <Divider sx={{ my: 1 }} />
            <Stack spacing={1}>
              {preview.metadata.duration && (
                <Typography variant="body2" color="text.secondary">
                  Duration: {formatDuration(preview.metadata.duration)}
                </Typography>
              )}
              {preview.metadata.width && preview.metadata.height && (
                <Typography variant="body2" color="text.secondary">
                  Resolution: {preview.metadata.width}×{preview.metadata.height}
                </Typography>
              )}
              {preview.file_size && (
                <Typography variant="body2" color="text.secondary">
                  Size: {formatFileSize(preview.file_size)}
                </Typography>
              )}
            </Stack>
          </Box>
        )}
      </Box>

      {/* Action button */}
      <Box sx={{ p: 2, pt: 0 }}>
        <Button
          fullWidth
          startIcon={<VisibilityIcon />}
          variant="contained"
          color="primary"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(preview);
          }}
        >
          Play Video
        </Button>
      </Box>
    </Paper>
  );
};

export default ProcessedVideoCard;
