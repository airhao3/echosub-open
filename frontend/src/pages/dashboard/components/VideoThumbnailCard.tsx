
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Chip,
  Checkbox,
  Card,
  CardContent,
  CardMedia,
  Fade,
  IconButton,
  useTheme,
  alpha,
} from '@mui/material';
import {
  PlayCircleFilled as PlayIcon,
  AccessTime as TimeIcon,
  Tune as TuneIcon,
  Download as DownloadIcon,
  Delete as DeleteIcon,
  VideoLibrary as VideoLibraryIcon,
} from '@mui/icons-material';
import { ThumbnailService } from '../../../services/api/thumbnailService';

interface VideoThumbnailCardProps {
  job: any;
  index: number;
  selectedJobIds: number[];
  onSelectOne: (id: number) => void;
  onDelete: (id: number) => void;
}

export const VideoThumbnailCard: React.FC<VideoThumbnailCardProps> = ({
  job,
  index,
  selectedJobIds,
  onSelectOne,
  onDelete,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const [isSelected, setIsSelected] = useState(selectedJobIds.includes(job.user_job_number));

  useEffect(() => {
    setIsSelected(selectedJobIds.includes(job.user_job_number));
  }, [selectedJobIds, job.user_job_number]);

  const handleCardClick = (event: React.MouseEvent) => {
    if (event.shiftKey || event.ctrlKey || event.metaKey) {
      event.preventDefault();
      onSelectOne(job.user_job_number);
    } else {
      navigate(`/dashboard/preview/${job.user_job_number}`);
    }
  };


  return (
    <Fade in={true} timeout={300 + index * 50}>
      <Card
        sx={{
          height: '100%',
          cursor: 'pointer',
          border: isSelected ? `2px solid ${theme.palette.primary.main}` : '1px solid rgba(255,255,255,0.12)',
          background: `linear-gradient(135deg, ${alpha(theme.palette.background.paper, 0.8)}, ${alpha(theme.palette.background.paper, 0.95)})`,
          backdropFilter: 'blur(10px)',
          transition: 'all 0.2s ease',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: `0 8px 24px ${alpha(theme.palette.primary.main, 0.3)}`,
          },
        }}
        onClick={handleCardClick}
      >
        <Box
          data-job-id={job.id}
          sx={{
            position: 'relative',
            height: 180,
            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.1)}, ${alpha(theme.palette.secondary.main, 0.1)})`,
            overflow: 'hidden',
          }}
        >
          <CardMedia
            component="img"
            height="180"
            image={ThumbnailService.getThumbnailUrl(job.id, 'medium')}
            alt={job.title || `Job #${job.user_job_number}`}
            sx={{
              objectFit: 'cover',
              width: '100%',
              height: '100%',
              transition: 'transform 0.3s ease',
              '&:hover': {
                transform: 'scale(1.05)',
              },
            }}
            onError={(e) => {
              console.log(`Thumbnail failed to load for job ${job.id} (user_job_number: ${job.user_job_number})`);
              console.log(`Thumbnail URL: ${ThumbnailService.getThumbnailUrl(job.id, 'medium')}`);
              e.currentTarget.style.display = 'none';
              e.currentTarget.parentElement?.setAttribute('data-thumbnail-failed', 'true');
            }}
            onLoad={() => {
              // Reset failed state if image loads successfully
              const parent = document.querySelector(`[data-job-id="${job.id}"]`);
              if (parent) {
                parent.setAttribute('data-thumbnail-failed', 'false');
              }
            }}
          />
          {/* Fallback for failed thumbnail */}
          <Box
            sx={{
              position: 'absolute',
              top: 0, left: 0, right: 0, bottom: 0,
              display: 'none', // Default hidden
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.15)}, ${alpha(theme.palette.secondary.main, 0.15)})`,
              color: theme.palette.primary.main,
              backdropFilter: 'blur(10px)',
              // Show when parent has data-thumbnail-failed="true"
              '[data-thumbnail-failed="true"] &': { display: 'flex' },
            }}
          >
            <VideoLibraryIcon sx={{ fontSize: 48, opacity: 0.6, mb: 1 }} />
            <Typography variant="caption" sx={{ opacity: 0.8, fontWeight: 500, textAlign: 'center', px: 1 }}>
              Generating Thumbnail...
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.6, fontSize: '0.6rem', mt: 0.5 }}>
              Job #{job.user_job_number}
            </Typography>
          </Box>
          {/* Language info - always visible */}
          <Typography
            variant="caption"
            sx={{
              position: 'absolute',
              bottom: 8, left: 8, right: 8,
              textAlign: 'center',
              px: 1, py: 0.5,
              backgroundColor: alpha(theme.palette.background.paper, 0.9),
              borderRadius: '8px',
              fontSize: '0.65rem',
              fontWeight: 600,
              backdropFilter: 'blur(4px)',
              lineHeight: 1.2,
              maxHeight: '40px',
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
{(() => {
              if (!job.source_language && !job.target_languages) {
                return 'Video File';
              }
              
              const source = job.source_language === 'auto' ? 'Auto' : job.source_language?.toUpperCase() || 'Unknown';
              
              let targets = '';
              if (job.target_languages) {
                if (Array.isArray(job.target_languages)) {
                  targets = job.target_languages.map((lang: string) => lang.toUpperCase()).join(', ');
                } else if (typeof job.target_languages === 'string') {
                  // Handle comma-separated string or single language
                  targets = job.target_languages.split(',').map((lang: string) => lang.trim().toUpperCase()).join(', ');
                }
              }
              
              return targets ? `${source} → ${targets}` : source;
            })()}
          </Typography>
          {/* Play button overlay - only shows on hover */}
          <Box
            sx={{
              position: 'absolute',
              top: 0, left: 0, right: 0, bottom: 0,
              background: 'linear-gradient(to bottom, transparent, rgba(0,0,0,0.4))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0,
              transition: 'opacity 0.3s ease',
              // Show when parent card is hovered
              '.MuiCard-root:hover &': {
                opacity: 1,
              },
            }}
          >
            <Box
              sx={{
                backgroundColor: 'rgba(255,255,255,0.9)',
                borderRadius: '50%',
                width: 60,
                height: 60,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                transform: 'scale(0.8)',
                transition: 'transform 0.2s ease',
                '&:hover': {
                  transform: 'scale(1)',
                },
              }}
            >
              <PlayIcon sx={{ 
                fontSize: 32, 
                color: theme.palette.primary.main,
                marginLeft: '4px' // Center the triangle better
              }} />
            </Box>
          </Box>
          <Chip
            label={job.status}
            size="small"
            sx={{
              position: 'absolute',
              top: 8, right: 8,
              backgroundColor: job.status.toLowerCase() === 'completed'
                ? theme.palette.success.main
                : job.status.toLowerCase() === 'failed'
                  ? theme.palette.error.main
                  : job.status.toLowerCase() === 'in_progress'
                    ? theme.palette.warning.main
                    : theme.palette.grey[500],
              color: 'white',
              fontSize: '0.75rem',
            }}
          />
          <Checkbox
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelectOne(job.user_job_number);
            }}
            sx={{
              position: 'absolute',
              top: 8, left: 8,
              color: 'white',
              backgroundColor: 'rgba(0,0,0,0.5)',
              '&.Mui-checked': {
                color: theme.palette.primary.main,
                backgroundColor: 'rgba(255,255,255,0.9)',
              },
            }}
          />
        </Box>
        <CardContent sx={{ p: 2, height: 'calc(100% - 180px)' }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 600,
              fontSize: '1rem',
              mb: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {job.title || `Job #${job.user_job_number}`}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            ID: #{job.user_job_number}
          </Typography>
          {job.created_at && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
              <TimeIcon fontSize="small" />
              {new Date(job.created_at).toLocaleDateString()}
            </Typography>
          )}
          <Box sx={{ display: 'flex', gap: 1, mt: 'auto', pt: 1 }}>
            {job.status.toLowerCase() === 'completed' && (
              <>
                {/* Video Parameters button temporarily hidden - focusing on subtitle processing only */}
                {/* <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/dashboard/video-params/${job.user_job_number}`);
                  }}
                  title="Adjust Video Parameters"
                  sx={{
                    backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                    '&:hover': { backgroundColor: alpha(theme.palette.secondary.main, 0.2) },
                  }}
                >
                  <TuneIcon fontSize="small" />
                </IconButton> */}
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    window.open(`/api/v1/downloads/results/${job.id}/original_video`, '_blank');
                  }}
                  title="Download"
                  sx={{
                    backgroundColor: alpha(theme.palette.success.main, 0.1),
                    '&:hover': { backgroundColor: alpha(theme.palette.success.main, 0.2) },
                  }}
                >
                  <DownloadIcon fontSize="small" />
                </IconButton>
              </>
            )}
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(job.user_job_number);
              }}
              title="Delete"
              sx={{
                backgroundColor: alpha(theme.palette.error.main, 0.1),
                '&:hover': { backgroundColor: alpha(theme.palette.error.main, 0.2) },
                marginLeft: 'auto',
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Box>
        </CardContent>
      </Card>
    </Fade>
  );
};
