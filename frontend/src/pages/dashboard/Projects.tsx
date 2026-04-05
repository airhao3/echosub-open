import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  TextField,
  InputAdornment,
  CircularProgress,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Button,
  Checkbox,
  Container,
  Card,
  CardContent,
  Avatar,
  useTheme,
  alpha,
  Grid,
  Pagination,
  ToggleButton,
  ToggleButtonGroup,
  CardMedia,
  Skeleton,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterListIcon,
  Visibility as ViewIcon,
  Cancel as CancelIcon,
  Download as DownloadIcon,
  Delete as DeleteIcon,
  VideoLibrary as VideoLibraryIcon,
  Analytics as AnalyticsIcon,
  Add as AddIcon,
  AutoAwesome as AutoAwesomeIcon,
  PlayCircleFilled as PlayIcon,
  AccessTime as TimeIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  Tune as TuneIcon,
  ViewList as ViewListIcon,
  ViewModule as ViewModuleIcon,
  Image as ImageIcon,
} from '@mui/icons-material';

import { getUserJobs, deleteUserJob, cancelUserJob, deleteMultipleUserJobs } from '../../services/api/jobService';
import { VideoThumbnailCard } from './components/VideoThumbnailCard';

// Use jobService functions directly

// Using a named export to prevent circular dependency issues
export const Projects: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([]);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  
  // View mode and pagination states
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('grid');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(8); // Default 8 for grid view (2 rows × 4 columns)
  
  useEffect(() => {
  }, []);

  const { data: jobs, isLoading, error, refetch } = useQuery('userJobs', getUserJobs);

  const handleSelectAllClick = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelecteds = filteredJobs.map((n) => n.user_job_number);
      setSelectedJobIds(newSelecteds);
      return;
    }
    setSelectedJobIds([]);
  };

  const handleSelectOneClick = (userJobNumber: number) => {
    const selectedIndex = selectedJobIds.indexOf(userJobNumber);
    let newSelected: number[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selectedJobIds, userJobNumber);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selectedJobIds.slice(1));
    } else if (selectedIndex === selectedJobIds.length - 1) {
      newSelected = newSelected.concat(selectedJobIds.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selectedJobIds.slice(0, selectedIndex),
        selectedJobIds.slice(selectedIndex + 1),
      );
    }
    setSelectedJobIds(newSelected);
  };

  const handleBulkDeleteClick = () => {
    setBulkDeleteDialogOpen(true);
  };

  const handleBulkDeleteConfirm = async () => {
    try {
      await deleteMultipleUserJobs(selectedJobIds);
      setBulkDeleteDialogOpen(false);
      setSelectedJobIds([]);
      refetch();
    } catch (error) {
      console.error('Error deleting multiple jobs:', error);
    }
  };

  const handleBulkDeleteCancel = () => {
    setBulkDeleteDialogOpen(false);
  };

  const filteredJobs = jobs?.filter((job: { user_job_number: number; title: string; status: string }) => {
    const searchTermLower = searchTerm.toLowerCase();
    const title = job.title?.toString() || '';
    const userJobNumber = job.user_job_number?.toString() || '';
    const status = job.status?.toString() || '';
    
    const matchesSearch = title.toLowerCase().includes(searchTermLower) ||
      userJobNumber.toLowerCase().includes(searchTermLower);
    const matchesStatus = statusFilter === 'all' || status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  }) || [];

  // Pagination logic
  const totalPages = Math.ceil(filteredJobs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedJobs = filteredJobs.slice(startIndex, startIndex + itemsPerPage);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter]);

  // Adjust items per page when view mode changes
  useEffect(() => {
    if (viewMode === 'list') {
      setItemsPerPage(10); // Default for list view
    } else {
      setItemsPerPage(8); // Default for grid view (2 rows × 4 columns)
    }
    setCurrentPage(1);
  }, [viewMode]);

  const handleViewJob = (userJobNumber: number) => {
    navigate(`/dashboard/preview/${userJobNumber}`);
  };



  
  
  const handleCancelJob = async (userJobNumber: number) => {
    try {
      await cancelUserJob(userJobNumber);
      refetch();
    } catch (error) {
      console.error('Error cancelling job:', error);
    }
  };
  
  const handleDeleteClick = (userJobNumber: number) => {
    setSelectedJobId(userJobNumber);
    setDeleteDialogOpen(true);
  };
  
  const handleDeleteConfirm = async () => {
    if (selectedJobId !== null) {
      try {
        await deleteUserJob(selectedJobId);
        setDeleteDialogOpen(false);
        refetch();
      } catch (error) {
        console.error('Error deleting job:', error);
      }
    }
  };
  
  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSelectedJobId(null);
  };
  
  const getStatusChipColor = (status: string) => {
    const statusLower = status.toLowerCase();
    switch (statusLower) {
      case 'pending':
        return 'warning';
      case 'processing':
        return 'info';
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'cancelled':
        return 'default';
      default:
        return 'default';
    }
  };

  if (isLoading) {
    return (
      <Box 
        display="flex" 
        justifyContent="center" 
        alignItems="center" 
        minHeight="80vh"
        sx={{
          background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(theme.palette.secondary.main, 0.05)} 100%)`
        }}
      >
        <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
          <CircularProgress size={60} thickness={4} />
          <Typography variant="h6" color="text.secondary">
            Loading your projects...
          </Typography>
        </Box>
      </Box>
    );
  }


  return (
    <Box
      sx={{
        background: theme.palette.background.default,
        height: '100vh', overflow: 'auto',
        pb: 2,
        position: 'relative',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 50%)',
          zIndex: 0,
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          top: '20%',
          right: '10%',
          width: '200px',
          height: '200px',
          borderRadius: '50%',
          background: `conic-gradient(from 0deg, 
            ${alpha(theme.palette.primary.main, 0.1)} 0deg,
            ${alpha(theme.palette.secondary.main, 0.08)} 120deg,
            ${alpha(theme.palette.primary.light, 0.06)} 240deg,
            ${alpha(theme.palette.primary.main, 0.1)} 360deg
          )`,
          zIndex: 0,
        },
      }}
    >
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
        
          <Box pt={2} pb={1}>
            {/* Header Section */}
            <Box mb={2}>
              
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3}>
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
                        <AnalyticsIcon sx={{ fontSize: 36, color: 'primary.main' }} />
                        我的项目
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{
                          mb: 2,
                          color: 'text.secondary',
                        }}
                      >
                        管理和跟踪所有视频翻译项目
                      </Typography>
                    </Box>
                    
                    <Box display="flex" gap={2} flexWrap="wrap">
                      {selectedJobIds.length > 0 && (
                        <Button
                          variant="contained"
                          color="error"
                          startIcon={<DeleteIcon />}
                          onClick={handleBulkDeleteClick}
                          sx={{
                            borderRadius: '12px',
                            px: 3,
                            py: 1.5,
                            fontWeight: 600,
                            boxShadow: '0 4px 16px rgba(211, 47, 47, 0.3)'
                          }}
                        >
                          删除所选 ({selectedJobIds.length})
                        </Button>
                      )}
                      <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => navigate('/dashboard/upload')}
                        sx={{
                          borderRadius: '12px',
                          px: 3,
                          py: 1.5,
                          fontSize: '1rem',
                          fontWeight: 600,
                          background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                          boxShadow: `0 8px 25px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.1)`,
                          '&:hover': {
                            
                            boxShadow: `0 12px 35px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.2)`,
                          },
                        }}
                      >
                        New Project
                      </Button>
                    </Box>
                  </Box>
                  
                  {/* Search and Filter Section */}
                  <Card
                    sx={{
                      background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
                      backdropFilter: 'blur(20px)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      borderRadius: '20px',
                      overflow: 'hidden',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
                      mb: 4
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Box display="flex" gap={2} flexWrap="wrap" alignItems="center" sx={{ width: '100%' }}>
                        <TextField
                          placeholder="搜索项目..."
                          variant="outlined"
                          size="small"
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          InputProps={{
                            startAdornment: (
                              <InputAdornment position="start">
                                <SearchIcon sx={{ color: 'primary.main' }} />
                              </InputAdornment>
                            ),
                          }}
                          sx={{ 
                            flex: 1,
                            minWidth: 250,
                            maxWidth: 350,
                            '& .MuiOutlinedInput-root': {
                              borderRadius: '12px',
                              backgroundColor: 'rgba(255,255,255,0.8)',
                              '&:hover': {
                                backgroundColor: 'rgba(255,255,255,0.9)',
                              },
                            }
                          }}
                        />
                        
                        <FormControl variant="outlined" size="small" sx={{ minWidth: 150, maxWidth: 200 }}>
                          <InputLabel>Status</InputLabel>
                          <Select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as string)}
                            label="Status"
                            startAdornment={
                              <InputAdornment position="start">
                                <FilterListIcon sx={{ color: 'primary.main' }} />
                              </InputAdornment>
                            }
                            sx={{
                              borderRadius: '12px',
                              backgroundColor: 'rgba(255,255,255,0.8)',
                              '&:hover': {
                                backgroundColor: 'rgba(255,255,255,0.9)',
                              },
                            }}
                          >
                            <MenuItem value="all">全部状态</MenuItem>
                            <MenuItem value="pending">等待中</MenuItem>
                            <MenuItem value="processing">处理中</MenuItem>
                            <MenuItem value="completed">已完成</MenuItem>
                            <MenuItem value="failed">失败</MenuItem>
                            <MenuItem value="cancelled">已取消</MenuItem>
                          </Select>
                        </FormControl>

                        {/* View Mode Toggle */}
                        <ToggleButtonGroup
                          value={viewMode}
                          exclusive
                          onChange={(e, newMode) => newMode && setViewMode(newMode)}
                          size="small"
                          sx={{
                            backgroundColor: 'rgba(255,255,255,0.8)',
                            borderRadius: '12px',
                          }}
                        >
                          <ToggleButton value="list" sx={{ borderRadius: '12px 0 0 12px' }}>
                            <ViewListIcon />
                          </ToggleButton>
                          <ToggleButton value="grid" sx={{ borderRadius: '0 12px 12px 0' }}>
                            <ViewModuleIcon />
                          </ToggleButton>
                        </ToggleButtonGroup>

                        {/* Items per page selector */}
                        <FormControl variant="outlined" size="small" sx={{ minWidth: 100, maxWidth: 150 }}>
                          <InputLabel>Per Page</InputLabel>
                          <Select
                            value={itemsPerPage}
                            onChange={(e) => {
                              setItemsPerPage(Number(e.target.value));
                              setCurrentPage(1);
                            }}
                            label="Per Page"
                            sx={{
                              borderRadius: '12px',
                              backgroundColor: 'rgba(255,255,255,0.8)',
                            }}
                          >
                            <MenuItem value={5}>5</MenuItem>
                            <MenuItem value={8}>8</MenuItem>
                            <MenuItem value={10}>10</MenuItem>
                            <MenuItem value={12}>12</MenuItem>
                            <MenuItem value={16}>16</MenuItem>
                            <MenuItem value={20}>20</MenuItem>
                            <MenuItem value={24}>24</MenuItem>
                            <MenuItem value={50}>50</MenuItem>
                          </Select>
                        </FormControl>
                        
                        <Box ml="auto">
                          <Typography variant="body2" color="text.secondary">
                            {filteredJobs.length} project{filteredJobs.length !== 1 ? 's' : ''} found
                            {totalPages > 1 && (
                              <> • Page {currentPage} of {totalPages}</>
                            )}
                          </Typography>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Box>
              
            </Box>
      
            {/* Content Section */}
            
              <Box>
                {error ? (
                  <Card
                    sx={{
                      p: 4,
                      textAlign: 'center',
                      borderRadius: '24px',
                      background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
                      backdropFilter: 'blur(20px)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.1)'
                    }}
                  >
                    <ErrorIcon sx={{ fontSize: 60, color: 'error.main', mb: 2 }} />
                    <Typography color="error" variant="h6" gutterBottom>
                      Error loading projects
                    </Typography>
                    <Typography color="text.secondary">
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
                ) : filteredJobs.length > 0 ? (
                  <>
                    {/* List View */}
                    {viewMode === 'list' ? (
                  <Card
                    sx={{
                      borderRadius: '20px',
                      background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
                      backdropFilter: 'blur(20px)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      overflow: 'hidden',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.1)'
                    }}
                  >
                    <TableContainer sx={{ width: '100%' }}>
                      <Table sx={{ width: '100%' }}>
                        <TableHead>
                          <TableRow sx={{ bgcolor: alpha(theme.palette.primary.main, 0.05) }}>
                            <TableCell padding="checkbox">
                              <Checkbox
                                indeterminate={
                                  selectedJobIds.length > 0 && selectedJobIds.length < filteredJobs.length
                                }
                                checked={paginatedJobs.length > 0 && selectedJobIds.length === filteredJobs.length}
                                onChange={handleSelectAllClick}
                                inputProps={{ 'aria-label': 'select all projects' }}
                                sx={{ color: 'primary.main' }}
                              />
                            </TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 200 }}>Project Name</TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 120 }}>Source Language</TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 120 }}>Target Language</TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 120 }}>Created At</TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 100 }}>Status</TableCell>
                            <TableCell sx={{ fontWeight: 600, fontSize: '0.95rem', minWidth: 200 }}>Actions</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {paginatedJobs.map((job, index) => {
                            const isSelected = selectedJobIds.indexOf(job.user_job_number) !== -1;
                            return (
                              <TableRow key={job.user_job_number}
                                hover
                                onClick={(e) => {
                                  if ((e.target as HTMLElement).closest('.action-buttons')) return;
                                  handleSelectOneClick(job.user_job_number);
                                }}
                                role="checkbox"
                                aria-checked={isSelected}
                                tabIndex={-1}
                                selected={isSelected}
                                sx={{ 
                                  '&:last-child td, &:last-child th': { border: 0 },
                                  '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.04),
                                    transform: 'translateX(4px)',
                                  },
                                  cursor: 'pointer'
                                }}
                              >
                                <TableCell padding="checkbox">
                                  <Checkbox
                                    color="primary"
                                    checked={isSelected}
                                  />
                                </TableCell>
                                <TableCell component="th" scope="row" sx={{ minWidth: 200 }}>
                                  <Box display="flex" alignItems="center" gap={2}>
                                    <Avatar
                                      sx={{
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.2)}, ${alpha(theme.palette.primary.main, 0.1)})`,
                                        width: 40,
                                        height: 40,
                                      }}
                                    >
                                      <VideoLibraryIcon sx={{ fontSize: 20, color: 'primary.main' }} />
                                    </Avatar>
                                    <Box>
                                      <Typography variant="body2" sx={{ fontWeight: 500, wordBreak: 'break-word' }}>
                                        #{job.user_job_number} - {job.title}
                                      </Typography>
                                    </Box>
                                  </Box>
                                </TableCell>
                                <TableCell sx={{ minWidth: 120 }}>
                                  <Chip 
                                    label={job.source_language?.toUpperCase()} 
                                    size="small" 
                                    variant="outlined"
                                    sx={{ 
                                      borderColor: alpha(theme.palette.primary.main, 0.3),
                                      color: 'primary.main',
                                      fontWeight: 500
                                    }}
                                  />
                                </TableCell>
                                <TableCell sx={{ minWidth: 120 }}>
                                  <Chip 
                                    label={job.target_languages?.toUpperCase()} 
                                    size="small" 
                                    variant="outlined"
                                    sx={{ 
                                      borderColor: alpha(theme.palette.secondary.main, 0.3),
                                      color: 'secondary.main',
                                      fontWeight: 500
                                    }}
                                  />
                                </TableCell>
                                <TableCell sx={{ minWidth: 120 }}>
                                  <Box display="flex" alignItems="center" gap={1}>
                                    <TimeIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                                    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                                      {new Date(job.created_at).toLocaleDateString()}
                                    </Typography>
                                  </Box>
                                </TableCell>
                                <TableCell sx={{ minWidth: 100 }}>
                                  <Chip
                                    label={job.status}
                                    size="small"
                                    sx={{
                                      background: (theme) => {
                                        switch (job.status.toLowerCase()) {
                                          case 'pending':
                                            return `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.15)}, ${alpha(theme.palette.warning.main, 0.1)})`;
                                          case 'processing':
                                            return `linear-gradient(135deg, ${alpha(theme.palette.info.main, 0.15)}, ${alpha(theme.palette.info.main, 0.1)})`;
                                          case 'completed':
                                            return `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.15)}, ${alpha(theme.palette.success.main, 0.1)})`;
                                          case 'failed':
                                            return `linear-gradient(135deg, ${alpha(theme.palette.error.main, 0.15)}, ${alpha(theme.palette.error.main, 0.1)})`;
                                          default:
                                            return `linear-gradient(135deg, ${alpha(theme.palette.grey[500], 0.15)}, ${alpha(theme.palette.grey[500], 0.1)})`;
                                        }
                                      },
                                      color: (theme) => {
                                        switch (job.status.toLowerCase()) {
                                          case 'pending':
                                            return theme.palette.warning.main;
                                          case 'processing':
                                            return theme.palette.info.main;
                                          case 'completed':
                                            return theme.palette.success.main;
                                          case 'failed':
                                            return theme.palette.error.main;
                                          default:
                                            return theme.palette.grey[600];
                                        }
                                      },
                                      fontWeight: 600,
                                      borderRadius: '12px',
                                      border: '1px solid rgba(255,255,255,0.2)',
                                    }}
                                  />
                                </TableCell>
                                <TableCell sx={{ minWidth: 200 }}>
                                  <Box display="flex" gap={1} className="action-buttons">
                                    <IconButton
                                      color="primary"
                                      onClick={() => handleViewJob(job.user_job_number)}
                                      title="查看详情"
                                      size="small"
                                      sx={{
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                        '&:hover': {
                                          backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                          transform: 'scale(1.1)',
                                        },
                                      }}
                                    >
                                      <ViewIcon />
                                    </IconButton>

                                    {['pending', 'processing'].includes(job.status.toLowerCase()) && (
                                      <IconButton
                                        color="warning"
                                        onClick={() => handleCancelJob(job.user_job_number)}
                                        title="取消任务"
                                        size="small"
                                        sx={{
                                          backgroundColor: alpha(theme.palette.warning.main, 0.1),
                                          '&:hover': {
                                            backgroundColor: alpha(theme.palette.warning.main, 0.2),
                                            transform: 'scale(1.1)',
                                          },
                                        }}
                                      >
                                        <CancelIcon />
                                      </IconButton>
                                    )}
                                    
                                    {job.status.toLowerCase() === 'completed' && (
                                      <IconButton
                                        color="success"
                                        onClick={() => handleViewJob(job.user_job_number)}
                                        title="Download Results"
                                        size="small"
                                        sx={{
                                          backgroundColor: alpha(theme.palette.success.main, 0.1),
                                          '&:hover': {
                                            backgroundColor: alpha(theme.palette.success.main, 0.2),
                                            transform: 'scale(1.1)',
                                          },
                                        }}
                                      >
                                        <DownloadIcon />
                                      </IconButton>
                                    )}
                                    
                                    {/* Video Parameters button temporarily hidden - focusing on subtitle processing only */}
                                    {/* {job.status.toLowerCase() === 'completed' && (
                                      <IconButton
                                        color="secondary"
                                        onClick={() => navigate(`/dashboard/video-params/${job.user_job_number}`)}
                                        title="Adjust Video Parameters"
                                        size="small"
                                        sx={{
                                          backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                          '&:hover': {
                                            backgroundColor: alpha(theme.palette.secondary.main, 0.2),
                                            transform: 'scale(1.1)',
                                          },
                                        }}
                                      >
                                        <TuneIcon />
                                      </IconButton>
                                    )} */}
                                    
                                    <IconButton
                                      color="error"
                                      onClick={() => handleDeleteClick(job.user_job_number)}
                                      title="删除任务"
                                      size="small"
                                      sx={{
                                        backgroundColor: alpha(theme.palette.error.main, 0.1),
                                        '&:hover': {
                                          backgroundColor: alpha(theme.palette.error.main, 0.2),
                                          transform: 'scale(1.1)',
                                        },
                                      }}
                                    >
                                      <DeleteIcon />
                                    </IconButton>
                                  </Box>
                                </TableCell>
                              </TableRow>
                            
                            );})}
                        </TableBody>
                      </Table>
                    </TableContainer>

                    {/* Pagination Controls for List View */}
                    {totalPages > 1 && (
                      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                        <Pagination
                          count={totalPages}
                          page={currentPage}
                          onChange={(_, page) => setCurrentPage(page)}
                          color="primary"
                          size="large"
                          sx={{
                            '& .MuiPaginationItem-root': {
                              borderRadius: '12px',
                              backgroundColor: 'rgba(255,255,255,0.8)',
                              backdropFilter: 'blur(10px)',
                              '&:hover': {
                                backgroundColor: 'rgba(255,255,255,0.9)',
                              },
                              '&.Mui-selected': {
                                backgroundColor: theme.palette.primary.main,
                                color: 'white',
                              }
                            }
                          }}
                        />
                      </Box>
                    )}
                  </Card>
                    ) : (
                      /* Grid View */
                      <>
                        <Grid container spacing={3} sx={{ mb: 3 }}>
                          {paginatedJobs.map((job, index) => (
                            <Grid item xs={6} sm={6} md={3} lg={3} key={job.user_job_number}>
                              <VideoThumbnailCard 
                                job={job} 
                                index={index} 
                                selectedJobIds={selectedJobIds}
                                onSelectOne={handleSelectOneClick}
                                onDelete={handleDeleteClick}
                              />
                            </Grid>
                          ))}
                        </Grid>

                        {/* Pagination Controls for Grid View */}
                        {totalPages > 1 && (
                          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                            <Pagination
                              count={totalPages}
                              page={currentPage}
                              onChange={(_, page) => setCurrentPage(page)}
                              color="primary"
                              size="large"
                              sx={{
                                '& .MuiPaginationItem-root': {
                                  borderRadius: '12px',
                                  backgroundColor: 'rgba(255,255,255,0.8)',
                                  backdropFilter: 'blur(10px)',
                                  '&:hover': {
                                    backgroundColor: 'rgba(255,255,255,0.9)',
                                  },
                                  '&.Mui-selected': {
                                    backgroundColor: theme.palette.primary.main,
                                    color: 'white',
                                  }
                                }
                              }}
                            />
                          </Box>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <Card
                    sx={{
                      p: 6,
                      textAlign: 'center',
                      borderRadius: '32px',
                      background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
                      backdropFilter: 'blur(30px)',
                      border: '3px dashed rgba(255,255,255,0.4)',
                      boxShadow: '0 25px 60px -10px rgba(0,0,0,0.1)',
                      position: 'relative',
                      overflow: 'hidden',
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        top: '-50%',
                        left: '-50%',
                        right: '-50%',
                        bottom: '-50%',
                        background: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'60\' height=\'60\' viewBox=\'0 0 60 60\'%3E%3Cg fill-opacity=\'0.03\'%3E%3Ccircle fill=\'%23ffffff\' cx=\'30\' cy=\'30\' r=\'2\'/%3E%3C/g%3E%3C/svg%3E")',
                        zIndex: 0,
                      },
                      '&::after': {
                        content: '""',
                        position: 'absolute',
                        top: '10%',
                        right: '10%',
                        width: '150px',
                        height: '150px',
                        borderRadius: '50%',
                        background: `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.1)} 0%, transparent 70%)`,
                        zIndex: 0,
                      },
                    }}
                  >
                    <Box sx={{ position: 'relative', zIndex: 1, mb: 2 }}>
                      <AutoAwesomeIcon 
                        sx={{ 
                          fontSize: 80, 
                          background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                          backgroundClip: 'text',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.1))',
                        }} 
                      />
                    </Box>
                    <Typography 
                      variant="h5" 
                      gutterBottom 
                      sx={{ 
                        fontWeight: 700,
                        position: 'relative',
                        zIndex: 1,
                        background: `linear-gradient(45deg, ${theme.palette.text.primary}, ${alpha(theme.palette.primary.main, 0.8)})`,
                        backgroundClip: 'text',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                      }}
                    >
                      {searchTerm || statusFilter !== 'all' ? '没有匹配的项目' : '暂无项目'}
                    </Typography>
                    <Typography
                      variant="body1"
                      color="text.secondary"
                      sx={{
                        mb: 4,
                        maxWidth: 400,
                        mx: 'auto',
                        position: 'relative',
                        zIndex: 1,
                        lineHeight: 1.6,
                        fontSize: '1.1rem'
                      }}
                    >
                      {searchTerm || statusFilter !== 'all'
                        ? '请尝试调整搜索条件或筛选条件'
                        : '创建你的第一个视频翻译项目，开始多语言内容创作'}
                    </Typography>
                    {(!searchTerm && statusFilter === 'all') && (
                      <Button
                        variant="contained"
                        size="large"
                        startIcon={<AddIcon />}
                        onClick={() => navigate('/dashboard/upload')}
                        sx={{
                          borderRadius: '16px',
                          px: 6,
                          py: 2,
                          fontSize: '1.2rem',
                          fontWeight: 700,
                          position: 'relative',
                          zIndex: 1,
                          background: 'linear-gradient(135deg, #FFD700 0%, #FFA500 100%)',
                          color: '#000',
                          boxShadow: '0 8px 25px rgba(0,0,0,0.3)',
                          minWidth: '220px',
                          '&:hover': {
                            
                            boxShadow: '0 12px 35px rgba(0,0,0,0.4)',
                          },
                        }}
                      >
                        Create Your First Project
                      </Button>
                    )}
                  </Card>
                )}
              </Box>
            
          </Box>
        
      </Container>
      
      {/* Dialogs */}
      <Dialog
        open={bulkDeleteDialogOpen}
        onClose={handleBulkDeleteCancel}
      >
        <DialogTitle>确认批量删除</DialogTitle>
        <DialogContent>
          <DialogContentText>
            确定要删除所选的 {selectedJobIds.length} 个任务吗？此操作无法撤销。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={handleBulkDeleteCancel}
            sx={{ borderRadius: '8px' }}
          >
            取消
          </Button>
          <Button 
            onClick={handleBulkDeleteConfirm} 
            color="error" 
            variant="contained"
            autoFocus
            sx={{ borderRadius: '8px' }}
          >
            删除
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          删除任务
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            确定要删除此任务吗？此操作无法撤销。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={handleDeleteCancel}
            sx={{ borderRadius: '8px' }}
          >
            取消
          </Button>
          <Button 
            onClick={handleDeleteConfirm} 
            color="error" 
            variant="contained"
            autoFocus
            sx={{ borderRadius: '8px' }}
          >
            删除
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// Default export for backward compatibility
export default Projects;
