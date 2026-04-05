import React, { useState } from 'react';
import { useQuery } from 'react-query';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  IconButton,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Checkbox,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Cancel as CancelIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';

import { getUserJobs, cancelUserJob, deleteUserJob, deleteMultipleUserJobs } from '../../services/api/jobService';

const Jobs: React.FC = () => {
  const navigate = useNavigate();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([]);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  
  const { data: jobs, isLoading, error, refetch } = useQuery(
    'jobs',
    getUserJobs
  );
  
    const handleSelectAllClick = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelecteds = jobs ? jobs.map((n) => n.user_job_number) : [];
      setSelectedJobIds(newSelecteds);
      return;
    }
    setSelectedJobIds([]);
  };

  const handleSelectOneClick = (id: number) => {
    const selectedIndex = selectedJobIds.indexOf(id);
    let newSelected: number[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selectedJobIds, id);
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

  const handleCreateJob = () => {
    navigate('/dashboard/jobs/new');
  };
  
  const handleViewJob = (userJobNumber: number) => {
    navigate(`/dashboard/jobs/${userJobNumber}`);
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
    if (selectedJobId) {
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
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    );
  }
  
  if (error) {
    return (
      <Box p={3}>
        <Typography color="error" variant="h6">
          Error loading data. Please refresh the page or try again later.
        </Typography>
      </Box>
    );
  }
  
  return (
    <Box p={3}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Typography variant="h4" component="h1" gutterBottom>
          My Video Jobs
        </Typography>
        <Box>
          {selectedJobIds.length > 0 && (
            <Button
              variant="contained"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleBulkDeleteClick}
              sx={{ mr: 2 }}
            >
              Delete Selected ({selectedJobIds.length})
            </Button>
          )}
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleCreateJob}
          >
            New Video Job
          </Button>
        </Box>
      </Box>
      
      {jobs && jobs.length > 0 ? (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    indeterminate={
                      selectedJobIds.length > 0 && selectedJobIds.length < (jobs?.length || 0)
                    }
                    checked={jobs && jobs.length > 0 && selectedJobIds.length === jobs.length}
                    onChange={handleSelectAllClick}
                    inputProps={{ 'aria-label': 'select all jobs' }}
                  />
                </TableCell>
                <TableCell>Job Name</TableCell>
                <TableCell>Source Language</TableCell>
                <TableCell>Target Language</TableCell>
                <TableCell>Created At</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {jobs.map((job) => {
                const isSelected = selectedJobIds.indexOf(job.user_job_number) !== -1;
                return (
                  <TableRow
                    key={job.id}
                    selected={isSelected}
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        color="primary"
                        checked={isSelected}
                        onChange={() => handleSelectOneClick(job.user_job_number)}
                        inputProps={{ 'aria-labelledby': `job-checkbox-${job.id}` }}
                      />
                    </TableCell>
                    <TableCell component="th" scope="row" id={`job-checkbox-${job.id}`}>
                      {job.title}
                    </TableCell>
                    <TableCell>{job.source_language}</TableCell>
                    <TableCell>{job.target_languages}</TableCell>
                    <TableCell>
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={job.status}
                        color={getStatusChipColor(job.status) as any}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton
                        color="primary"
                        onClick={() => handleViewJob(job.user_job_number)}
                        title="View Details"
                      >
                        <ViewIcon />
                      </IconButton>
                      
                      {['pending', 'processing'].includes(job.status.toLowerCase()) && (
                        <IconButton
                          color="warning"
                          onClick={() => handleCancelJob(job.user_job_number)}
                          title="Cancel Job"
                        >
                          <CancelIcon />
                        </IconButton>
                      )}
                      
                      {job.status.toLowerCase() === 'completed' && (
                        <IconButton
                          color="success"
                          onClick={() => handleViewJob(job.user_job_number)}
                          title="Download Results"
                        >
                          <DownloadIcon />
                        </IconButton>
                      )}
                      
                      <IconButton
                        color="error"
                        onClick={() => handleDeleteClick(job.user_job_number)}
                        title="Delete Job"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Box py={4} display="flex" flexDirection="column" alignItems="center">
          <Typography variant="h6" color="text.secondary" mb={2}>
            You haven't created any video jobs yet
          </Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleCreateJob}
          >
            Create Your First Job
          </Button>
        </Box>
      )}
      
      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
      >
        <DialogTitle>Delete Confirmation</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this video job? This action cannot be undone, and all related files and records will be deleted.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} color="primary">
            Cancel
          </Button>
          <Button onClick={handleDeleteConfirm} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog
        open={bulkDeleteDialogOpen}
        onClose={handleBulkDeleteCancel}
      >
        <DialogTitle>Confirm Bulk Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the selected {selectedJobIds.length} jobs? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleBulkDeleteCancel} color="primary">
            Cancel
          </Button>
          <Button onClick={handleBulkDeleteConfirm} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Jobs;
