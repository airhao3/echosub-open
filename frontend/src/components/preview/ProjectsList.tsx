import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
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
} from '@mui/material';
import { Add as AddIcon, Visibility as ViewIcon, Download as DownloadIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { getJobs, deleteJob, Job } from '../../services/api/jobService';

interface ProjectsListProps {
  onSelectJob?: (jobId: number) => void;
}

export function ProjectsList({ onSelectJob }: ProjectsListProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [selectedJobId, setSelectedJobId] = React.useState<number | null>(null);
  
  const { data: jobs, isLoading, error } = useQuery('jobs', getJobs);
  
  const deleteJobMutation = useMutation(deleteJob, {
    onSuccess: () => {
      queryClient.invalidateQueries('jobs');
      setDeleteDialogOpen(false);
    },
  });

  // Filter completed jobs
  const completedJobs = React.useMemo(() => {
    return (jobs || [])
      .filter((job: Job) => job.status?.toLowerCase() === 'completed')
      .sort((a: Job, b: Job) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [jobs]);

  const handleViewJob = (jobId: number) => {
    if (onSelectJob) {
      onSelectJob(jobId);
    } else {
      navigate(`/dashboard/jobs/${jobId}`);
    }
  };

  const handleCreateNew = () => {
    navigate('/dashboard/jobs/new');
  };

  const handleDeleteClick = (jobId: number) => {
    setSelectedJobId(jobId);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (selectedJobId) {
      deleteJobMutation.mutate(selectedJobId);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSelectedJobId(null);
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" my={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box my={4}>
        <Alert severity="error">Failed to load projects</Alert>
      </Box>
    );
  }

  if (completedJobs.length === 0) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>No Completed Projects</Typography>
        <Typography color="text.secondary" paragraph>
          Your completed translation projects will appear here.
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreateNew}
          sx={{ mt: 2 }}
        >
          Start a New Project
        </Button>
      </Paper>
    );
  }

  return (
    <Box>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Project Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created At</TableCell>
              <TableCell>Source Language</TableCell>
              <TableCell>Target Languages</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {completedJobs.map((job: Job) => (
              <TableRow key={job.id} hover>
                <TableCell>{job.title || `Project ${job.id}`}</TableCell>
                <TableCell>
                  <Chip 
                    label={job.status} 
                    color="success"
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {new Date(job.created_at).toLocaleString()}
                </TableCell>
                <TableCell>{job.source_language || 'Auto'}</TableCell>
                <TableCell>
                  {Array.isArray(job.target_languages) 
                    ? job.target_languages.join(', ') 
                    : job.target_languages || 'N/A'}
                </TableCell>
                <TableCell>
                  <IconButton 
                    onClick={() => handleViewJob(job.id)}
                    title="View Project"
                    size="small"
                    sx={{ mr: 1 }}
                  >
                    <ViewIcon />
                  </IconButton>
                  <IconButton 
                    href={`/api/jobs/${job.id}/download`}
                    title="Download Project"
                    size="small"
                    sx={{ mr: 1 }}
                  >
                    <DownloadIcon />
                  </IconButton>
                  <IconButton 
                    onClick={() => handleDeleteClick(job.id)}
                    title="Delete Project"
                    size="small"
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
      >
        <DialogTitle id="delete-dialog-title">Delete Project</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this project? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} color="primary">
            Cancel
          </Button>
          <Button 
            onClick={handleDeleteConfirm} 
            color="error" 
            variant="contained"
            disabled={deleteJobMutation.isLoading}
            startIcon={deleteJobMutation.isLoading ? <CircularProgress size={20} /> : null}
          >
            {deleteJobMutation.isLoading ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
