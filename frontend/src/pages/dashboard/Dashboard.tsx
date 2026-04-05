import React, { useEffect, useState } from 'react';
import { useQuery } from 'react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Button,
  CircularProgress,
  Card,
  CardContent,
  CardMedia,
  Avatar,
  Chip,
  Container,
  useTheme,
} from '@mui/material';
import { 
  Add as AddIcon, 
  TrendingUp as TrendingUpIcon,
  VideoLibrary as VideoLibraryIcon,
  AutoAwesome as AutoAwesomeIcon,
  PlayCircleFilled as PlayIcon,
  AccessTime as TimeIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  CloudUpload as UploadIcon,
  Analytics as AnalyticsIcon,
  Insights as InsightsIcon,
} from '@mui/icons-material';

import { getUserJobs } from '../../services/api/jobService';
import { ThumbnailService } from '../../services/api/thumbnailService';

interface StatusCount {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  

  useEffect(() => {
  }, []);

  const { data: jobs, isLoading, error } = useQuery('userJobs', getUserJobs);
  
  const statusCounts: StatusCount = jobs?.reduce(
    (acc: StatusCount, job) => {
      const status = job.status.toLowerCase();
      if (status in acc) {
        acc[status as keyof StatusCount] += 1;
      }
      return acc;
    },
    { pending: 0, processing: 0, completed: 0, failed: 0, cancelled: 0 }
  ) || { pending: 0, processing: 0, completed: 0, failed: 0, cancelled: 0 };
  
  const totalJobs = jobs?.length || 0;

  // Calculate additional metrics
  const completionRate = totalJobs > 0 ? (statusCounts.completed / totalJobs) * 100 : 0;
  
  // Sort jobs by most recent (created_at or updated_at) and take first 6
  const recentJobs = jobs?.sort((a, b) => {
    // Use updated_at if available, otherwise fall back to created_at
    const dateA = new Date(a.updated_at || a.created_at);
    const dateB = new Date(b.updated_at || b.created_at);
    return dateB.getTime() - dateA.getTime(); // Sort in descending order (newest first)
  }).slice(0, 6) || [];
  
  // Create stat cards data
  const statCards = [
    { title: "全部项目", value: totalJobs, icon: VideoLibraryIcon, color: theme.palette.primary.main },
    { title: "处理中", value: statusCounts.processing, icon: ScheduleIcon, color: theme.palette.info.main },
    { title: "已完成", value: statusCounts.completed, icon: CheckIcon, color: theme.palette.success.main },
    { title: "失败", value: statusCounts.failed, icon: ErrorIcon, color: theme.palette.error.main },
  ];
  
  const handleCreateJob = () => {
    navigate('/dashboard/upload');
  };
  
  if (isLoading) {
    return (
      <Box 
        display="flex" 
        justifyContent="center" 
        alignItems="center" 
        minHeight="80vh"
        sx={{
          background: theme.palette.background.default,
        }}
      >
        <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
          <CircularProgress size={60} thickness={4} />
          <Typography variant="h6" color="text.secondary">
            Loading your dashboard...
          </Typography>
        </Box>
      </Box>
    );
  }
  
  if (error) {
    return (
      <Container maxWidth="lg">
        <Box p={3} display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
          <Card sx={{ p: 4, textAlign: 'center', maxWidth: 500 }}>
            <ErrorIcon sx={{ fontSize: 60, color: 'error.main', mb: 2 }} />
            <Typography color="error" variant="h6" gutterBottom>
              Error loading dashboard
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Please refresh the page or try again later.
            </Typography>
            <Button 
              variant="contained" 
              sx={{ mt: 3 }} 
              onClick={() => window.location.reload()}
            >
              Refresh Page
            </Button>
          </Card>
        </Box>
      </Container>
    );
  }
  
  return (
    <Box
      sx={{
        background: theme.palette.background.default,
        height: '100vh', overflow: 'auto',
        pb: 2,
      }}
    >
      <Container maxWidth="lg">
        
          <Box pt={2} pb={1}>
            {/* Header Section */}
            <Box mb={2}>
              
                <Box>
                  <Typography 
                    variant="h3" 
                    component="h1" 
                    gutterBottom
                    sx={{
                      fontWeight: 700,
                      color: 'text.primary',
                      mb: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                    }}
                  >
                    <AutoAwesomeIcon sx={{ fontSize: 36, color: 'primary.main' }} />
                    欢迎使用 EchoSub 👋
                  </Typography>
                  <Typography
                    variant="body1"
                    sx={{
                      mb: 2,
                      color: 'text.secondary',
                    }}
                  >
                    轻松管理你的视频翻译项目
                  </Typography>
                  
                  {/* Quick Action Bar */}
                  <Box display="flex" gap={2} flexWrap="wrap">
                    <Button
                      variant="contained"
                      size="large"
                      startIcon={<AddIcon />}
                      onClick={handleCreateJob}
                      sx={{
                        borderRadius: '12px',
                        px: 4,
                        py: 1.5,
                        fontSize: '1rem',
                        fontWeight: 600,
                        backgroundColor: 'primary.main',
                        boxShadow: 'none',
                        '&:hover': {
                          backgroundColor: 'primary.dark',
                          boxShadow: 'none',
                        },
                      }}
                    >
                      New Project
                    </Button>
                    <Button
                      variant="outlined"
                      size="large"
                      startIcon={<AnalyticsIcon />}
                      onClick={() => navigate('/dashboard/projects')}
                      sx={{
                        borderRadius: '12px',
                        px: 4,
                        py: 1.5,
                        fontSize: '1rem',
                        fontWeight: 600,
                        borderColor: 'divider',
                        color: 'text.primary',
                        '&:hover': {
                          borderColor: 'text.secondary',
                          backgroundColor: 'rgba(0,0,0,0.02)',
                        },
                      }}
                    >
                      查看全部项目
                    </Button>
                  </Box>
                </Box>
              
            </Box>
            
            {/* Stats Cards */}
              <Grid container spacing={2} mb={3}>
                {statCards.map((card) => {
                  const IconComponent = card.icon;
                  return (
                    <Grid item xs={6} sm={3} key={card.title}>
                        <Card
                          sx={{
                            borderRadius: '12px',
                            border: '1px solid',
                            borderColor: 'divider',
                            boxShadow: 'none',
                          }}
                        >
                          <CardContent sx={{ p: 2 }}>
                            <Box display="flex" alignItems="center" gap={1.5}>
                              <IconComponent sx={{ fontSize: 24, color: card.color }} />
                              <Box>
                                <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary', lineHeight: 1 }}>
                                  {card.value}
                                </Typography>
                                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                  {card.title}
                                </Typography>
                              </Box>
                            </Box>
                          </CardContent>
                        </Card>
                      
                    </Grid>
                  );
                })}
              </Grid>
            
            
            {/* Recent Projects */}
              <Box>
                <Box mb={1.5} display="flex" alignItems="center" justifyContent="space-between">
                  <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    最近的项目
                  </Typography>
                  {jobs && jobs.length > 6 && (
                    <Button size="small" onClick={() => navigate('/dashboard/projects')}>
                      查看全部 ({jobs.length})
                    </Button>
                  )}
                </Box>
                
                {jobs && jobs.length > 0 ? (
                  <Grid container spacing={2}>
                    {recentJobs.map((job) => (
                      <Grid item xs={12} sm={6} md={4} key={job.id}>
                          <Card
                            sx={{
                              cursor: 'pointer',
                              borderRadius: '8px',
                              border: '1px solid',
                              borderColor: 'divider',
                              boxShadow: 'none',
                              overflow: 'hidden',
                            }}
                            onClick={() => {
                              if (job.status.toLowerCase() === 'processing') {
                                navigate(`/dashboard/job-processing/${job.user_job_number}`);
                              } else {
                                navigate(`/dashboard/preview/${job.user_job_number}`);
                              }
                            }}
                          >
                            <Box sx={{ position: 'relative', height: 160, bgcolor: 'grey.100', overflow: 'hidden' }}>
                              <CardMedia
                                component="img"
                                height="160"
                                image={ThumbnailService.getThumbnailUrl(job.id, 'medium')}
                                alt={job.title || ''}
                                sx={{ objectFit: 'cover', width: '100%', height: '100%' }}
                                onError={(e) => { e.currentTarget.style.display = 'none'; }}
                              />
                            </Box>
                            
                            <CardContent sx={{ p: 1.5, pb: '8px !important' }}>
                              <Typography variant="body2" noWrap title={job.title} sx={{ fontWeight: 600 }}>
                                {job.title}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {job.source_language?.toUpperCase()} → {job.target_languages?.toUpperCase()}
                              </Typography>
                            </CardContent>
                          </Card>
                        
                      </Grid>
                    ))}
                  </Grid>
                ) : (
                  <Card sx={{ p: 4, textAlign: 'center', borderRadius: '12px', border: '2px dashed', borderColor: 'divider', boxShadow: 'none' }}>
                    <VideoLibraryIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                      还没有项目
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      创建你的第一个视频翻译项目
                    </Typography>
                    <Button variant="contained" startIcon={<UploadIcon />} onClick={handleCreateJob}>
                      新建任务
                    </Button>
                  </Card>
                )}
              </Box>
            
          </Box>
        
      </Container>
    </Box>
  );
};

export default Dashboard;
