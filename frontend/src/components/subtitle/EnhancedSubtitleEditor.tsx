import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Subtitle } from '../../utils/subtitleUtils';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  TextField,
  IconButton,
  List,
  ListItem,
  Chip,
  Tooltip,
  Divider,
  ButtonGroup,
} from '@mui/material';
import {
  Add as AddIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
  CallSplit as SplitScreenIcon,
  MergeType as MergeIcon,
  Schedule as ScheduleIcon,
  FileDownload as FileDownloadIcon,
  Save as SaveIcon,
  Restore as RestoreIcon,
  History as HistoryIcon,
} from '@mui/icons-material';
import { previewService } from '../../services/api/previewService';
import { subtitleVersionService } from '../../services/api/subtitleVersionService';
import { debounce } from 'lodash';
import { SxProps, Theme } from '@mui/material';
import TimeAdjustmentDialog from './TimeAdjustmentDialog';
import SplitSubtitleDialog from './SplitSubtitleDialog';
import MergeSubtitleDialogSimple from './MergeSubtitleDialogSimple';
import TimelineOffsetDialogSimple from './TimelineOffsetDialogSimple';
import SubtitleExportDialog from './SubtitleExportDialog';
import InlineTimeRangeSlider from './InlineTimeRangeSlider';
import { useNotificationContext } from '../common/NotificationProvider';
import { subtitleEditService, SubtitleEdit } from '../../services/api/subtitleEditService';

interface LocalSubtitle {
  id: string;
  text: string;
  startTime: number;
  endTime: number;
  language?: string;
}

interface BulkUpdateOperation {
  type: 'BULK_UPDATE';
  language: string;
  subtitles: LocalSubtitle[];
  action: 'split' | 'merge';
  details: any;
}

interface LanguageSubtitles {
  language: string;
  subtitles: LocalSubtitle[];
  loading: boolean;
  error: string | null;
}

interface GroupedSubtitle {
  startTime: number;
  endTime: number;
  subtitlesByLanguage: {
    [language: string]: LocalSubtitle;
  };
}

interface EnhancedSubtitleEditorProps {
  jobId: number | string;
  languages: string[];
  subtitles: LanguageSubtitles[];
  currentTime: number;
  videoDuration?: number; // Video total duration (seconds)
  onSubtitleClick: (time: number) => void;
  onSubtitleSave?: (subtitle: LocalSubtitle, language: string) => void;
  onFrontendCopyUpdate?: (frontendCopy: LanguageSubtitles[]) => void; // Frontend copy update callback
  onPlaySpeedChange?: (speed: number) => void;
  onPlayPause?: () => void;
  isPlaying?: boolean;
  onSaveSuccess?: (subtitles: LanguageSubtitles[]) => void;
  onManualSave?: () => void;
  isSaving?: boolean;
  sx?: SxProps<Theme> & { [key: string]: any };
}



// Editable text component
interface EditableTextProps {
  text: string;
  isEditing: boolean;
  onEdit: (newText: string) => void;
  onStartEdit: (clickPosition?: number) => void;
  onSave: () => void;
  onCancel: () => void;
  // Remove real-time text change callback, only update when save is confirmed
  language: string;
  subtitleId: string;
  emptySubtitles: Set<string>;
}

const EditableText: React.FC<EditableTextProps> = ({
  text,
  isEditing,
  onEdit,
  onStartEdit,
  onSave,
  onCancel,
  language,
  subtitleId,
  emptySubtitles
}) => {
  const spanRef = useRef<HTMLSpanElement>(null);
  const [editText, setEditText] = useState(text);
  const [isComposing, setIsComposing] = useState(false); // Mark if Chinese input method is active

  useEffect(() => {
    setEditText(text);
  }, [text]);

  // Text change handling - only update local state, no real-time preview
  const handleTextChange = (newText: string) => {
    setEditText(newText);
    // Remove real-time preview, only update when user confirms save
  };

  // Handle input method events
  const handleCompositionStart = () => {
    setIsComposing(true);
  };

  const handleCompositionEnd = () => {
    setIsComposing(false);
    // Remove real-time preview after input method completion
  };

  const handleSpanClick = (event: React.MouseEvent<HTMLSpanElement>) => {
    event.stopPropagation();
    
    // Simply start editing, no complex cursor positioning
    onStartEdit(0);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onEdit(editText);
      onSave();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      setEditText(text);
      onCancel();
    }
  };

  const langColor = language === 'en' ? 'primary' : 
                    language === 'zh' ? 'error' : 
                    language === 'auto' ? 'info' : 'success';

  if (isEditing) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          value={editText}
          onChange={(e) => handleTextChange(e.target.value)}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          onKeyDown={handleKeyDown}
          size="small"
          variant="outlined"
          autoFocus
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.9)',
            }
          }}
        />
        <ButtonGroup size="small" orientation="vertical">
          <Tooltip title="保存 (Enter)">
            <IconButton
              size="small"
              color="primary"
              onClick={() => {
                onEdit(editText);
                onSave();
              }}
            >
              <CheckIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="取消 (Esc)">
            <IconButton
              size="small"
              onClick={() => {
                setEditText(text);
                onCancel();
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </ButtonGroup>
      </Box>
    );
  }

  return (
    <Box 
      sx={{ 
        cursor: 'text',
        width: '100%',
        minHeight: '1.5em',
        p: 1,
        borderRadius: 1,
        border: '1px solid transparent',
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
          border: `1px solid ${langColor}.light`,
        },
        transition: 'all 0.2s ease'
      }}
      onClick={(e) => {
        e.stopPropagation(); // Prevent event bubbling
        handleSpanClick(e);
      }}
    >
      <span 
        ref={spanRef}
        style={{ 
          userSelect: 'text',
          WebkitUserSelect: 'text',
          fontSize: '0.875rem'
        }}
      >
        {text || (emptySubtitles.has(subtitleId) ? '点击输入字幕内容...' : '点击编辑...')}
      </span>
    </Box>
  );
};

const EnhancedSubtitleEditor: React.FC<EnhancedSubtitleEditorProps> = ({ 
  jobId, 
  languages, 
  subtitles, 
  currentTime, 
  videoDuration,
  onSubtitleClick,
  onSubtitleSave,
  onFrontendCopyUpdate,
  onPlaySpeedChange,
  onPlayPause,
  isPlaying,
  onSaveSuccess,
  onManualSave,
  isSaving
}) => {
  // Simplified state management: only keep necessary working copy
  const [workingSubtitles, setWorkingSubtitles] = useState<LanguageSubtitles[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  const [groupedSubtitles, setGroupedSubtitles] = useState<GroupedSubtitle[]>([]);
  const [editingSubtitle, setEditingSubtitle] = useState<{id: string, language: string} | null>(null);
  const [emptySubtitles, setEmptySubtitles] = useState<Set<string>>(new Set());
  const [currentSubtitleId, setCurrentSubtitleId] = useState<string | null>(null);
  
  // Dialog states
  const [timeDialogOpen, setTimeDialogOpen] = useState(false);
  const [splitDialogOpen, setSplitDialogOpen] = useState(false);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [offsetDialogOpen, setOffsetDialogOpen] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  
  const [selectedLanguageForOffset, setSelectedLanguageForOffset] = useState<string>('');
  
  // Version management
  const { showSuccess, showError } = useNotificationContext();
  const [isLoadingVersion, setIsLoadingVersion] = useState(false);
  const [selectedSubtitleForDialog, setSelectedSubtitleForDialog] = useState<{
    subtitle: LocalSubtitle;
    language: string;
  } | null>(null);
  const [selectedSubtitleForMerge, setSelectedSubtitleForMerge] = useState<{
    current: LocalSubtitle;
    next: LocalSubtitle;
    language: string;
  } | null>(null);
  
  // Reference to the subtitle list container for scrolling
  const subtitleListRef = useRef<HTMLUListElement>(null);

  // Remove complex edit history management, simplify to basic save state
  
  // Remove complex edit history functionality
  
  // Remove undo functionality
  
  
  
  // Remove local cache update functions

  // Simplified preview: direct sync to video player, no debounce, no backend calls
  const syncToVideoPlayer = useCallback((updatedSubtitle: Subtitle, language: string) => {
    if (onSubtitleSave) {
      onSubtitleSave(updatedSubtitle, language);
    }
  }, [onSubtitleSave]);

  // Remove real-time preview debounce function, only update when save is confirmed


  // Simplified initialization: directly use passed subtitle data
  useEffect(() => {
    // Only initialize if there are no unsaved changes, or if it's the very first load
    if (!jobId || !subtitles.length) return;
    if (hasChanges) { // If there are unsaved changes, don't re-initialize from props
      console.log('⚠️ Unsaved changes exist, skipping initialization of working copy to protect data.');
      return;
    }
    
    console.log('🔄 Initializing working copy:', subtitles.length, 'languages');
    setWorkingSubtitles(JSON.parse(JSON.stringify(subtitles)));
    setHasChanges(false);
  }, [jobId, subtitles, hasChanges]); 
  
  // External subtitle update handling: only update when no changes
  useEffect(() => {
    if (hasChanges) {
      console.log('⚠️ User has unsaved changes, protecting working copy.');
      return;
    }
    
    if (subtitles.length > 0) {
      console.log('🔄 Syncing external subtitle updates.');
      setWorkingSubtitles(JSON.parse(JSON.stringify(subtitles)));
    }
  }, [subtitles, hasChanges]);

  // Group subtitles by time ranges
  useEffect(() => {
    // Handle subtitle grouping and time range calculation
    const allSubtitlesWithLanguage: (Subtitle & { language: string })[] = [];
    
    workingSubtitles.forEach((langSub: any) => {
      if (langSub.subtitles && Array.isArray(langSub.subtitles) && langSub.subtitles.length > 0) {
        try {
          const subtitlesWithLanguage = langSub.subtitles.map((sub: Subtitle) => ({
            ...sub,
            id: `${langSub.language}-${sub.id}`,
            language: langSub.language
          }));
          allSubtitlesWithLanguage.push(...subtitlesWithLanguage);
        } catch (error) {
          console.error(`Error processing subtitles for ${langSub.language}:`, error);
        }
      }
    });

    allSubtitlesWithLanguage.sort((a, b) => {
      // First, sort by time
      const timeDiff = a.startTime - b.startTime;
      if (Math.abs(timeDiff) > 0.001) { // If time difference is greater than 1ms
        return timeDiff;
      }
      
      // If times are the same or very close, sort by ID
      const aId = a.id.includes('-') ? a.id.split('-')[1] : a.id;
      const bId = b.id.includes('-') ? b.id.split('-')[1] : b.id;
      
      // Simple numeric ID sorting (for the new 1,2,3... numbering system)
      const aNum = parseInt(aId) || 0;
      const bNum = parseInt(bId) || 0;
      return aNum - bNum;
    });

    const timeRanges: {start: number, end: number}[] = [];
    
    allSubtitlesWithLanguage.forEach(sub => {
      let foundOverlap = false;
      
      for (let i = 0; i < timeRanges.length; i++) {
        const range = timeRanges[i];
        
        if ((sub.startTime <= range.end && sub.endTime >= range.start)) {
          range.start = Math.min(range.start, sub.startTime);
          range.end = Math.max(range.end, sub.endTime);
          foundOverlap = true;
          break;
        }
      }
      
      if (!foundOverlap) {
        timeRanges.push({
          start: sub.startTime,
          end: sub.endTime
        });
      }
    });
    
    timeRanges.sort((a, b) => a.start - b.start);
    
    const grouped: GroupedSubtitle[] = timeRanges.map(range => ({
      startTime: range.start,
      endTime: range.end,
      subtitlesByLanguage: {}
    }));
    
    allSubtitlesWithLanguage.forEach(sub => {
      let assigned = false;
      
      for (let i = 0; i < grouped.length; i++) {
        const group = grouped[i];
        
        if (sub.startTime <= group.endTime && sub.endTime >= group.startTime) {
          // If a subtitle for this language already exists in the group, create a new group
          if (group.subtitlesByLanguage[sub.language]) {
            // Create a new, separate group for this subtitle
            grouped.splice(i + 1, 0, {
              startTime: sub.startTime,
              endTime: sub.endTime,
              subtitlesByLanguage: {
                [sub.language]: sub
              }
            });
            assigned = true;
            break;
          } else {
            group.subtitlesByLanguage[sub.language] = sub;
            assigned = true;
            break;
          }
        }
      }
      
      // If no suitable group was found, create a new one
      if (!assigned) {
        grouped.push({
          startTime: sub.startTime,
          endTime: sub.endTime,
          subtitlesByLanguage: {
            [sub.language]: sub
          }
        });
      }
    });
    
    // Re-sort groups to ensure correct time order
    grouped.sort((a, b) => a.startTime - b.startTime);
    
    // Debug info: Grouping completion statistics
    if (grouped.length > 0) {
      console.log(`✅ Subtitle grouping complete: ${grouped.length} time groups`, {
        totalSubtitles: allSubtitlesWithLanguage.length,
        languages: Array.from(new Set(allSubtitlesWithLanguage.map(s => s.language)))
      });
    }
    
    setGroupedSubtitles(grouped);
  }, [workingSubtitles]);

  // Track current subtitle and scroll
  useEffect(() => {
    if (!groupedSubtitles || groupedSubtitles.length === 0) return;
    
    const currentGroup = groupedSubtitles.find(group => 
      currentTime >= group.startTime && currentTime <= group.endTime
    );
    
    if (currentGroup) {
      const firstSubtitleKey = Object.keys(currentGroup.subtitlesByLanguage)[0];
      if (firstSubtitleKey) {
        const firstSubId = currentGroup.subtitlesByLanguage[firstSubtitleKey].id;
        setCurrentSubtitleId(firstSubId);
        
        const subtitleElement = document.getElementById(`group-${currentGroup.startTime}`);
        if (subtitleElement && subtitleListRef.current) {
          const containerHeight = subtitleListRef.current.clientHeight;
          const subtitleTop = subtitleElement.offsetTop;
          const subtitleHeight = subtitleElement.clientHeight;
          
          subtitleListRef.current.scrollTop = subtitleTop - (containerHeight / 2) + (subtitleHeight / 2);
        }
      }
    }
  }, [currentTime, groupedSubtitles]);

  // Remove real-time text change handling, only update when save is confirmed

  // Handle subtitle text editing
  const handleStartEdit = (subtitleId: string, language: string, clickPosition?: number) => {
    // If another subtitle is currently being edited, clean up any empty ones first
    if (editingSubtitle && editingSubtitle.id !== subtitleId) {
      const { id, language: currentLang } = editingSubtitle;
      if (emptySubtitles.has(id)) {
        cleanupEmptySubtitle(id, currentLang);
      }
    }
    
    // Seek to the corresponding time and pause the video when a subtitle is clicked
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const subtitle = langSub?.subtitles.find(s => s.id === originalId);
    
    if (subtitle && onSubtitleClick) {
      console.log('📍 Starting to edit subtitle, seeking to time:', subtitle.startTime, 's');
      onSubtitleClick(subtitle.startTime);
      
      // Immediately pause the video for editing
      if (onPlayPause && !isPlaying) {
        // If the video is playing, pause it
        setTimeout(() => {
          onPlayPause();
        }, 50);
      }
    }
    
    setEditingSubtitle({ id: subtitleId, language });
  };

  // Clean up empty subtitles
  const cleanupEmptySubtitle = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const subtitle = langSub?.subtitles.find(s => s.id === originalId);
    
    if (subtitle && (!subtitle.text || subtitle.text.trim() === '')) {
      // Remove empty subtitle
      setWorkingSubtitles(workingSubtitles.map((langSub: any) => {
        if (langSub.language === language) {
          return {
            ...langSub,
            subtitles: langSub.subtitles.filter((sub: Subtitle) => sub.id !== originalId)
          };
        }
        return langSub;
      }));
      
      // Remove from the set of empty subtitles
      setEmptySubtitles(prev => {
        const newSet = new Set(prev);
        newSet.delete(subtitleId);
        return newSet;
      });
    }
  };

  const handleSaveEdit = (newText: string, subtitleId: string, language: string) => {
    // For IDs like "zh-new-xxxxx", correctly extract the original ID
    const parts = subtitleId.split('-');
    const originalId = parts.length > 2 ? parts.slice(1).join('-') : parts[1];
    
    console.log('🎯 Edit Save - ID Parsing:', {
      subtitleId,
      parts,
      originalId,
      newText: newText.substring(0, 50) + (newText.length > 50 ? '...' : ''),
      language
    });
    
    // If text is empty, mark as an empty subtitle
    if (!newText || newText.trim() === '') {
      setEmptySubtitles(prev => new Set(prev).add(subtitleId));
    } else {
      // Remove empty subtitle mark
      setEmptySubtitles(prev => {
        const newSet = new Set(prev);
        newSet.delete(subtitleId);
        return newSet;
      });
    }
    
    // Get current subtitle data for the callback first
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const currentSubtitle = langSub?.subtitles.find(s => s.id === originalId);
    
    // Update local state and immediately trigger callback for real-time sync
    const updatedSubtitles = workingSubtitles.map((langSub: any) => {
      if (langSub.language === language) {
        return {
          ...langSub,
          subtitles: langSub.subtitles.map((sub: Subtitle) => 
            sub.id === originalId ? { ...sub, text: newText } : sub
          )
        };
      }
      return langSub;
    });
    
    setWorkingSubtitles(updatedSubtitles);
    
    // On edit confirmation: update frontend copy and sync to player, do not call backend
    if (currentSubtitle && onSubtitleSave) {
      console.log('✅ Frontend edit confirmed, syncing to player:', { 
        id: subtitleId, 
        text: newText.substring(0, 20),
        note: 'Frontend update only, no backend call'
      });
      
      // Sync to video player for display, but don't save to backend
      const updatedSubtitle = { ...currentSubtitle, text: newText };
      onSubtitleSave(updatedSubtitle, language);
    }

    // Mark as having changes
    setHasChanges(true);
    
    console.log('📝 Edit save complete - marked as dirty:', {
      subtitleId: originalId,
      language,
      textLength: newText.length
    });

    setEditingSubtitle(null);
  };

  const handleCancelEdit = () => {
    // If canceling edit, check if an empty subtitle needs to be cleaned up
    if (editingSubtitle) {
      const { id, language } = editingSubtitle;
      if (emptySubtitles.has(id)) {
        cleanupEmptySubtitle(id, language);
      }
    }
    setEditingSubtitle(null);
  };

  // Open time adjustment dialog
  const handleOpenTimeDialog = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const subtitle = langSub?.subtitles.find(s => s.id === originalId);
    
    if (subtitle) {
      setSelectedSubtitleForDialog({
        subtitle: { ...subtitle, id: subtitleId },
        language
      });
      setTimeDialogOpen(true);
    }
  };

  // Adapter for InlineTimeRangeSlider component
  const handleOpenTimeDialogFromSlider = (subtitle: LocalSubtitle, language: string) => {
    handleOpenTimeDialog(subtitle.id, language);
  };

  // Handle time adjustment save
  const handleTimeAdjustmentSave = (newStartTime: number, newEndTime: number) => {
    if (!selectedSubtitleForDialog) return;
    
    const { subtitle, language } = selectedSubtitleForDialog;
    const originalId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
    
    setWorkingSubtitles(workingSubtitles.map((langSub: LanguageSubtitles) => {
      if (langSub.language === language) {
        return {
          ...langSub,
          subtitles: langSub.subtitles.map(sub => 
            sub.id === originalId ? 
              { ...sub, startTime: newStartTime, endTime: newEndTime } : 
              sub
          )
        };
      }
      return langSub;
    }));

    // Mark as having changes after time adjustment
    setHasChanges(true);
    
    // Close dialog
    setTimeDialogOpen(false);
    setSelectedSubtitleForDialog(null);
  };

  // Handle inline time range slider change
  const handleInlineTimeChange = (groupStartTime: number, groupEndTime: number, newStartTime: number, newEndTime: number) => {
    const targetGroup = groupedSubtitles.find(group => 
      group.startTime === groupStartTime && group.endTime === groupEndTime
    );
    if (!targetGroup) return;

    // Real-time preview: seek to the new start time
    if (onSubtitleClick) {
      console.log('⏰ Timeline adjusted, seeking to new time:', newStartTime, 's');
      onSubtitleClick(newStartTime);
    }

    // Trigger real-time preview and update subtitles
    Object.keys(targetGroup.subtitlesByLanguage).forEach(language => {
      const subtitle = targetGroup.subtitlesByLanguage[language];
      const originalId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
      
      const updatedSubtitle = {
        ...subtitle,
        startTime: newStartTime,
        endTime: newEndTime
      };
      
      // Real-time preview callback
      if (onSubtitleSave) onSubtitleSave(updatedSubtitle, language);
      
      // Update local state
      setWorkingSubtitles((prev: any) => prev.map((langSub: any) => {
        if (langSub.language === language) {
          return {
            ...langSub,
            subtitles: langSub.subtitles.map((sub: Subtitle) => 
              sub.id === originalId ? { ...sub, startTime: newStartTime, endTime: newEndTime } : sub
            )
          };
        }
        return langSub;
      }));
      
      // Mark as having changes
      setHasChanges(true);
    });

    setHasChanges(true);
  };

  // Open split dialog
  const handleOpenSplitDialog = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const subtitle = langSub?.subtitles.find(s => s.id === originalId);
    
    if (subtitle) {
      setSelectedSubtitleForDialog({
        subtitle: { ...subtitle, id: subtitleId },
        language
      });
      setSplitDialogOpen(true);
    }
  };

  // Renumber subtitles: convert a/b markers to consecutive numbers
  const renumberSubtitles = (subtitles: LocalSubtitle[]): LocalSubtitle[] => {
    return subtitles.map((sub, index) => ({
      ...sub,
      id: (index + 1).toString()
    }));
  };

  // Handle subtitle split save - new simple approach
  const handleSplitSubtitleSave = (splitPosition: number, splitTime: number, firstText: string, secondText: string) => {
    if (!selectedSubtitleForDialog) return;
    
    const { subtitle, language } = selectedSubtitleForDialog;
    
    console.log('🟢 New split version started - simple approach 🟢', subtitle);

    // Seek to split point for real-time preview
    if (onSubtitleClick) {
      onSubtitleClick(splitTime);
    }

    // Create the second part of the subtitle
    const secondSubtitle = {
      id: 'temp-split', // Temporary ID, will be renumbered later
      text: secondText,
      startTime: splitTime,
      endTime: subtitle.endTime
    };

    // Update all subtitle data
    const updatedAllSubtitles = workingSubtitles.map((langSub: any) => {
      if (langSub.language === language) {
        const updatedSubtitles = [...langSub.subtitles];
        
        // Fix ID matching issue: get original ID for lookup
        const targetId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
        const originalIndex = updatedSubtitles.findIndex(sub => sub.id === targetId);
        
        // Debug: Ensure split operation finds target subtitle
        if (originalIndex === -1) {
          console.error('Split operation failed - subtitle not found:', { 
            originalSubtitleId: subtitle.id, 
            targetId, 
            availableIds: updatedSubtitles.map(s => s.id)
          });
          return langSub;
        }
        
        if (originalIndex !== -1) {
          console.log('Found subtitle, processing split');
          
          // Update the first part of the subtitle (keep original ID for now)
          const firstSubtitle = {
            ...updatedSubtitles[originalIndex],
            text: firstText,
            endTime: splitTime
          };
          updatedSubtitles[originalIndex] = firstSubtitle;
          
          // Insert the second part after the original subtitle
          updatedSubtitles.splice(originalIndex + 1, 0, secondSubtitle);
          
          // Sort by time to ensure correct order
          updatedSubtitles.sort((a, b) => a.startTime - b.startTime);
          
          // Renumber: generate consecutive numeric IDs
          const renumberedSubtitles = updatedSubtitles.map((sub, index) => ({
            ...sub,
            id: (index + 1).toString()
          }));
          
          console.log('✅ Split complete:', {
            originalText: firstSubtitle.text,
            newText: secondText,
            totalCount: renumberedSubtitles.length,
            secondPartId: renumberedSubtitles.find(s => s.text === secondText)?.id
          });
          
          // Trigger full subtitle list update - split is a structural change
          console.log('✂️ Triggering full subtitle list update after split:', {
            language: language,
            countBeforeSplit: langSub.subtitles.length,
            countAfterSplit: renumberedSubtitles.length,
            originalSubtitleId: targetId,
            addedSubtitle: 'temp-id -> renumbered'
          });
          
          // Pass full list update via onSubtitleSave
          if (onSubtitleSave) {
            const bulkUpdate: BulkUpdateOperation = {
              type: 'BULK_UPDATE',
              language: language,
              subtitles: renumberedSubtitles,
              action: 'split',
              details: {
                originalId: targetId,
                firstText: firstText,
                secondText: secondText,
                splitTime: splitTime
              }
            };
            onSubtitleSave(bulkUpdate as any, language);
          }
          
          // Mark as having unsaved changes
          setHasChanges(true);
          
          return {
            ...langSub,
            subtitles: renumberedSubtitles
          };
        } else {
          console.error('Subtitle to be split not found!');
        }
      }
      return langSub;
    });

    setWorkingSubtitles(updatedAllSubtitles);
    setHasChanges(true);

    // Mark as having unsaved changes
    setHasChanges(true);

    console.log('Split complete:', {
      original: subtitle.text,
      first: firstText,
      second: secondText,
      splitTime: splitTime
    });

    // Close dialog and clean up state
    setSplitDialogOpen(false);
    setSelectedSubtitleForDialog(null);
  };

  // Open merge dialog
  const handleOpenMergeDialog = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    const currentIndex = langSub?.subtitles.findIndex(s => s.id === originalId);
    
    if (langSub && currentIndex !== undefined && currentIndex >= 0 && currentIndex < langSub.subtitles.length - 1) {
      const currentSubtitle = langSub.subtitles[currentIndex];
      const nextSubtitle = langSub.subtitles[currentIndex + 1];
      
      setSelectedSubtitleForMerge({
        current: { ...currentSubtitle, id: subtitleId },
        next: { ...nextSubtitle, id: `${language}-${nextSubtitle.id}` },
        language
      });
      setMergeDialogOpen(true);
    }
  };

  // Handle subtitle merge save
  const handleMergeSubtitleSave = (mergedText: string, newEndTime: number, deleteSubtitleId: string) => {
    if (!selectedSubtitleForMerge) return;
    
    const { current, next, language } = selectedSubtitleForMerge;
    const currentOriginalId = current.id.includes('-') ? current.id.split('-')[1] : current.id;
    const nextOriginalId = next.id.includes('-') ? next.id.split('-')[1] : next.id;

    // Merge timeline: use start time of the first and end time of the second
    const mergedStartTime = current.startTime;
    const mergedEndTime = next.endTime;

    console.log('🔗 Merging subtitles:', { 
      from: `"${current.text}" + "${next.text}"`,
      to: `"${mergedText}"`,
      timeRange: `${mergedStartTime.toFixed(2)}-${mergedEndTime.toFixed(2)}`
    });

    // Seek to the start of the merged subtitle for real-time preview
    if (onSubtitleClick) {
      onSubtitleClick(mergedStartTime);
    }

    // Create the merged subtitle object
    const mergedSubtitle = {
      id: currentOriginalId,
      text: mergedText,
      startTime: mergedStartTime,
      endTime: mergedEndTime
    };

    // Immediately trigger real-time preview
    if (onSubtitleSave) {
      console.log('🔗 Triggering merge real-time preview');
      onSubtitleSave(mergedSubtitle, language);
    }

    const updatedAllSubtitles = workingSubtitles.map((langSub: LanguageSubtitles) => {
      if (langSub.language === language) {
        const updatedSubtitles = langSub.subtitles
          .map(sub => {
            // Update the current subtitle with the merged text and time
            if (sub.id === currentOriginalId) {
              return mergedSubtitle;
            }
            return sub;
          })
          // Delete the next subtitle
          .filter((sub: Subtitle) => sub.id !== nextOriginalId);
        
        return {
          ...langSub,
          subtitles: updatedSubtitles
        };
      }
      return langSub;
    });

    setWorkingSubtitles(updatedAllSubtitles);

    // Mark as dirty
    setHasChanges(true);

    // Trigger full subtitle list update - merge is a structural change, requires full refresh
    // Find the updated subtitle list for the current language
    const currentLangSubs = updatedAllSubtitles.find((ls: LanguageSubtitles) => ls.language === language)?.subtitles || [];
    
    // Directly update the parent component's allSubtitles state, which will auto-trigger video player refresh
    console.log('🔗 Triggering full subtitle list update after merge:', {
      language: language,
      countBeforeMerge: workingSubtitles.find((ls: LanguageSubtitles) => ls.language === language)?.subtitles.length,
      countAfterMerge: currentLangSubs.length,
      deletedSubtitleId: nextOriginalId,
      mergedIntoSubtitleId: currentOriginalId
    });
    
    // Pass a special marker to indicate this is a full list update
    if (onSubtitleSave) {
      const bulkUpdate: BulkUpdateOperation = {
        type: 'BULK_UPDATE',
        language: language,
        subtitles: currentLangSubs,
        action: 'merge',
        details: {
          mergedId: currentOriginalId,
          deletedId: nextOriginalId,
          mergedText: mergedText
        }
      };
      onSubtitleSave(bulkUpdate as any, language);
    }

    // Mark as having unsaved changes
    setHasChanges(true);

    console.log('✅ Merge complete:', {
      currentText: current.text,
      nextText: next.text,
      mergedText: mergedText,
      currentTimeRange: `${current.startTime} - ${current.endTime}`,
      nextTimeRange: `${next.startTime} - ${next.endTime}`,
      mergedTimeRange: `${mergedStartTime} - ${mergedEndTime}`,
      totalSubtitles: updatedAllSubtitles.find((ls: LanguageSubtitles) => ls.language === language)?.subtitles.length
    });

    // Close dialog
    setMergeDialogOpen(false);
    setSelectedSubtitleForMerge(null);
  };

  // Open timeline offset dialog
  const handleOpenOffsetDialog = (language: string) => {
    setSelectedLanguageForOffset(language);
    setOffsetDialogOpen(true);
  };

  // Handle timeline offset application
  const handleApplyTimelineOffset = (offsetSeconds: number, language: string) => {
    setWorkingSubtitles(workingSubtitles.map((langSub: LanguageSubtitles) => {
      if (langSub.language === language) {
        const updatedSubtitles = langSub.subtitles.map(sub => ({
          ...sub,
          startTime: Math.max(0, sub.startTime + offsetSeconds),
          endTime: Math.max(0, sub.endTime + offsetSeconds)
        }));
        
        return {
          ...langSub,
          subtitles: updatedSubtitles
        };
      }
      return langSub;
    }));
    setHasChanges(true); // Mark as dirty
  };

  // Discard all unsaved changes
  const handleDiscardChanges = () => {
    if (!hasChanges) return;
    // Restore from initial state - requires reload
    window.location.reload();
    setHasChanges(false);
    showSuccess('已放弃未保存的修改');
  };

  // Restore to the originally generated version
  const handleSwitchToSource = async () => {
    if (!jobId || !languages?.length) return;
    
    setIsLoadingVersion(true);
    try {
      console.log('🔄 Starting to restore to the originally generated version...');
      
      // Reload the original version
      const newAllSubtitles = [];
      
      for (const language of languages) {
        try {
          // Get version history, find the original version (smallest version number)
          const versionHistory = await subtitleVersionService.getVersionHistory(Number(jobId), language, true);
          console.log(`Version history for ${language}:`, versionHistory);
          
          if (versionHistory.length > 0) {
            // Find the version with the smallest version number (the original)
            const originalVersion = versionHistory.reduce((oldest, current) => 
              current.version_number < oldest.version_number ? current : oldest
            );
            
            console.log(`Restoring to original version for ${language}:`, originalVersion);
            
            // Restore to the original version
            const restoreResponse = await subtitleVersionService.restoreVersion(
              Number(jobId), 
              language, 
              originalVersion.id
            );
            
            console.log(`✅ Restore response for ${language}:`, restoreResponse);
            console.log(`📋 Number of restored subtitles for ${language}:`, restoreResponse.subtitles?.length || 0);
            
            const subtitles: LocalSubtitle[] = restoreResponse.subtitles.map((sub: any) => ({
              ...sub,
              id: `${language}-${sub.id}`
            }));
            
            console.log(`🔄 Processed subtitles for ${language}:`, subtitles.length, subtitles.slice(0, 2));
            
            newAllSubtitles.push({
              language,
              subtitles,
              loading: false,
              error: null
            });
          } else {
            console.warn(`No version history found for ${language}, using current version.`);
            // If no version history, fall back to getting the current version
            const response = await previewService.getSubtitles(Number(jobId), language);
            const subtitles: LocalSubtitle[] = response.map((sub: any) => ({
              ...sub,
              id: `${language}-${sub.id}`
            }));
            
            newAllSubtitles.push({
              language,
              subtitles,
              loading: false,
              error: null
            });
          }
        } catch (error) {
          console.error(`Failed to restore original version for ${language}:`, error);
          newAllSubtitles.push({
            language,
            subtitles: [],
            loading: false,
            error: `Failed to restore ${language} original version`
          });
        }
      }
      
      console.log('🎯 Final subtitle state to be set:', newAllSubtitles);
      console.log('📊 Subtitle count per language:', newAllSubtitles.map(ls => ({
        language: ls.language,
        count: ls.subtitles.length,
        hasError: !!ls.error
      })));
      
      setWorkingSubtitles(newAllSubtitles);
      // Original state was set on initialization
      setHasChanges(false); // Reset changes flag
      showSuccess('已恢复到最初生成的版本');
    } catch (error: any) {
      showError(error.message || 'Failed to restore original version');
    } finally {
      setIsLoadingVersion(false);
    }
  };

  const handleSaveChanges = async () => {
    if (!hasChanges) return;
    setIsLoadingVersion(true);
    try {
      const langSub = workingSubtitles.find((ls: LanguageSubtitles) => ls.subtitles.length > 0);
      if (!langSub) {
        showError('Nothing to save');
        setIsLoadingVersion(false);
        return;
      }

      const editsToSend: SubtitleEdit[] = [];

      // Get original language subtitles for comparison
      const originalSubtitlesByLang = workingSubtitles.reduce((acc: any, langSub: LanguageSubtitles) => {
        acc[langSub.language] = langSub.subtitles;
        return acc;
      }, {});
      const originalLangSub = originalSubtitlesByLang[langSub.language];
      const originalSubtitlesMap = new Map(originalLangSub?.map((s: Subtitle) => [s.id, s]) || []);

      // Temporary solution: delete all existing subtitles and then recreate them
      console.log('🔄 Using temporary save solution: delete + recreate');
      console.log('Current subtitle count:', langSub.subtitles.length);
      console.log('Original subtitle count:', originalLangSub?.length || 0);

      // Step 1: Delete all existing subtitles
      if (originalLangSub) {
        originalLangSub.forEach((originalSub: Subtitle) => {
          editsToSend.push({
            job_id: Number(jobId),
            language: langSub.language,
            subtitle_id: originalSub.id,
            edit_type: 'DELETE' as const,
          });
        });
      }

      // Step 2: Recreate all subtitles
      langSub.subtitles.forEach((sub: Subtitle, index: number) => {
        editsToSend.push({
          job_id: Number(jobId),
          language: langSub.language,
          subtitle_id: `new-${index}-${Date.now()}`, // Unique temporary ID
          new_text: sub.text,
          new_start_time: sub.startTime,
          new_end_time: sub.endTime,
          edit_type: 'CREATE' as const,
          metadata: {
            final_order: index + 1
          },
        });
      });

      console.log(`📤 Preparing to send ${editsToSend.length} operations (delete ${originalLangSub?.length || 0}, create ${langSub.subtitles.length})`);

      if (editsToSend.length === 0) {
        showSuccess('没有检测到需要保存的修改');
        setHasChanges(false);
        setIsLoadingVersion(false);
        return;
      }

      const response = await subtitleEditService.saveBatchSubtitleEdits({
        job_id: Number(jobId),
        language: langSub.language,
        edits: editsToSend
      });

      if (response.success && response.updatedSubtitle) {
        // Backend returns Subtitle | Subtitle[], needs to be handled uniformly
        const updatedSubtitlesFromServer = Array.isArray(response.updatedSubtitle)
          ? response.updatedSubtitle
          : [response.updatedSubtitle];

        // Renumber subtitles and add language prefix
        const renumberedSubtitles = renumberSubtitles(updatedSubtitlesFromServer);
        const newSubtitlesWithLangPrefix = renumberedSubtitles.map((sub: Subtitle) => ({
          ...sub,
          id: `${langSub.language}-${sub.id}` // Re-add language prefix
        }));

        // Update the subtitle list for the current language
        const newLangSub = { ...langSub, subtitles: newSubtitlesWithLangPrefix };
        const newAllSubtitles = workingSubtitles.map((ls: LanguageSubtitles) => ls.language === langSub.language ? newLangSub : ls);

        // Update frontend state with authoritative data from the backend
        const deepCopy = JSON.parse(JSON.stringify(newAllSubtitles));
        setWorkingSubtitles(deepCopy);
        // Simplified original state management
        setHasChanges(false);
        
        // Clear temporary cache
        try {
          await fetch(`/api/v1/subtitles/auto-save/${jobId}?language=${langSub.language}`, {
            method: 'DELETE',
          });
        } catch (error) {
          console.warn('Failed to clear temp cache:', error);
        }
        
        showSuccess('修改已保存');
      } else {
        showError(response.message || '保存失败');
      }
    } catch (error: any) {
      console.error('Failed to save subtitles:', error);
      showError(error.message || '保存失败');
    } finally {
      setIsLoadingVersion(false);
    }
  };

  // Delete specified subtitle
  const handleDeleteSubtitle = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    
    setWorkingSubtitles(workingSubtitles.map((langSub: LanguageSubtitles) => {
      if (langSub.language === language) {
        const filteredSubtitles = langSub.subtitles.filter(sub => sub.id !== originalId);
        
        // Renumber
        const renumberedSubtitles = filteredSubtitles
          .sort((a, b) => a.startTime - b.startTime)
          .map((sub: Subtitle, index: number) => ({
            ...sub,
            id: (index + 1).toString()
          }));
        
        return {
          ...langSub,
          subtitles: renumberedSubtitles
        };
      }
      return langSub;
    }));
    
    setHasChanges(true);
  };

  // Add new subtitle after the specified one
  const handleAddSubtitleAfter = (subtitleId: string, language: string) => {
    const originalId = subtitleId.includes('-') ? subtitleId.split('-')[1] : subtitleId;
    const langSub = workingSubtitles.find((ls: any) => ls.language === language);
    
    if (!langSub) return;
    
    const currentIndex = langSub.subtitles.findIndex(s => s.id === originalId);
    if (currentIndex === -1) return;
    
    const currentSubtitle = langSub.subtitles[currentIndex];
    const nextSubtitle = langSub.subtitles[currentIndex + 1];
    
    // Calculate time range for the new subtitle
    const newStartTime = currentSubtitle.endTime + 0.1;
    let newEndTime = nextSubtitle 
      ? Math.min(currentSubtitle.endTime + 3, nextSubtitle.startTime - 0.1)
      : currentSubtitle.endTime + 3;
    
    // Ensure it doesn't exceed video duration
    if (videoDuration && newEndTime > videoDuration) {
      newEndTime = Math.max(videoDuration - 0.1, newStartTime + 1);
    }
    
    // Ensure minimum duration
    if (newEndTime <= newStartTime) {
      newEndTime = newStartTime + 1;
    }
    
    const newSubtitle: LocalSubtitle = {
      id: `new-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      text: '', // Use empty string to avoid placeholder text
      startTime: newStartTime,
      endTime: newEndTime
    };
    
    setWorkingSubtitles(workingSubtitles.map((langSub: LanguageSubtitles) => {
      if (langSub.language === language) {
        const updatedSubtitles = [...langSub.subtitles];
        updatedSubtitles.splice(currentIndex + 1, 0, newSubtitle);
        return {
          ...langSub,
          subtitles: updatedSubtitles
        };
      }
      return langSub;
    }));
    
    const fullSubtitleId = `${language}-${newSubtitle.id}`;
    
    // Mark as empty and start editing (don't save immediately)
    setEmptySubtitles(prev => new Set(prev).add(fullSubtitleId));
    setEditingSubtitle({ id: fullSubtitleId, language });
    setHasChanges(true); // Mark as dirty
  };

  

  // Handle container click to clean up empty subtitles
  const handleContainerClick = (event: React.MouseEvent) => {
    // If the container itself is clicked (not a child element), clean up empty subtitles
    if (event.target === event.currentTarget && editingSubtitle) {
      const { id, language } = editingSubtitle;
      if (emptySubtitles.has(id)) {
        cleanupEmptySubtitle(id, language);
      }
      setEditingSubtitle(null);
    }
  };

  return (
    <Box 
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden'
      }}
      onClick={handleContainerClick}
    >
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        mb: 2,
        pb: 1,
        borderBottom: '1px solid',
        borderColor: 'divider'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6" sx={{ color: '#333', fontWeight: 600 }}>
            字幕编辑器
          </Typography>
          {hasChanges && (
            <Box sx={{
              px: 1.5,
              py: 0.5,
              bgcolor: '#fff3e0',
              border: '1px solid #ff9800',
              borderRadius: '12px',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: '#f57c00',
              display: 'flex',
              alignItems: 'center',
              gap: 0.5
            }}>
              ⏳ Unsaved Changes
            </Box>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          
          
          
          
          {/* New Save Button */}
          <Tooltip title="保存修改">
            <Button
              startIcon={<SaveIcon />}
              onClick={onManualSave}
              size="small"
              variant="contained"
              color="primary"
              disabled={!hasChanges || isLoadingVersion || isSaving}
              sx={{ 
                borderRadius: '8px',
                backgroundColor: hasChanges ? '#ff9800' : undefined,
                '&:hover': {
                  backgroundColor: hasChanges ? '#f57c00' : undefined,
                }
              }}
            >
              {isLoadingVersion ? '保存中...' : '保存修改'}
            </Button>
          </Tooltip>

          {/* Existing buttons */}
          <Tooltip title="放弃所有未保存的修改">
            <Button
              startIcon={<RestoreIcon />}
              onClick={handleDiscardChanges}
              size="small"
              variant="outlined"
              color="warning"
              disabled={!hasChanges || isLoadingVersion}
              sx={{ borderRadius: '8px' }}
            >
              Discard Changes
            </Button>
          </Tooltip>
          
          
          <Tooltip title="下载字幕文件">
            <Button
              startIcon={<FileDownloadIcon />}
              onClick={() => setExportDialogOpen(true)}
              size="small"
              variant="outlined"
              color="success"
              sx={{ borderRadius: '8px' }}
            >
              下载文件
            </Button>
          </Tooltip>
          
        </Box>
      </Box>

      {workingSubtitles.map((langSub: LanguageSubtitles) => (
        <React.Fragment key={`lang-${langSub.language}`}>
          {langSub.loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {langSub.error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {langSub.error}
            </Alert>
          )}
        </React.Fragment>
      ))}

      <List 
        component="ul" 
        ref={subtitleListRef} 
        sx={{ overflow: 'auto', flexGrow: 1 }}
        onClick={handleContainerClick}
      >
        {groupedSubtitles.map((group, index) => {
          const languagesInGroup = Object.keys(group.subtitlesByLanguage);
          const isCurrentGroup = Object.values(group.subtitlesByLanguage).some(
            sub => currentSubtitleId === sub.id
          );
          
          return (
            <ListItem
              key={`time-group-${group.startTime}`}
              id={`group-${group.startTime}`}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                bgcolor: isCurrentGroup ? 'action.selected' : 'inherit',
                borderLeft: isCurrentGroup ? '3px solid' : 'none',
                borderLeftColor: 'primary.main',
                borderRadius: 2,
                mb: 1.5,
                p: 2,
                boxShadow: isCurrentGroup ? '0 2px 8px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.3s ease'
              }}
            >
              {/* Inline Time Range Slider */}
              <Box sx={{ 
                width: '100%',
                mb: 1.5 
              }}>
                <InlineTimeRangeSlider
                  startTime={group.startTime}
                  endTime={group.endTime}
                  onTimeChange={(newStartTime, newEndTime) => 
                    handleInlineTimeChange(group.startTime, group.endTime, newStartTime, newEndTime)
                  }
                  onSeekTo={onSubtitleClick}
                  languagesInGroup={languagesInGroup}
                  subtitlesByLanguage={group.subtitlesByLanguage}
                  onOpenTimeDialog={handleOpenTimeDialogFromSlider}
                />
              </Box>
              
              <Divider sx={{ width: '100%', mb: 1.5 }} />
              
              {/* Subtitles for each language */}
              {languagesInGroup.map(lang => {
                const subtitle = group.subtitlesByLanguage[lang];
                const isEditing = editingSubtitle?.id === subtitle.id && editingSubtitle?.language === lang;
                
                const langColor = lang === 'en' ? 'primary' : 
                                  lang === 'zh' ? 'error' : 
                                  lang === 'auto' ? 'info' : 'success';
                                  
                const langDisplay = lang === 'auto' ? 'Auto' :
                                    lang === 'zh' ? 'Chinese' :
                                    lang === 'en' ? 'English' : lang;
                
                return (
                  <Box
                    key={subtitle.id}
                    sx={{
                      width: '100%',
                      mb: 1.5,
                      p: 1.5,
                      borderLeft: `4px solid`,
                      borderLeftColor: `${langColor}.main`,
                      bgcolor: 'background.paper',
                      borderRadius: 2,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                      }
                    }}
                  >
                    <Box sx={{
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      mb: 1
                    }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          label={langDisplay}
                          size="small"
                          color={langColor}
                          variant="filled"
                        />
                        <Tooltip title={`调整 ${langDisplay} 时间偏移`}>
                          <IconButton 
                            size="small"
                            onClick={() => handleOpenOffsetDialog(lang)}
                            sx={{ borderRadius: '6px' }}
                          >
                            <ScheduleIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title="拆分字幕">
                          <IconButton 
                            size="small"
                            onClick={() => handleOpenSplitDialog(subtitle.id, lang)}
                            sx={{ borderRadius: '6px' }}
                          >
                            <SplitScreenIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="合并下一条字幕">
                          <IconButton 
                            size="small"
                            onClick={() => handleOpenMergeDialog(subtitle.id, lang)}
                            sx={{ borderRadius: '6px' }}
                            disabled={(() => {
                              const originalId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
                              const langSub = workingSubtitles.find(ls => ls.language === lang);
                              const currentIndex = langSub?.subtitles.findIndex(s => s.id === originalId);
                              return !langSub || currentIndex === undefined || currentIndex >= langSub.subtitles.length - 1;
                            })()}
                          >
                            <MergeIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="在下方添加字幕">
                          <IconButton 
                            size="small"
                            onClick={() => handleAddSubtitleAfter(subtitle.id, lang)}
                            sx={{ borderRadius: '6px' }}
                          >
                            <AddIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="删除此字幕">
                          <span>
                            <IconButton 
                              size="small"
                              onClick={() => handleDeleteSubtitle(subtitle.id, lang)}
                              sx={{ borderRadius: '6px', color: 'error.main' }}
                              disabled={(() => {
                                const langSub = workingSubtitles.find(ls => ls.language === lang);
                                return !langSub || langSub.subtitles.length <= 1;
                              })()}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </Box>
                    </Box>
                    
                    <EditableText
                      text={subtitle.text}
                      isEditing={isEditing}
                      onEdit={(newText) => handleSaveEdit(newText, subtitle.id, lang)}
                      onStartEdit={(clickPosition) => handleStartEdit(subtitle.id, lang, clickPosition)}
                      onSave={() => {}}
                      onCancel={handleCancelEdit}
                      language={lang}
                      subtitleId={subtitle.id}
                      emptySubtitles={emptySubtitles}
                    />
                  </Box>
                );
              })}
            </ListItem>
          );
        })}
        
        {groupedSubtitles.length === 0 && !workingSubtitles.some(ls => ls.loading) && (
          <ListItem>
            <Typography color="text.secondary">
              No subtitles found. Please select languages or add new subtitles.
            </Typography>
          </ListItem>
        )}
      </List>

      {/* Time adjustment dialog */}
      <TimeAdjustmentDialog
        open={timeDialogOpen}
        subtitle={selectedSubtitleForDialog?.subtitle || null}
        currentVideoTime={currentTime}
        videoDuration={videoDuration}
        onClose={() => {
          setTimeDialogOpen(false);
          setSelectedSubtitleForDialog(null);
        }}
        onSave={handleTimeAdjustmentSave}
        onSeekTo={onSubtitleClick}
        onPlaySpeedChange={onPlaySpeedChange}
        onPlayPause={onPlayPause}
        isPlaying={isPlaying}
      />

      {/* Split subtitle dialog */}
      <SplitSubtitleDialog
        open={splitDialogOpen}
        subtitle={selectedSubtitleForDialog?.subtitle || null}
        onClose={() => {
          setSplitDialogOpen(false);
          setSelectedSubtitleForDialog(null);
        }}
        onSplit={handleSplitSubtitleSave}
        onSeekTo={onSubtitleClick}
      />

      {/* Merge subtitle dialog */}
      <MergeSubtitleDialogSimple
        open={mergeDialogOpen}
        currentSubtitle={selectedSubtitleForMerge?.current || null}
        nextSubtitle={selectedSubtitleForMerge?.next || null}
        onClose={() => {
          setMergeDialogOpen(false);
          setSelectedSubtitleForMerge(null);
        }}
        onMerge={handleMergeSubtitleSave}
        onSeekTo={onSubtitleClick}
      />

      {/* Timeline offset dialog */}
      <TimelineOffsetDialogSimple
        open={offsetDialogOpen}
        subtitles={workingSubtitles.find((langSub: LanguageSubtitles) => langSub.language === selectedLanguageForOffset)?.subtitles || []}
        language={selectedLanguageForOffset}
        onClose={() => {
          setOffsetDialogOpen(false);
          setSelectedLanguageForOffset('');
        }}
        onApplyOffset={handleApplyTimelineOffset}
        onSeekTo={onSubtitleClick}
      />
      
      {/* Export dialog */}
      <SubtitleExportDialog
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
        jobId={Number(jobId)}
        language={languages[0] || 'zh'}
        jobTitle={`Job ${jobId}`}
      />
    </Box>
  );
};

export default EnhancedSubtitleEditor;
