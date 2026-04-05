import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Download as DownloadIcon,
  Publish as PublishIcon,
  FileDownload as FileDownloadIcon,
  CheckCircle as CheckCircleIcon,
  Description as DescriptionIcon,
  Movie as MovieIcon,
  Subtitles as SubtitlesIcon,
} from '@mui/icons-material';
import { subtitleVersionService } from '../../services/api/subtitleVersionService';
import { subtitleEditService } from '../../services/api/subtitleEditService';
import { useNotificationContext } from '../common/NotificationProvider';

interface SubtitleExportDialogProps {
  open: boolean;
  onClose: () => void;
  jobId: number;
  language: string;
  jobTitle?: string;
}

type ExportFormat = 'srt' | 'vtt' | 'ass';

const SubtitleExportDialog: React.FC<SubtitleExportDialogProps> = ({
  open,
  onClose,
  jobId,
  language,
  jobTitle = 'Subtitle File',
}) => {
  const { showSuccess, showError } = useNotificationContext();
  const [exportFormat, setExportFormat] = useState<ExportFormat>('srt');
  const [isExporting, setIsExporting] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const formatOptions = [
    { value: 'srt', label: 'SRT Format', description: 'Universal format, best compatibility' },
    { value: 'vtt', label: 'WebVTT Format', description: 'Standard for web video subtitles' },
    { value: 'ass', label: 'ASS Format', description: 'Advanced format with styling support' },
  ];

  // Export subtitle file
  const handleExport = async () => {
    try {
      setIsExporting(true);
      
      const downloadUrl = await subtitleEditService.exportEditedSubtitles(
        jobId,
        language,
        exportFormat
      );

      // Create download link
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${jobTitle}_${language}.${exportFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Clean up URL
      window.URL.revokeObjectURL(downloadUrl);

      showSuccess(`${exportFormat.toUpperCase()} file exported successfully`);
    } catch (error: any) {
      showError(error.message || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  // Publish current version
  const handlePublish = async () => {
    try {
      setIsPublishing(true);
      
      const result = await subtitleVersionService.publishVersion(
        jobId,
        language,
        undefined,
        'Official Release Version'
      );

      if (result.success) {
        showSuccess('Version published successfully');
        onClose();
      }
    } catch (error: any) {
      showError(error.message || 'Publish failed');
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <FileDownloadIcon />
          <Typography variant="h6">Export and Publish</Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Alert severity="info" sx={{ mb: 2 }}>
            Select an export format to download the subtitle file, or publish the current version as the official one.
          </Alert>

          <Typography variant="subtitle1" gutterBottom>
            Job Information
          </Typography>
          <Box sx={{ mb: 2 }}>
            <Chip
              icon={<MovieIcon />}
              label={jobTitle}
              color="primary"
              variant="outlined"
              sx={{ mr: 1, mb: 1 }}
            />
            <Chip
              icon={<SubtitlesIcon />}
              label={`Language: ${language === 'zh' ? 'Chinese' : language === 'en' ? 'English' : language}`}
              color="secondary"
              variant="outlined"
              sx={{ mr: 1, mb: 1 }}
            />
          </Box>
        </Box>

        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Export Format
          </Typography>
          <FormControl fullWidth>
            <InputLabel>Select Format</InputLabel>
            <Select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
              label="Select Format"
            >
              {formatOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  <Box>
                    <Typography variant="body1">{option.label}</Typography>
                    <Typography variant="caption" color="textSecondary">
                      {option.description}
                    </Typography>
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Available Actions
          </Typography>
          <List dense>
            <ListItem>
              <ListItemIcon>
                <DownloadIcon color="primary" />
              </ListItemIcon>
              <ListItemText
                primary="Export Subtitle File"
                secondary="Download the edited subtitle file to your local machine"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <PublishIcon color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Publish Official Version"
                secondary="Save the current edited state as the official published version"
              />
            </ListItem>
          </List>
        </Box>

        {/* Progress Indicator */}
        {(isExporting || isPublishing) && (
          <Box sx={{ mb: 2 }}>
            <LinearProgress />
            <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
              {isExporting ? 'Exporting file...' : 'Publishing version...'}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={isExporting || isPublishing}>
          Cancel
        </Button>
        
        <Button
          startIcon={<DownloadIcon />}
          onClick={handleExport}
          disabled={isExporting || isPublishing}
          variant="outlined"
        >
          {isExporting ? 'Exporting...' : 'Export File'}
        </Button>
        
        <Button
          startIcon={<PublishIcon />}
          onClick={handlePublish}
          disabled={isExporting || isPublishing}
          variant="contained"
          color="success"
        >
          {isPublishing ? 'Publishing...' : 'Publish Version'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SubtitleExportDialog;
