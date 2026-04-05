import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle, useCallback, useMemo } from 'react';
import { Box, Typography, CircularProgress, Alert, Button, IconButton } from '@mui/material';
import { Refresh as RefreshIcon, Settings as SettingsIcon } from '@mui/icons-material';
import 'video.js/dist/video-js.css';
import '../../styles/videojs-advanced.css';
import Player from 'video.js/dist/types/player';
import SubtitleStyleControls, { SubtitleStyle } from './SubtitleStyleControls';
import { getVideoType } from '../../utils/videoUtils';
import { useVideoJS } from '../../hooks/useVideoJS';

interface Subtitle {
  id: string;
  startTime: number;
  endTime: number;
  text: string;
  isEditing?: boolean;
}

interface MultiLanguageSubtitles {
  [languageCode: string]: Subtitle[];
}

interface VideoJSAdvancedPlayerProps {
  src: string;
  fallbackSrc?: string;
  title?: string;
  width?: string | number;
  height?: string | number;
  autoPlay?: boolean;
  controls?: boolean;
  subtitles?: Subtitle[];
  multiLanguageSubtitles?: MultiLanguageSubtitles;
  selectedLanguages?: string[];
  currentSubtitleLanguage?: string;
  jobId?: number;
  onTimeUpdate?: (time: number) => void;
  onReady?: (player: Player) => void;
  onDurationChange?: (duration: number) => void;
  onError?: (error: any) => void;
  onSubtitleClick?: (subtitle: Subtitle) => void;
  className?: string;
  style?: React.CSSProperties;
}

export interface VideoJSAdvancedPlayerRef {
  play: () => Promise<void>;
  pause: () => void;
  currentTime: (time?: number) => number;
  duration: () => number;
  getPlayer: () => Player | null;
  setSubtitles: (subtitles: Subtitle[]) => void;
  toggleSubtitles: (show: boolean) => void;
  seekTo: (time: number) => void;
  togglePlay: () => Promise<void>;
  setPlaybackRate: (rate: number) => void;
  getPlaybackRate: () => number;
  isPaused: () => boolean;
  updateSubtitleText: (id: string, newText: string) => void;
  finishSubtitleEdit: (id: string, finalText: string) => void;
  cancelSubtitleEdit: (id: string) => void;
}

const VideoJSAdvancedPlayer = forwardRef<VideoJSAdvancedPlayerRef, VideoJSAdvancedPlayerProps>(({
  src,
  fallbackSrc,
  title,
  width = '100%',
  height = '100%',
  autoPlay = false,
  controls = true,
  subtitles = [],
  multiLanguageSubtitles = {},
  selectedLanguages = [],
  currentSubtitleLanguage = 'zh',
  jobId,
  onTimeUpdate,
  onReady,
  onDurationChange,
  onError,
  onSubtitleClick,
  className = '',
  style = {},
}, ref) => {
  const videoRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processedSrc, setProcessedSrc] = useState<string>('');
  const [currentVideoSrc, setCurrentVideoSrc] = useState<string>(src);
  const [hasTriedFallback, setHasTriedFallback] = useState<boolean>(false);
  
  const [internalSubtitles, setInternalSubtitles] = useState<Subtitle[]>(subtitles);
  const [currentSubtitle, setCurrentSubtitle] = useState<string>('');
  const [showSubtitles, setShowSubtitles] = useState<boolean>(true);
  const [editingSubtitleId, setEditingSubtitleId] = useState<string | null>(null);
  
  const [styleControlsAnchor, setStyleControlsAnchor] = useState<HTMLElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>({
    fontSize: 20, fontFamily: 'Arial', fontWeight: 'normal', fontStyle: 'normal',
    color: '#FFFFFF', backgroundColor: '#000000', backgroundOpacity: 0.7,
    strokeColor: '#000000', strokeWidth: 1, position: 'bottom', alignment: 'center'
  });

  useEffect(() => {
    setCurrentVideoSrc(src);
    setHasTriedFallback(false);
    setError(null);
  }, [src]);

  useEffect(() => {
    setInternalSubtitles(subtitles);
  }, [subtitles]);

  const getCurrentSubtitle = useCallback((currentTime: number): string => {
    if (!internalSubtitles || internalSubtitles.length === 0) return '';
    
    // Add small tolerance for timing precision issues (especially for first subtitle at 0.000)
    const tolerance = 0.1; // 100ms tolerance
    
    // Debug: Log first subtitle details when video starts
    if (currentTime < 1.0 && internalSubtitles.length > 0) {
      console.log('[DEBUG] First subtitle check:', {
        currentTime: currentTime.toFixed(3),
        firstSubtitle: {
          id: internalSubtitles[0].id,
          startTime: internalSubtitles[0].startTime,
          endTime: internalSubtitles[0].endTime,
          text: internalSubtitles[0].text.substring(0, 50) + '...'
        },
        tolerance,
        matchCondition: `${currentTime.toFixed(3)} >= ${(internalSubtitles[0].startTime - tolerance).toFixed(3)} && ${currentTime.toFixed(3)} <= ${(internalSubtitles[0].endTime + tolerance).toFixed(3)}`
      });
    }
    
    const matchingSubtitle = internalSubtitles.find(sub => 
      currentTime >= (sub.startTime - tolerance) && currentTime <= (sub.endTime + tolerance)
    );
    
    // Debug: Log when first subtitle should be found but isn't
    if (currentTime < 1.0 && !matchingSubtitle && internalSubtitles.length > 0) {
      console.warn('[DEBUG] First subtitle not matched:', {
        currentTime: currentTime.toFixed(3),
        firstSubStartTime: internalSubtitles[0].startTime,
        condition1: currentTime >= (internalSubtitles[0].startTime - tolerance),
        condition2: currentTime <= (internalSubtitles[0].endTime + tolerance)
      });
    }
    
    return matchingSubtitle ? matchingSubtitle.text : '';
  }, [internalSubtitles]);

  // New function to get multi-language subtitles
  const getMultiLanguageSubtitles = useCallback((currentTime: number): string[] => {
    const subtitleTexts: string[] = [];
    
    if (!selectedLanguages || selectedLanguages.length === 0) {
      return subtitleTexts; // Return empty array if no languages selected
    }
    
    // Add small tolerance for timing precision issues (especially for first subtitle at 0.000)
    const tolerance = 0.1; // 100ms tolerance
    
    selectedLanguages.forEach(langCode => {
      const langSubtitles = multiLanguageSubtitles[langCode];
      if (langSubtitles && langSubtitles.length > 0) {
        const matchingSubtitle = langSubtitles.find(sub => 
          currentTime >= (sub.startTime - tolerance) && currentTime <= (sub.endTime + tolerance)
        );
        if (matchingSubtitle && matchingSubtitle.text.trim()) {
          // Add language label for clarity
          const langLabel = langCode === 'src' ? 'Original' : 
                           langCode === 'zh' ? 'Chinese' : 
                           langCode === 'en' ? 'English' : 
                           langCode.toUpperCase();
          subtitleTexts.push(`[${langLabel}] ${matchingSubtitle.text}`);
        }
      }
    });

    return subtitleTexts;
  }, [selectedLanguages, multiLanguageSubtitles]);

  useEffect(() => {
    if (!currentVideoSrc) {
      setError('No video source provided');
      return;
    }
    let processedUrl = currentVideoSrc;
    if (currentVideoSrc.includes('/api/v1/') || currentVideoSrc.includes('localhost')) {
      try {
        const url = new URL(currentVideoSrc, window.location.origin);
        const token = localStorage.getItem('token');
        if (token) url.searchParams.set('token', token);
        if (!url.searchParams.has('streamable')) url.searchParams.set('streamable', 'true');
        processedUrl = url.toString();
      } catch (urlError) {
        console.error('Error processing URL:', urlError);
      }
    }
    setProcessedSrc(processedUrl);
  }, [currentVideoSrc]);

  const playerOptions = useMemo(() => {
    if (!processedSrc) return null;
    return {
      controls: true, responsive: true, fluid: false, fill: true, autoplay: false,
      muted: false, preload: 'metadata', loadingSpinner: true, playbackRates: [],
      aspectRatio: '16:9', sources: [{ src: processedSrc, type: getVideoType(processedSrc) }],
      techOrder: ['html5'],
      controlBar: {
        playToggle: true, progressControl: true, currentTimeDisplay: true, durationDisplay: true,
        volumePanel: { inline: false, vertical: true }, fullscreenToggle: true
      }
    };
  }, [processedSrc]);

  const handlePlayerError = useCallback((playerError: any) => {
    console.error('VideoJS player error:', playerError);
    setLoading(false);

    if (fallbackSrc && !hasTriedFallback) {
      console.log('SMART FALLBACK: Trying fallback video:', fallbackSrc);
      setHasTriedFallback(true);
      setCurrentVideoSrc(fallbackSrc);
      return;
    }

    let errorMessage = 'Video loading failed';
    if (playerError) {
      switch (playerError.code) {
        case 1: errorMessage = 'Video loading was aborted'; break;
        case 2: errorMessage = 'Network error, please check network connection'; break;
        case 3: errorMessage = 'Video decoding error, file may be corrupted'; break;
        case 4: errorMessage = hasTriedFallback ? 'Video format not supported, both original video and subtitle version cannot be played' : 'Video format not supported or codec missing'; break;
        default: errorMessage = playerError.message || `Video loading failed (error code: ${playerError.code})`;
      }
    }
    setError(errorMessage);
    onError?.(playerError);
  }, [fallbackSrc, hasTriedFallback, onError]);

  const playerCallbacks = useMemo(() => ({
    onReady: (player: Player) => {
      console.log('VideoJS Advanced Player ready');
      setLoading(false);
      setError(null);
      player.volume(0.7);
      onReady?.(player);
    },
    onPlay: () => { setLoading(false); setIsPlaying(true); },
    onPause: () => setIsPlaying(false),
    onLoadStart: () => { setLoading(true); setError(null); },
    onLoadedData: () => setLoading(false),
    onTimeUpdate: (time: number) => {
      let subtitleText = '';
      
      // Debug logging - only log frequently during first few seconds
      if (time < 5.0) {
        console.log('[VideoJS Player] Time:', time.toFixed(3), 'Selected Languages:', selectedLanguages, 'Internal Subtitles:', internalSubtitles.length);
        if (internalSubtitles.length > 0) {
          console.log('[VideoJS Player] First subtitle available:', {
            id: internalSubtitles[0].id,
            startTime: internalSubtitles[0].startTime,
            endTime: internalSubtitles[0].endTime,
            text: internalSubtitles[0].text.substring(0, 30) + '...'
          });
        }
      }
      
      // Check if multi-language mode is enabled and we have selected languages
      if (selectedLanguages && selectedLanguages.length > 0) {
        const multiSubtitles = getMultiLanguageSubtitles(time);
        subtitleText = multiSubtitles.join('\n');
        if (time < 5.0) console.log('[VideoJS Player] Multi-language subtitles:', multiSubtitles);
      } else {
        // Fall back to single language subtitle
        subtitleText = getCurrentSubtitle(time);
        if (time < 5.0) console.log('[VideoJS Player] Single language subtitle:', subtitleText);
      }
      
      if (subtitleText !== currentSubtitle) {
        setCurrentSubtitle(subtitleText);
        console.log('[VideoJS Player] Setting subtitle text:', subtitleText.substring(0, 50) + (subtitleText.length > 50 ? '...' : ''));
      }
      onTimeUpdate?.(time);
    },
    onDurationChange: onDurationChange,
    onError: (error: any) => handlePlayerError(error),
  }), [onReady, onTimeUpdate, onDurationChange, getCurrentSubtitle, getMultiLanguageSubtitles, currentSubtitle, handlePlayerError, selectedLanguages, internalSubtitles]);

  const playerRef = useVideoJS({
    videoNodeRef: videoRef,
    options: playerOptions,
    callbacks: playerCallbacks,
  });

  const handleTogglePlay = useCallback(async () => {
    const player = playerRef.current;
    if (!player || player.isDisposed()) return;

    try {
      if (player.paused()) {
        await player.play();
      } else {
        player.pause();
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error("Player toggle failed", error);
      }
    }
  }, [playerRef]);

  useImperativeHandle(ref, () => ({
    play: async () => { await playerRef.current?.play(); },
    pause: () => { playerRef.current?.pause(); },
    currentTime: (time) => {
      if (time !== undefined) playerRef.current?.currentTime(time);
      return playerRef.current?.currentTime() || 0;
    },
    duration: () => playerRef.current?.duration() || 0,
    getPlayer: () => playerRef.current,
    setSubtitles: (newSubtitles) => setInternalSubtitles(newSubtitles),
    toggleSubtitles: (show) => setShowSubtitles(show),
    seekTo: (time) => { playerRef.current?.currentTime(time); },
    togglePlay: handleTogglePlay,
    setPlaybackRate: (rate) => { playerRef.current?.playbackRate(rate); },
    getPlaybackRate: () => playerRef.current?.playbackRate() || 1,
    isPaused: () => playerRef.current?.paused() ?? true,
    updateSubtitleText: (id, newText) => {
      const player = playerRef.current;
      if (!player) return;
      const targetSub = internalSubtitles.find(sub => sub.id.endsWith(id.split('-').pop() || ''));
      if (targetSub && (player.currentTime() || 0) >= targetSub.startTime && (player.currentTime() || 0) <= targetSub.endTime) {
        setCurrentSubtitle(newText);
      }
    },
    finishSubtitleEdit: (id, finalText) => {
      setEditingSubtitleId(null);
      const player = playerRef.current;
      if (!player) return;
      const targetSub = internalSubtitles.find(sub => sub.id === id);
      if (targetSub && (player.currentTime() || 0) >= targetSub.startTime && (player.currentTime() || 0) <= targetSub.endTime) {
        setCurrentSubtitle(finalText);
      }
    },
    cancelSubtitleEdit: () => setEditingSubtitleId(null),
  }), [playerRef, internalSubtitles, handleTogglePlay]);

  useEffect(() => {
    const player = playerRef.current;
    if (player && !player.isDisposed() && processedSrc) {
      const currentSrc = player.currentSrc();
      if (currentSrc !== processedSrc) {
        player.src({ src: processedSrc, type: getVideoType(processedSrc) });
      }
    }
  }, [processedSrc, playerRef]);

  const handleRetry = () => {
    setError(null);
    setLoading(true);
    setCurrentVideoSrc(src); // Reset to original src to retry
    setHasTriedFallback(false);
  };

  if (error) {
    return (
      <Box sx={{ ...style, width, height, minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Alert severity="error" action={<Button onClick={handleRetry} size="small">Retry</Button>}>{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ ...style, width, height, minHeight: '300px', backgroundColor: '#000', position: 'relative' }} className={`videojs-advanced-container ${className}`}>
      {title && (
        <Box sx={{ position: 'absolute', top: 8, left: 8, right: 8, zIndex: 10, pointerEvents: 'none' }}>
          <Typography variant="subtitle1" sx={{ color: 'white', textShadow: '1px 1px 3px rgba(0,0,0,0.8)' }}>{title}</Typography>
          {hasTriedFallback && <Typography variant="caption" sx={{ color: '#90caf9' }}>📹 Using embedded subtitle version</Typography>}
        </Box>
      )}
      {loading && (
        <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 20 }}>
          <CircularProgress size={30} /><Typography variant="body2" sx={{ color: 'white', ml: 1 }}>Loading...</Typography>
        </Box>
      )}
      <Box onClick={handleTogglePlay} sx={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 'calc(100% - 50px)', zIndex: 3, cursor: 'pointer' }} />
      <Box ref={videoRef} sx={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, zIndex: 2 }} />
      {showSubtitles && currentSubtitle && (
        <Box
          onClick={() => {
            const time = playerRef.current?.currentTime() || 0;
            const activeSubtitle = subtitles.find(s => time >= s.startTime && time <= s.endTime);
            if (activeSubtitle) {
              playerRef.current?.pause();
              setEditingSubtitleId(activeSubtitle.id);
              onSubtitleClick?.(activeSubtitle);
            }
          }}
          sx={{ position: 'absolute', bottom: 60, left: '50%', transform: 'translateX(-50%)', zIndex: 15, maxWidth: '90%', textAlign: 'center', pointerEvents: 'auto', cursor: 'pointer' }}
        >
          <Typography sx={{ 
            ...subtitleStyle, 
            padding: '8px 16px', 
            borderRadius: '8px', 
            display: 'inline-block',
            whiteSpace: 'pre-line', // Support line breaks
            lineHeight: 1.4,
            maxWidth: '100%'
          }}>
            {currentSubtitle}
          </Typography>
        </Box>
      )}
      <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 16 }}>
        <IconButton 
          size="small" 
          onClick={(e) => setStyleControlsAnchor(e.currentTarget)}
          sx={{
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            border: '2px solid rgba(255, 255, 255, 0.3)',
            backdropFilter: 'blur(4px)',
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.9)',
              border: '2px solid rgba(255, 255, 255, 0.6)',
              transform: 'scale(1.1)',
            },
            '&:active': {
              backgroundColor: 'rgba(255, 255, 255, 0.2)',
              color: '#000',
            },
            transition: 'all 0.2s ease-in-out',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
          }}
        >
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Box>
      <SubtitleStyleControls style={subtitleStyle} onChange={setSubtitleStyle} anchorEl={styleControlsAnchor} open={Boolean(styleControlsAnchor)} onClose={() => setStyleControlsAnchor(null)} />
    </Box>
  );
});

VideoJSAdvancedPlayer.displayName = 'VideoJSAdvancedPlayer';

export default VideoJSAdvancedPlayer;
