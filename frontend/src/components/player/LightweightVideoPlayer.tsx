import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Box, Typography, CircularProgress, Alert, FormControl, Select, MenuItem, InputLabel } from '@mui/material';
import 'video.js/dist/video-js.css';
import { useVideoJS } from '../../hooks/useVideoJS';
import { getVideoType } from '../../utils/videoUtils';
import Player from 'video.js/dist/types/player';

interface LightweightVideoPlayerProps {
  jobId: number;
  title?: string;
  availableLanguages?: string[];
  onLanguageChange?: (language: string) => void;
}

const getLanguageLabel = (languageCode: string): string => {
    const labelMap: { [key: string]: string } = {
      'zh': '中文',
      'en': 'English',
      'ja': '日本語',
      'ko': '한국어',
      'fr': 'Français',
      'es': 'Español',
      'de': 'Deutsch'
    };
    return labelMap[languageCode] || languageCode;
};

const LightweightVideoPlayer: React.FC<LightweightVideoPlayerProps> = ({
  jobId,
  title,
  availableLanguages = [],
  onLanguageChange
}) => {
  const videoRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');

  const videoUrl = useMemo(() => `/api/v1/preview/video/${jobId}`, [jobId]);
  const getSubtitleUrl = useCallback((language: string) => `/api/v1/downloads/results/${jobId}/subtitles?format=vtt&language=${language}`, [jobId]);

  useEffect(() => {
    if (availableLanguages.length > 0 && !selectedLanguage) {
      const defaultLang = availableLanguages.includes('zh') ? 'zh' : availableLanguages[0];
      setSelectedLanguage(defaultLang);
    }
  }, [availableLanguages, selectedLanguage]);

  const loadSubtitles = useCallback((language: string, player: Player) => {
    try {
      if (!language) return;
      const subtitleUrl = getSubtitleUrl(language);
      
      // The TextTrackList type definition from video.js is incorrect, so we cast to `any` 
      // to make it compatible with Array.from.
      const tracksToRemove = Array.from(player.remoteTextTracks() as any);
      tracksToRemove.forEach((track: any) => {
        player.removeRemoteTextTrack(track);
      });

      player.addRemoteTextTrack({
        kind: 'subtitles',
        src: subtitleUrl,
        srclang: language,
        label: getLanguageLabel(language),
        default: true
      }, false);

      console.log(`Loaded subtitles for language: ${language}`);
    } catch (e) {
      console.warn(`Failed to load subtitles for language ${language}:`, e);
    }
  }, [getSubtitleUrl]);

  const playerOptions = useMemo(() => ({
    controls: true,
    responsive: true,
    fluid: true,
    sources: [{
      src: videoUrl,
      type: getVideoType(videoUrl)
    }],
    playbackRates: [0.5, 1, 1.25, 1.5, 2],
  }), [videoUrl]);

  const playerCallbacks = useMemo(() => ({
    onReady: (player: Player) => {
      console.log('Lightweight player is ready');
      setLoading(false);
      if (selectedLanguage) {
        loadSubtitles(selectedLanguage, player);
      }
    },
    onError: () => {
      console.error('Video player error');
      setError('无法加载视频文件');
      setLoading(false);
    }
  }), [selectedLanguage, loadSubtitles]);

  const playerRef = useVideoJS({
    videoNodeRef: videoRef,
    options: playerOptions,
    callbacks: playerCallbacks,
  });

  const handleLanguageChange = (event: any) => {
    const newLanguage = event.target.value;
    setSelectedLanguage(newLanguage);
    
    const player = playerRef.current;
    if (player && !player.isDisposed()) {
      loadSubtitles(newLanguage, player);
    }
    
    onLanguageChange?.(newLanguage);
  };

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      
      {availableLanguages.length > 1 && (
        <Box sx={{ mb: 2 }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>字幕语言</InputLabel>
            <Select
              value={selectedLanguage}
              onChange={handleLanguageChange}
              label="字幕语言"
            >
              <MenuItem value="">无字幕</MenuItem>
              {availableLanguages.map((lang) => (
                <MenuItem key={lang} value={lang}>
                  {getLanguageLabel(lang)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

      <Box 
        sx={{ 
          position: 'relative',
          width: '100%',
          backgroundColor: '#000',
          borderRadius: 1,
          overflow: 'hidden'
        }}
      >
        {loading && (
          <Box
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 10
            }}
          >
            <CircularProgress size={48} sx={{ color: 'white' }} />
          </Box>
        )}
        <div ref={videoRef} style={{ width: '100%' }} />
      </Box>

      <Box sx={{ mt: 1, display: 'flex', gap: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
        <Typography variant="caption">
          云端智能处理模式
        </Typography>
        {selectedLanguage && (
          <Typography variant="caption">
            当前字幕：{getLanguageLabel(selectedLanguage)}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default LightweightVideoPlayer;
