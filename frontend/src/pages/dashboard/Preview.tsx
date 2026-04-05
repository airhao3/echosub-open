import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Alert,
  IconButton,
  Paper,
  Container,
  Button,
  Grid,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  FormControlLabel,
  Checkbox,
  Chip,
  Stack,
  Tooltip,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import VideoJSAdvancedPlayer from '../../components/preview/VideoJSAdvancedPlayer';
import SubtitleInlineEditor from '../../components/preview/SubtitleInlineEditor';
import EnhancedSubtitleEditor from '../../components/subtitle/EnhancedSubtitleEditor';
import { previewService } from '../../services/api/previewService';
import { getUserJobs, getUserJob } from '../../services/api/jobService';
import subtitleEditService from '../../services/api/subtitleEditService';
import { subtitleVersionService } from '../../services/api/subtitleVersionService';
import { useNotificationContext } from '../../components/common/NotificationProvider';

const Preview: React.FC = () => {
  const { jobId } = useParams<{ jobId?: string }>();
  const navigate = useNavigate();
  const { showSuccess, showError, showWarning } = useNotificationContext();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<any | null>(null);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([]);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>(['en']);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [videoDuration, setVideoDuration] = useState<number>(0);
  // Unified subtitle state management
  const [allSubtitles, setAllSubtitles] = useState<any[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [currentSubtitleLanguage, setCurrentSubtitleLanguage] = useState<string>('');
  const [isLoadingSubtitles, setIsLoadingSubtitles] = useState<boolean>(false);
  
  // Calculate currently displayed subtitles (real-time calculation, not stored)
  const currentLanguageSubtitles = React.useMemo(() => {
    const langSub = allSubtitles.find(ls => ls.language === currentSubtitleLanguage);
    const subtitles = langSub?.subtitles || [];
    
    console.log('[Preview] Processing subtitles for language:', currentSubtitleLanguage);
    console.log('[Preview] Raw subtitles data:', subtitles.slice(0, 3)); // Log first 3 items
    
    const processedSubtitles = subtitles.map((sub: any) => ({
      id: sub.id, // Keep ID as string (as expected by VideoJS player)
      startTime: sub.startTime || sub.start_time || 0, // Handle both formats, fallback to 0
      endTime: sub.endTime || sub.end_time || 0, // Handle both formats, fallback to 0
      text: sub.text
    })).sort((a: any, b: any) => (a.startTime || 0) - (b.startTime || 0)); // Ensure subtitles are sorted by start time
    
    console.log('[Preview] Processed subtitles for player:', processedSubtitles.slice(0, 3)); // Log first 3 processed items
    console.log('[Preview] First subtitle timing:', processedSubtitles[0] ? {
      startTime: processedSubtitles[0].startTime,
      endTime: processedSubtitles[0].endTime,
      text: processedSubtitles[0].text.substring(0, 50)
    } : 'No subtitles');
    
    return processedSubtitles;
  }, [allSubtitles, currentSubtitleLanguage]);

  // Build multi-language subtitles object for the video player
  const multiLanguageSubtitles = React.useMemo(() => {
    const multiSubs: { [languageCode: string]: any[] } = {};
    
    selectedLanguages.forEach(langCode => {
      const langSub = allSubtitles.find(ls => ls.language === langCode);
      if (langSub?.subtitles) {
        multiSubs[langCode] = langSub.subtitles.map((sub: any) => ({
          id: sub.id,
          startTime: sub.startTime || sub.start_time || 0,
          endTime: sub.endTime || sub.end_time || 0,
          text: sub.text
        })).sort((a: any, b: any) => (a.startTime || 0) - (b.startTime || 0));
      }
    });
    
    return multiSubs;
  }, [allSubtitles, selectedLanguages]);

  const [showInlineEditor, setShowInlineEditor] = useState(false);
  const [selectedSubtitle, setSelectedSubtitle] = useState<any>(null);
  const [editingSubtitle, setEditingSubtitle] = useState<any>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const advancedPlayerRef = useRef<any>(null);

  const handleGoBack = () => {
    navigate(-1); // Navigate to the previous page
  };

  // Load subtitle data for all languages (simplified version)
  const loadAllSubtitles = useCallback(async (userJobNumber: number, globalJobId: number, languages: string[]) => {
    // Prevent duplicate loading
    if (isLoadingSubtitles) {
      console.log('⏳ Subtitles already loading, skipping duplicate request');
      return;
    }
    
    setIsLoadingSubtitles(true);
    try {
      console.log('Loading subtitles for user job:', userJobNumber, 'languages:', languages);
      const subtitlePromises = languages.map(async (language) => {
        try {
          // Directly call previewService.getSubtitles, backend will automatically handle priority:
          // 1. Prioritize loading modified.json (if it exists)
          // 2. Fallback to the original subtitle file
          const subtitleData = await previewService.getSubtitles(globalJobId, language);
          console.log(`✅ Successfully loaded ${language} subtitles, count: ${subtitleData.length}`);
          
          return { language, subtitles: subtitleData, loading: false, error: null };
        } catch (error) {
          console.error(`Error loading subtitles for ${language}:`, error);
          return { language, subtitles: [], loading: false, error: `加载 ${language} 字幕失败` };
        }
      });
      
      const results = await Promise.all(subtitlePromises);
      
      setAllSubtitles(results);
      setHasUnsavedChanges(false);
      
      // Set the currently displayed language (prioritize the first language)
      const primaryLanguage = languages[0] || 'en';
      setCurrentSubtitleLanguage(primaryLanguage);
      
      console.log('✅ Subtitles loaded successfully:', {
        totalLanguages: results.length,
        primaryLanguage,
        subtitleCounts: results.map(r => ({ lang: r.language, count: r.subtitles?.length || 0 }))
      });
      
    } catch (error) {
      console.error('Error loading subtitles:', error);
      setAllSubtitles([]);
    } finally {
      setIsLoadingSubtitles(false);
    }
  }, [setAllSubtitles, setCurrentSubtitleLanguage, setHasUnsavedChanges, setIsLoadingSubtitles]); // Dependencies for useCallback

  // Fetch the most recent job if no jobId is provided
  useEffect(() => {
    const fetchJob = async () => {
      try {
        setLoading(true);
        setError(null);
        
        let jobData: any;
        
        if (jobId && !isNaN(Number(jobId))) {
          // If jobId is provided, fetch that specific job by user job number
          jobData = await getUserJob(Number(jobId));
        } else {
          // Otherwise, fetch all user jobs and get the most recent one
          const jobs = await getUserJobs();
          
          if (!jobs || jobs.length === 0) {
            setError('未找到任务，请先创建一个任务');
            setLoading(false);
            return;
          }
          
          // Sort jobs by creation date (newest first)
          const sortedJobs = [...jobs].sort((a, b) => 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
          
          // Get the most recent job
          jobData = sortedJobs[0];
          
          // Update URL with the user job number without reloading the page
          window.history.replaceState(
            null, 
            '', 
            `/dashboard/preview/${jobData.user_job_number}`
          );
        }
        
        if (!jobData) {
          setError('Job not found.');
          setLoading(false);
          return;
        }
        
        setSelectedJob(jobData);
        
        // Get actual available languages from preview options API first
        let defaultLanguage = jobData.target_languages?.split(',')[0]?.trim() || 'en'; // Use first target language as fallback
        try {
          // Try user-specific preview options first, fall back to global ID if needed
          let previewOptions;
          try {
            previewOptions = await previewService.getUserPreviewOptions(jobData.user_job_number);
          } catch (userError) {
            console.warn('User preview options failed, falling back to global ID:', userError);
            previewOptions = await previewService.getPreviewOptions(jobData.id);
          }
          const subtitleOptions = previewOptions.available_previews.filter(
            (option) => option.type === 'subtitles'
          );
          
          if (subtitleOptions.length > 0) {
            // Extract actual languages from subtitle files
            const actualLanguages = subtitleOptions
              .map(option => option.language)
              .filter((lang): lang is string => typeof lang === 'string' && lang !== 'auto'); // Remove auto and undefined values
            
            // Remove duplicates and set available languages, replace any source language indicators with 'src'
            const uniqueLanguages = Array.from(new Set(actualLanguages.map(lang => lang === jobData.source_language ? 'src' : lang)));
            
            // Always include the source language as an option
            if (jobData.source_language && !uniqueLanguages.includes('src')) {
              uniqueLanguages.unshift('src'); // Add source language at the beginning
            }
            
            setAvailableLanguages(uniqueLanguages);
            
            // Set default language to the first target language (not source language)
            const targetLanguages = uniqueLanguages.filter(lang => lang !== 'src');
            defaultLanguage = targetLanguages[0] || jobData.target_languages?.split(',')[0]?.trim() || 'en';
            setSelectedLanguages([defaultLanguage]);
          } else {
            // Fallback to job metadata if no subtitle files found
            if (jobData.subtitle_languages && jobData.subtitle_languages.length > 0) {
              const filteredLangs = jobData.subtitle_languages.filter((lang: string) => lang !== 'auto');
              // Always include source language
              const languagesWithSource = jobData.source_language ? ['src', ...filteredLangs] : filteredLangs;
              setAvailableLanguages(Array.from(new Set(languagesWithSource)));
              // Default to first target language, not source language
              defaultLanguage = filteredLangs[0] || jobData.target_languages?.split(',')[0]?.trim() || 'en';
              setSelectedLanguages([defaultLanguage]);
            } else if (typeof jobData.target_languages === 'string') {
              const languages = jobData.target_languages.split(',').map((lang: string) => lang.trim());
              const allLangs = [jobData.source_language, ...languages]
                .filter((lang, index, self) => lang && lang.trim() !== '' && self.indexOf(lang) === index);
              const filteredLangs = allLangs.filter(lang => lang !== 'auto');
              // Replace source language with 'src' and ensure it's included
              const languagesWithSrc = filteredLangs.map(lang => lang === jobData.source_language ? 'src' : lang);
              setAvailableLanguages(Array.from(new Set(languagesWithSrc)));
              // Default to first target language, not source language
              const targetLangs = languagesWithSrc.filter(lang => lang !== 'src');
              defaultLanguage = targetLangs[0] || jobData.target_languages?.split(',')[0]?.trim() || 'en';
              setSelectedLanguages([defaultLanguage]);
            } else {
              // Final fallback - always include source language if available
              const fallbackLangs = jobData.source_language ? ['src', 'zh', 'en'] : ['zh', 'en'];
              setAvailableLanguages(fallbackLangs);
              // Default to first target language, not source language
              const targetFallback = fallbackLangs.filter(lang => lang !== 'src');
              defaultLanguage = jobData.target_languages?.split(',')[0]?.trim() || targetFallback[0] || 'en';
              setSelectedLanguages([defaultLanguage]);
            }
          }
        } catch (previewError) {
          console.warn('Failed to get preview options, using job metadata:', previewError);
          // Fallback to original logic if preview API fails
          if (jobData.subtitle_languages && jobData.subtitle_languages.length > 0) {
            const filteredLangs = jobData.subtitle_languages.filter((lang: string) => lang !== 'auto');
            // Always include source language
            const languagesWithSource = jobData.source_language ? ['src', ...filteredLangs] : filteredLangs;
            setAvailableLanguages(Array.from(new Set(languagesWithSource)));
            setSelectedLanguages([filteredLangs[0] || jobData.target_languages?.split(',')[0]?.trim() || 'en']);
          } else if (typeof jobData.target_languages === 'string') {
            const languages = jobData.target_languages.split(',').map((lang: string) => lang.trim());
            const allLangs = [jobData.source_language, ...languages]
              .filter((lang, index, self) => lang && lang.trim() !== '' && self.indexOf(lang) === index);
            const filteredLangs = allLangs.filter(lang => lang !== 'auto');
            // Replace source language with 'src' and ensure it's included
            const languagesWithSrc = filteredLangs.map(lang => lang === jobData.source_language ? 'src' : lang);
            setAvailableLanguages(Array.from(new Set(languagesWithSrc)));
            setSelectedLanguages([filteredLangs[0] || jobData.target_languages?.split(',')[0]?.trim() || 'en']);
          } else {
            // Final fallback - always include source language if available
            const fallbackLangs = jobData.source_language ? ['src', 'zh', 'en'] : ['zh', 'en'];
            setAvailableLanguages(fallbackLangs);
            setSelectedLanguages([jobData.target_languages?.split(',')[0]?.trim() || 'en']);
          }
        }
        
      } catch (err) {
        console.error('Error fetching job:', err);
        setError('Failed to load job data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchJob();
  }, [jobId]);

  // Load subtitles when job or languages change
  useEffect(() => {
    if (selectedJob && selectedLanguages.length > 0 && !isLoadingSubtitles) {
      console.log('Loading subtitles for job:', selectedJob.user_job_number, 'languages:', selectedLanguages);
      loadAllSubtitles(selectedJob.user_job_number, selectedJob.id, selectedLanguages);
    }
  }, [selectedJob?.id, selectedLanguages.join(','), loadAllSubtitles]); // Use stable references

  // Handle subtitle language switch
  const handleSubtitleLanguageChange = (language: string) => {
    setCurrentSubtitleLanguage(language);
    const newSubtitles = allSubtitles.find(s => s.language === language)?.subtitles || [];
    console.log(`Switched to ${language} subtitles:`, newSubtitles.length);
    
    // If using VideoJS player, notify it to update subtitles
    if (advancedPlayerRef.current) {
      // Directly pass subtitle data, as single-language subtitles already have the correct ID format
      advancedPlayerRef.current.setSubtitles(newSubtitles);
      console.log('🔄 Switched player subtitle language:', language);
    }
  };

  // Handle seeking video to a specific time (for subtitle editing - pause at position)
  const handleSeekVideo = (time: number) => {
    if (advancedPlayerRef.current) {
      advancedPlayerRef.current.seekTo(time);
      // Ensure the video is paused at the position for easy editing
      setTimeout(() => {
        if (advancedPlayerRef.current) {
          advancedPlayerRef.current.pause();
        }
      }, 100);
    } else if (videoRef.current) {
      videoRef.current.currentTime = time;
      // Don't autoplay, stay paused for editing
      videoRef.current.pause();
    }
  };

  // Handle playback speed change
  const handlePlaySpeedChange = (speed: number) => {
    if (advancedPlayerRef.current) {
      advancedPlayerRef.current.setPlaybackRate(speed);
    } else if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
  };

  // Handle play/pause toggle
  const handlePlayPause = () => {
    if (advancedPlayerRef.current) {
      advancedPlayerRef.current.togglePlay();
    } else if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  };

  // Get current playing state
  const isPlaying = (() => {
    if (advancedPlayerRef.current) {
      return !advancedPlayerRef.current.isPaused();
    } else if (videoRef.current) {
      return !videoRef.current.paused;
    }
    return false;
  })();

  // Handle video time update
  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time);
  };

  // Handle subtitle click for editing
  const handleSubtitleClick = (subtitle: any) => {
    setSelectedSubtitle(subtitle);
    console.log('Selected subtitle for editing:', subtitle);
  };

  // Handle subtitle inline editing
  const handleSubtitleEdit = (subtitle: any) => {
    setEditingSubtitle(subtitle);
    setShowInlineEditor(true);
  };

  // Handle subtitle save from inline editor - real-time update
  const handleSubtitleSave = (editedSubtitle: any) => {
    console.log('📝 Saving subtitle from inline editor:', {
      id: editedSubtitle.id,
      text: editedSubtitle.text?.substring(0, 30) || '',
      language: currentSubtitleLanguage
    });
    
    // Update local state in real-time (effective immediately)
    const updatedSubtitles = allSubtitles.map(langSub => {
      if (langSub.language === currentSubtitleLanguage) {
        return {
          ...langSub,
          subtitles: langSub.subtitles?.map((sub: any) => 
            sub.id === editedSubtitle.id ? editedSubtitle : sub
          ) || []
        };
      }
      return langSub;
    });
    
    setAllSubtitles(updatedSubtitles);
    
    // Immediately sync to the player
    if (advancedPlayerRef.current?.setSubtitles) {
      const currentLangSubs = updatedSubtitles.find(ls => ls.language === currentSubtitleLanguage)?.subtitles || [];
      // Directly pass subtitle data, as single-language subtitles already have the correct ID format
      advancedPlayerRef.current.setSubtitles(currentLangSubs);
      console.log('📺 Synced to player in real-time:', currentLangSubs.length, 'subtitles');
    }
  };

  // Handle frontend copy update from enhanced editor
  const handleFrontendCopyUpdate = useCallback((frontendCopy: any[]) => {
    console.log('📡 Received frontend copy update:', frontendCopy.length, 'languages');
    
    // Update allSubtitles state
    setAllSubtitles(frontendCopy);
    
    // Sync current language subtitles to the video player
    const currentLangData = frontendCopy.find(langSub => langSub.language === currentSubtitleLanguage);
    if (currentLangData && advancedPlayerRef.current?.setSubtitles) {
      console.log('🎬 Syncing frontend copy to video player:', currentLangData.subtitles.length, 'subtitles');
      advancedPlayerRef.current.setSubtitles(currentLangData.subtitles);
    }
  }, [currentSubtitleLanguage]);

  // Handle subtitle save from enhanced editor
  const handleEnhancedSubtitleSave = async (subtitle: any, language: string) => {
    // Check for bulk updates (like merge, split, etc.)
    if (subtitle.type === 'BULK_UPDATE') {
      console.log('🔄 Processing bulk update:', {
        action: subtitle.action,
        language: subtitle.language,
        subtitleCount: subtitle.subtitles.length,
        details: subtitle.details
      });
      
      // Directly update the subtitle list for the entire language
      const updatedSubtitles = allSubtitles.map(langSub => {
        if (langSub.language === subtitle.language) {
          return {
            ...langSub,
            subtitles: subtitle.subtitles
          };
        }
        return langSub;
      });
      
      setAllSubtitles(updatedSubtitles);
      setHasUnsavedChanges(true); // Mark as unsaved
      
      // Immediately refresh the video player
      if (advancedPlayerRef.current?.setSubtitles && subtitle.language === currentSubtitleLanguage) {
        console.log('🎬 Bulk updating video player subtitles:', subtitle.subtitles.length, 'items');
        advancedPlayerRef.current.setSubtitles(subtitle.subtitles);
      }
      
      return; // Bulk updates don't need the single subtitle processing logic below
    }
    
    // Handle single subtitle update
    console.log('🔥 [Preview] Received subtitle update:', { 
      id: subtitle.id, 
      text: subtitle.text?.substring(0, 30) + '...', 
      language,
      startTime: subtitle.startTime,
      endTime: subtitle.endTime,
      currentSubtitleLanguage: currentSubtitleLanguage,
      'Language Match': language === currentSubtitleLanguage ? '✅' : '❌'
    });
    
    // Handle multi-language ID matching
    const backendSubtitleId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
    
    // Immediately update local state - full update of subtitle properties (text + time)
    const updatedSubtitles = allSubtitles.map(langSub => {
      if (langSub.language === language) {
        return {
          ...langSub,
          subtitles: langSub.subtitles?.map((sub: any) => {
            return sub.id === backendSubtitleId ? { 
              ...sub, 
              text: subtitle.text, 
              startTime: subtitle.startTime ?? sub.startTime, 
              endTime: subtitle.endTime ?? sub.endTime 
            } : sub;
          }) || []
        };
      }
      return langSub;
    });
    
    setAllSubtitles(updatedSubtitles);
    setHasUnsavedChanges(true); // Mark as unsaved
    
    // Player will auto-update via props, no manual call needed
    if (advancedPlayerRef.current && language === currentSubtitleLanguage) {
      console.log('🔥 [Preview] Single subtitle update, player will refresh via props.');
    }
    
    // Call backend auto-save API to persist changes
    try {
      const currentLangSubtitles = updatedSubtitles.find(ls => ls.language === language)?.subtitles || [];
      const response = await fetch(`/api/v1/subtitles/auto-save/${globalJobId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            language: language,
            subtitles: currentLangSubtitles
          })
        }
      );
      
      if (response.ok) {
        console.log('✅ Auto-save successful');
      } else {
        console.warn('⚠️ Auto-save failed:', response.statusText);
      }
    } catch (error) {
      console.warn('⚠️ Auto-save request failed:', error);
    }
    
    // Debug merge operation
    if (subtitle.mergeOperation) {
      console.group('🔗 Debugging subtitle merge operation');
      console.log('Original subtitle ID:', subtitle.id);
      console.log('Deleted subtitle ID:', subtitle.mergeOperation.nextSubtitleId);
      console.log('Merged text:', subtitle.mergeOperation.mergedText);
      console.log('New end time:', subtitle.mergeOperation.newEndTime);
      console.log('Start time:', subtitle.startTime);
      console.groupEnd();
    }
    
    try {
      // Determine edit type and call the corresponding API
      let result: any;
      
      if (subtitle.id.startsWith('new-') || subtitle.id.startsWith('split-')) {
        // Newly created subtitle
        result = await subtitleEditService.createSubtitle(
          selectedJob.id, 
          language, 
          subtitle // Pass the complete subtitle object
        );
      } else if (subtitle.mergeOperation) {
        // Merge operation
        console.log('🔗 Processing subtitle merge operation:', subtitle.mergeOperation);
        // Clean up IDs for the merge operation
        const cleanCurrentId = subtitle.id.includes('-') ? subtitle.id.split('-')[1] : subtitle.id;
        const cleanNextId = subtitle.mergeOperation.nextSubtitleId.includes('-') ? 
          subtitle.mergeOperation.nextSubtitleId.split('-')[1] : subtitle.mergeOperation.nextSubtitleId;
        
        result = await subtitleEditService.mergeSubtitles(
          selectedJob.id,
          language,
          cleanCurrentId,
          cleanNextId,
          subtitle.mergeOperation.mergedText,
          subtitle.mergeOperation.newEndTime,
          subtitle.startTime
        );
      } else {
        // Find the original subtitle for comparison
        // Use the previously extracted backendSubtitleId to match the pure numeric ID stored in allSubtitles
        const originalSubtitle = allSubtitles.find(s => s.language === language)?.subtitles.find((sub: any) => {
          return sub.id === backendSubtitleId;
        });
        
        console.log('🔍 Found original subtitle result:', {
          backendSubtitleId,
          originalSubtitle: originalSubtitle ? { id: originalSubtitle.id, text: originalSubtitle.text.substring(0, 20) } : null,
          subtitle: { id: subtitle.id, text: subtitle.text.substring(0, 20) },
          allSubtitlesForLang: allSubtitles.find(s => s.language === language)?.subtitles.map((s: any) => s.id).slice(0, 5)
        });
        
        if (originalSubtitle) {
          if (originalSubtitle.text !== subtitle.text) {
            // Text change
            result = await subtitleEditService.updateSubtitleText(
              selectedJob.id,
              language,
              backendSubtitleId,
              originalSubtitle.text,
              subtitle.text
            );
          } else if (
            originalSubtitle.startTime !== subtitle.startTime || 
            originalSubtitle.endTime !== subtitle.endTime
          ) {
            // Timing change
            result = await subtitleEditService.updateSubtitleTiming(
              selectedJob.id,
              language,
              backendSubtitleId,
              originalSubtitle.startTime,
              subtitle.startTime,
              originalSubtitle.endTime,
              subtitle.endTime
            );
          } else {
            // No changes, no need to save
            return {
              success: true,
              message: 'No changes to subtitle',
              subtitle: subtitle
            };
          }
        } else {
          // If original subtitle is not found, it might be newly created, try to create it
          console.warn('Original subtitle not found, attempting to create new subtitle:', { id: subtitle.id, cleanId: backendSubtitleId });
          result = await subtitleEditService.createSubtitle(
            selectedJob.id,
            language,
            { ...subtitle, id: backendSubtitleId } // Create with the cleaned ID
          );
        }
      }
      
      if (result?.success) {
        console.log('Subtitle saved successfully:', result.message);
        showSuccess('Subtitle saved successfully');
        
        // Auto-save version
        try {
          const primaryLanguage = language;
          const languageSubtitles = allSubtitles.find(s => s.language === language)?.subtitles || [];
          await subtitleVersionService.autoSave(selectedJob.id, primaryLanguage, languageSubtitles);
        } catch (autoSaveError) {
          console.warn('Auto-save failed:', autoSaveError);
        }
        
        // Note: Since EnhancedSubtitleEditor handles real-time state updates internally,
        // this part is mainly for API saving and subsequent processing
        console.log('💾 API save successful, state has been updated in real-time by the editor');
        
        return {
          success: true,
          message: 'Subtitle saved successfully',
          subtitle: subtitle
        };
      } else {
        console.error('Failed to save subtitle:', result?.message);
        showError(result?.message || 'Failed to save subtitle');
        return {
          success: false,
          message: result?.message || 'Failed to save subtitle',
          error: result?.errors
        };
      }
    } catch (error) {
      console.error('Error saving subtitle:', error);
      showError('An error occurred while saving the subtitle');
      return {
        success: false,
        message: 'Failed to save subtitle',
        error: error
      };
    }
  };

  // Handle inline editor close
  const handleInlineEditorClose = () => {
    setShowInlineEditor(false);
    setEditingSubtitle(null);
  };

  // Handle video ready
  const handleVideoReady = (player?: any) => {
    console.log('Video is ready');
    // Get video duration
    if (player && player.duration) {
      const duration = player.duration();
      if (duration && duration > 0) {
        setVideoDuration(duration);
        console.log('Video duration:', duration);
      }
    }
  };

  const handleSaveSuccess = (savedSubtitles: any[]) => {
    console.log('✅ Save successful, updating parent component authoritative state');
    setAllSubtitles(savedSubtitles);
  };
  
  // Handle duration change
  const handleDurationChange = (duration: number) => {
    setVideoDuration(duration);
    console.log('Video duration updated:', duration);
  };

  // Handle language change (multi-select)
  const handleLanguageChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    const newLanguages = typeof value === 'string' ? value.split(',') : value;
    setSelectedLanguages(newLanguages);
    
    // Set current language to first selected language
    if (newLanguages.length > 0) {
      setCurrentSubtitleLanguage(newLanguages[0]);
    }
    // useEffect will handle loading subtitles when selectedLanguages changes
  };

  const handleManualSave = async () => {
    if (!selectedJob) {
      showError('Cannot save: No job selected.');
      return;
    }

    setIsSaving(true);
    try {
      const savePromises = allSubtitles
        .filter(langSub => langSub.subtitles && langSub.subtitles.length > 0)
        .map(langSub => 
          subtitleVersionService.saveWorkingVersion(
            selectedJob.id,
            langSub.language,
            langSub.subtitles,
            'Manual Save' // Description for the saved version
          ).then(response => ({ ...response, language: langSub.language }))
        );

      if (savePromises.length === 0) {
        showWarning('No subtitle content to save.');
        return;
      }

      const results = await Promise.all(savePromises);

      const successfulSaves = results.filter(r => r.success);
      const failedSaves = results.filter(r => !r.success);

      if (successfulSaves.length === results.length) {
        showSuccess(`所有语言(${successfulSaves.length})的字幕修改已保存`);
        setHasUnsavedChanges(false);
      } else if (successfulSaves.length > 0) {
        showWarning(
          `部分保存成功 (${successfulSaves.length}/${results.length})，` +
          `失败语言: ${failedSaves.map(f => f.language).join(', ')}`
        );
        // Only set unsaved changes to false if all intended saves were successful
      } else {
        showError(`Failed to save subtitles for all languages (${failedSaves.length}), please try again.`);
      }

      console.log('Manual save complete:', { successfulSaves, failedSaves });

    } catch (error) {
      console.error('A critical error occurred during manual save:', error);
      showError('A critical error occurred while saving subtitles, please check the console.');
    } finally {
      setIsSaving(false);
    }
  };

  // If loading or error
  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 3, md: 4 }, textAlign: 'center' }}>
        <CircularProgress />
        <Typography sx={{ mt: 2 }}>加载视频预览中...</Typography>
      </Container>
);
  }

  if (error || !selectedJob) {
    return (
      <Container maxWidth="md" sx={{ mt: 4, textAlign: 'center' }}>
        <Alert severity="error">
          {error || '无效或缺少任务 ID，请检查链接'}
        </Alert>
        <Button 
          variant="contained"
          startIcon={<ArrowBackIcon />}
          onClick={handleGoBack}
          sx={{ mt: 2 }}
        >
          返回
        </Button>
      </Container>
    );
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 64px)' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>加载视频预览中...</Typography>
      </Box>
    );
  }

  if (error || !selectedJob) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Alert severity="error">
          {error || '无效或缺少任务 ID，请检查链接'}
        </Alert>
        <Button 
          variant="contained"
          startIcon={<ArrowBackIcon />}
          onClick={handleGoBack}
          sx={{ mt: 2 }}
        >
          返回
        </Button>
      </Box>
    );
  }

  const globalJobId = selectedJob.id; // Keep for internal operations that need global ID

  return (
    <Box sx={{ 
      height: '100vh',
      background: '#f5f5f5',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      <Box sx={{ 
        px: 3,
        py: 1.5, // Reduce vertical margin
        background: 'background.paper',
        borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        flexWrap: 'nowrap',
        gap: 2,
        boxShadow: '0 1px 4px rgba(0, 0, 0, 0.08)',
        minHeight: '72px' // Set minimum height
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <IconButton 
            component={Link} 
            to="/dashboard/projects"
            sx={{ 
              mr: 2,
              background: '#f5f5f5',
              border: '1px solid #e0e0e0',
              borderRadius: '12px',
              color: '#666',
              '&:hover': {
                background: '#e0e0e0',
                transform: 'translateY(-2px)',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)'
              },
              transition: 'all 0.3s ease'
            }}
          >
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography 
              variant="h5" 
              component="h1" 
              noWrap 
              sx={{ 
                maxWidth: { xs: '200px', sm: '300px', md: 'unset' },
                color: '#333',
                fontWeight: 600
              }}
            >
              {selectedJob ? selectedJob.title : '视频预览'}
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          {/* Compact language selection */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, color: '#333', whiteSpace: 'nowrap' }}>
              字幕语言:
            </Typography>
            
            {/* Selected languages */}
            {selectedLanguages.length > 0 && (
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
                {selectedLanguages.map((lang) => (
                  <Chip
                    key={lang}
                    label={
                      lang === 'auto' ? '自动' :
                      lang === 'src' ? '原文' :
                      lang === 'zh' ? '中文' :
                      lang === 'en' ? '英语' :
                      lang === 'es' ? '西班牙语' :
                      lang === 'fr' ? '法语' :
                      lang === 'de' ? '德语' :
                      lang === 'ja' ? '日语' :
                      lang === 'ko' ? '韩语' :
                      lang === 'pt' ? '葡萄牙语' :
                      lang === 'ru' ? '俄语' :
                      lang === 'it' ? '意大利语' :
                      lang === 'ar' ? '阿拉伯语' :
                      lang === 'hi' ? '印地语' :
                      lang
                    }
                    onDelete={() => {
                      const newSelected = selectedLanguages.filter(l => l !== lang);
                      setSelectedLanguages(newSelected);
                      if (newSelected.length > 0) {
                        setCurrentSubtitleLanguage(newSelected[0]);
                      }
                      // useEffect will handle loading subtitles when selectedLanguages changes
                    }}
                    color={selectedLanguages.length > 1 ? "primary" : "default"}
                    variant={selectedLanguages.length > 1 ? "filled" : "outlined"}
                    size="small"
                  />
                ))}
              </Stack>
            )}
          </Box>
          
          {/* Available languages (compact) */}
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
            {availableLanguages.filter(lang => !selectedLanguages.includes(lang)).map((lang) => (
              <Chip
                key={lang}
                label={
                  lang === 'auto' ? '自动' :
                  lang === 'src' ? '原文' :
                  lang === 'zh' ? '中文' :
                  lang === 'en' ? '英语' :
                  lang === 'es' ? '西班牙语' :
                  lang === 'fr' ? '法语' :
                  lang === 'de' ? '德语' :
                  lang === 'ja' ? '日语' :
                  lang === 'ko' ? '韩语' :
                  lang === 'pt' ? '葡萄牙语' :
                  lang === 'ru' ? '俄语' :
                  lang === 'it' ? '意大利语' :
                  lang === 'ar' ? '阿拉伯语' :
                  lang === 'hi' ? '印地语' :
                  lang
                }
                onClick={() => {
                  const newSelected = [...selectedLanguages, lang];
                  setSelectedLanguages(newSelected);
                  setCurrentSubtitleLanguage(lang);
                  // useEffect will handle loading subtitles when selectedLanguages changes
                }}
                variant="outlined"
                size="small"
                sx={{ 
                  cursor: 'pointer',
                  opacity: 0.7,
                  '&:hover': {
                    opacity: 1,
                    backgroundColor: 'primary.light',
                    color: 'white'
                  }
                }}
              />
            ))}
          </Stack>
        </Box>
      </Box>

      <Grid container spacing={2} sx={{ 
        flex: 1,
        overflow: 'hidden',
        height: 'calc(100% - 72px)', // Match top minimum height
        alignItems: 'stretch',
        px: 2,
        py: 1.5 // Reduce vertical margin
      }}>
        <Grid item xs={12} md={7} sx={{ 
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
        }}>
          <Paper elevation={2} sx={{ 
            p: 1,
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            background: 'background.paper',
            borderRadius: '12px',
            minHeight: 0 // Ensure proper scaling
          }}>
            <VideoJSAdvancedPlayer 
              ref={advancedPlayerRef}
              src={previewService.getOriginalVideoPreviewUrl(globalJobId)}
              title={`${selectedJob.title}${selectedJob.status?.toLowerCase() !== 'completed' ? ' (处理中...)' : ''}`}
              width="100%"
              height="100%"
              controls
              autoPlay={false}
              subtitles={currentLanguageSubtitles}
              multiLanguageSubtitles={selectedLanguages.length > 1 ? multiLanguageSubtitles : {}}
              selectedLanguages={selectedLanguages.length > 1 ? selectedLanguages : []}
              currentSubtitleLanguage={currentSubtitleLanguage}
              onTimeUpdate={handleTimeUpdate}
              onReady={handleVideoReady}
              onDurationChange={handleDurationChange}
              onError={(error) => {
                console.error('VideoJS Advanced player error:', error);
                // If job is not completed, provide more friendly error message
                if (selectedJob.status !== 'COMPLETED') {
                  console.warn('Job status:', selectedJob.status, 'Video may be processing');
                }
              }}
              onSubtitleClick={handleSubtitleEdit}
              style={{ 
                width: '100%',
                height: '100%',
                flex: 1,
                minHeight: 0
              }}
            />
          </Paper>
        </Grid>
        <Grid item xs={12} md={5} sx={{ 
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
        }}>
          <Paper elevation={2} sx={{ 
            p: 2,
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            height: '100%',
            background: 'background.paper',
            borderRadius: '12px',
            minHeight: 0
          }}>
            <EnhancedSubtitleEditor 
              jobId={globalJobId}
              languages={selectedLanguages}
              subtitles={allSubtitles}
              currentTime={currentTime}
              videoDuration={videoDuration}
              onSubtitleClick={handleSeekVideo}
              onSubtitleSave={handleEnhancedSubtitleSave}
              onPlaySpeedChange={handlePlaySpeedChange}
              onPlayPause={handlePlayPause}
              isPlaying={isPlaying}
              onFrontendCopyUpdate={handleFrontendCopyUpdate}
              onSaveSuccess={handleSaveSuccess}
              onManualSave={handleManualSave}
              isSaving={isSaving}
            />
            
            {/* Subtitle inline editor */}
            <SubtitleInlineEditor
              subtitle={editingSubtitle}
              open={showInlineEditor}
              onClose={handleInlineEditorClose}
              onSave={handleSubtitleSave}
              currentTime={currentTime}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

// VideoPlayer props are already properly typed in the component itself

export default Preview;
