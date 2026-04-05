import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Typography,
  Box,
  Chip,
  Divider,
  CircularProgress,
  Alert,
  Tooltip,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  Restore as RestoreIcon,
  Publish as PublishIcon,
  Compare as CompareIcon,
  MoreVert as MoreVertIcon,
  Save as SaveIcon,
  History as HistoryIcon,
  AutoMode as AutoModeIcon,
  CheckCircle as CheckCircleIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { subtitleVersionService, SubtitleVersion } from '../../services/api/subtitleVersionService';
import { useNotificationContext } from '../common/NotificationProvider';

interface SubtitleVersionDialogProps {
  open: boolean;
  onClose: () => void;
  jobId: number;
  language: string;
  onVersionRestore?: (versionId: string, subtitles: any[]) => void;
  onVersionPublish?: (versionId: string) => void;
}

const SubtitleVersionDialog: React.FC<SubtitleVersionDialogProps> = ({
  open,
  onClose,
  jobId,
  language,
  onVersionRestore,
  onVersionPublish,
}) => {
  const { showSuccess, showError, showWarning } = useNotificationContext();
  const [versions, setVersions] = useState<SubtitleVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [includeAutoSaves, setIncludeAutoSaves] = useState(true);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuVersionId, setMenuVersionId] = useState<string | null>(null);

  // Load version history
  const loadVersionHistory = async () => {
    if (!jobId || !language) return;

    setLoading(true);
    try {
      const history = await subtitleVersionService.getVersionHistory(
        jobId,
        language,
        includeAutoSaves
      );
      setVersions(history);
    } catch (error) {
      console.error('Failed to load version history:', error);
      showError('Failed to load version history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadVersionHistory();
    }
  }, [open, jobId, language, includeAutoSaves]);

  // Restore version
  const handleRestoreVersion = async (versionId: string) => {
    try {
      setLoading(true);
      const result = await subtitleVersionService.restoreVersion(jobId, language, versionId);
      
      if (result.success) {
        showSuccess('Version restored successfully');
        onVersionRestore?.(versionId, result.subtitles);
        loadVersionHistory(); // Reload history
      }
    } catch (error: any) {
      showError(error.message || 'Failed to restore version');
    } finally {
      setLoading(false);
    }
  };

  // Publish version
  const handlePublishVersion = async (versionId: string) => {
    try {
      setLoading(true);
      const result = await subtitleVersionService.publishVersion(jobId, language, versionId);
      
      if (result.success) {
        showSuccess('Version published successfully');
        onVersionPublish?.(versionId);
        loadVersionHistory(); // Reload history
      }
    } catch (error: any) {
      showError(error.message || 'Failed to publish version');
    } finally {
      setLoading(false);
    }
  };

  // Save current edit as a new version
  const handleSaveCurrentVersion = async () => {
    try {
      // This needs to get the current subtitle data from the parent component
      showWarning('This feature needs to be implemented in the editor');
    } catch (error: any) {
      showError(error.message || 'Failed to save version');
    }
  };

  // Compare versions
  const handleCompareVersions = () => {
    if (selectedVersions.length !== 2) {
      showWarning('Please select two versions to compare');
      return;
    }
    
    // TODO: Implement version comparison UI
    showWarning('Version comparison feature is under development');
  };

  // Clean up old versions
  const handleCleanupVersions = async () => {
    try {
      setLoading(true);
      const result = await subtitleVersionService.cleanupOldVersions(jobId, language, 20);
      
      if (result.success && result.deleted_count > 0) {
        showSuccess(`Cleaned up ${result.deleted_count} old versions`);
        loadVersionHistory();
      } else {
        showWarning('No versions to clean up');
      }
    } catch (error: any) {
      showError(error.message || 'Failed to clean up versions');
    } finally {
      setLoading(false);
    }
  };

  // Version menu actions
  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, versionId: string) => {
    setAnchorEl(event.currentTarget);
    setMenuVersionId(versionId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuVersionId(null);
  };

  // Version selection toggle
  const handleVersionSelect = (versionId: string) => {
    setSelectedVersions(prev => {
      if (prev.includes(versionId)) {
        return prev.filter(id => id !== versionId);
      } else if (prev.length < 2) {
        return [...prev, versionId];
      } else {
        return [prev[1], versionId]; // Replace the first selection
      }
    });
  };

  const getVersionTypeChip = (version: SubtitleVersion) => {
    if (version.is_current) {
      return (
        <Chip 
          size="small" 
          label="Current"
          color="success" 
          icon={<CheckCircleIcon />}
        />
      );
    } else if (version.is_auto_save) {
      return (
        <Chip 
          size="small" 
          label="Auto-save"
          color="info" 
          variant="outlined"
          icon={<AutoModeIcon />}
        />
      );
    } else {
      return (
        <Chip 
          size="small" 
          label="Manual Save"
          color="primary" 
          variant="outlined"
          icon={<SaveIcon />}
        />
      );
    }
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <HistoryIcon />
            <Typography variant="h6">Version History</Typography>
            <Typography variant="body2" color="textSecondary">
              ({language})
            </Typography>
          </Box>
        </DialogTitle>

        <DialogContent>
          {loading && (
            <Box display="flex" justifyContent="center" p={2}>
              <CircularProgress />
            </Box>
          )}

          {!loading && versions.length === 0 && (
            <Alert severity="info">
              No version history found.
            </Alert>
          )}

          {!loading && versions.length > 0 && (
            <List>
              {versions.map((version, index) => (
                <React.Fragment key={version.id}>
                  <ListItem
                    button
                    selected={selectedVersions.includes(version.id)}
                    onClick={() => handleVersionSelect(version.id)}
                    sx={{
                      border: selectedVersions.includes(version.id) 
                        ? '2px solid #1976d2' 
                        : '1px solid transparent',
                      borderRadius: 1,
                      mb: 1
                    }}
                  >
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="subtitle1">
                            Version {version.version_number}
                          </Typography>
                          {getVersionTypeChip(version)}
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="textSecondary">
                            {version.description}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {subtitleVersionService.formatVersionTime(version.created_at)} • 
                            {version.subtitle_count} subtitles • 
                            {subtitleVersionService.formatFileSize(version.file_size)}
                          </Typography>
                        </Box>
                      }
                    />
                    
                    <ListItemSecondaryAction>
                      <Box display="flex" alignItems="center" gap={1}>
                        {!version.is_current && (
                          <Tooltip title="Restore this version">
                            <IconButton
                              edge="end"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRestoreVersion(version.id);
                              }}
                              disabled={loading}
                            >
                              <RestoreIcon />
                            </IconButton>
                          </Tooltip>
                        )}
                        
                        <Tooltip title="Publish this version">
                          <IconButton
                            edge="end"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePublishVersion(version.id);
                            }}
                            disabled={loading}
                          >
                            <PublishIcon />
                          </IconButton>
                        </Tooltip>

                        <IconButton
                          edge="end"
                          onClick={(e) => handleMenuClick(e, version.id)}
                        >
                          <MoreVertIcon />
                        </IconButton>
                      </Box>
                    </ListItemSecondaryAction>
                  </ListItem>
                  
                  {index < versions.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          )}
        </DialogContent>

        <DialogActions>
          <Box display="flex" justifyContent="space-between" width="100%">
            <Box display="flex" gap={1}>
              <Button
                startIcon={<CompareIcon />}
                onClick={handleCompareVersions}
                disabled={selectedVersions.length !== 2}
                variant="outlined"
              >
                Compare Versions
              </Button>
              
              <Button
                startIcon={<DeleteIcon />}
                onClick={handleCleanupVersions}
                disabled={loading}
                variant="outlined"
                color="warning"
              >
                Clean Up Old Versions
              </Button>
            </Box>

            <Box display="flex" gap={1}>
              <Button onClick={onClose}>
                Close
              </Button>
              
              <Button
                startIcon={<SaveIcon />}
                onClick={handleSaveCurrentVersion}
                variant="contained"
                disabled={loading}
              >
                Save Current Version
              </Button>
            </Box>
          </Box>
        </DialogActions>
      </Dialog>

      {/* Version Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => {
          if (menuVersionId) {
            handleRestoreVersion(menuVersionId);
          }
          handleMenuClose();
        }}>
          <RestoreIcon sx={{ mr: 1 }} />
          Restore this version
        </MenuItem>
        
        <MenuItem onClick={() => {
          if (menuVersionId) {
            handlePublishVersion(menuVersionId);
          }
          handleMenuClose();
        }}>
          <PublishIcon sx={{ mr: 1 }} />
          Publish this version
        </MenuItem>
      </Menu>
    </>
  );
};

export default SubtitleVersionDialog;
