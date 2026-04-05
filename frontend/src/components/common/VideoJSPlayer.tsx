import React, { useRef, forwardRef, useImperativeHandle, useMemo, useEffect } from 'react';
import 'video.js/dist/video-js.css';
import { getVideoType } from '../../utils/videoUtils';
import { useVideoJS, VideoJSEventCallbacks } from '../../hooks/useVideoJS';
import Player from 'video.js/dist/types/player';

type VideoJSPlayerType = Player;

export interface VideoJSPlayerProps {
  src: string;
  poster?: string;
  width?: number | string;
  height?: number | string;
  controls?: boolean;
  autoplay?: boolean;
  preload?: 'auto' | 'metadata' | 'none';
  muted?: boolean;
  playsinline?: boolean;
  className?: string;
  onReady?: (player: VideoJSPlayerType) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onTimeUpdate?: (currentTime: number) => void;
  onDurationChange?: (duration: number) => void;
  onVolumeChange?: (volume: number) => void;
  onError?: (error: any) => void;
  onEnded?: () => void;
  onLoadStart?: () => void;
  onLoadedData?: () => void;
  onCanPlay?: () => void;
  onSeeking?: () => void;
  onSeeked?: () => void;
  options?: any;
}

export interface VideoJSPlayerRef {
  player: VideoJSPlayerType | null;
  play: () => Promise<void>;
  pause: () => void;
  currentTime: (time?: number) => number;
  duration: () => number;
  volume: (vol?: number) => number;
  muted: (mute?: boolean) => boolean;
  paused: () => boolean;
  seeking: () => boolean;
  ended: () => boolean;
}

const VideoJSPlayer = forwardRef<VideoJSPlayerRef, VideoJSPlayerProps>(({
  src,
  poster,
  controls = true,
  autoplay = false,
  preload = 'metadata',
  muted = false,
  playsinline = true,
  className = '',
  onReady,
  onPlay,
  onPause,
  onTimeUpdate,
  onDurationChange,
  onVolumeChange,
  onError,
  onEnded,
  onLoadStart,
  onLoadedData,
  onCanPlay,
  onSeeking,
  onSeeked,
  options: customOptions = {}
}, ref) => {
  const videoRef = useRef<HTMLDivElement>(null);

  const playerOptions = useMemo(() => ({
    controls,
    responsive: true,
    fluid: true,
    fill: true,
    preload,
    autoplay,
    muted,
    playsinline,
    poster,
    sources: [{
      src,
      type: getVideoType(src)
    }],
    playbackRates: [0.5, 1, 1.25, 1.5, 2],
    ...customOptions
  }), [src, poster, controls, autoplay, preload, muted, playsinline, customOptions]);

  const playerCallbacks: VideoJSEventCallbacks = useMemo(() => ({
    onReady,
    onPlay,
    onPause,
    onTimeUpdate,
    onDurationChange,
    onVolumeChange,
    onError,
    onEnded,
    onLoadStart,
    onLoadedData,
    onCanPlay,
    onSeeking,
    onSeeked
  }), [
    onReady, onPlay, onPause, onTimeUpdate, onDurationChange, onVolumeChange,
    onError, onEnded, onLoadStart, onLoadedData, onCanPlay, onSeeking, onSeeked
  ]);

  const playerRef = useVideoJS({
    videoNodeRef: videoRef,
    options: playerOptions,
    callbacks: playerCallbacks,
  });

  useImperativeHandle(ref, () => {
    const player = playerRef.current;
    return {
      player,
      play: async () => {
        await player?.play();
      },
      pause: () => {
        player?.pause();
      },
      currentTime: (time?: number) => {
        if (time !== undefined && player) {
          player.currentTime(time);
        }
        return player?.currentTime() || 0;
      },
      duration: () => player?.duration() || 0,
      volume: (vol?: number) => {
        if (vol !== undefined && player) {
          player.volume(vol);
        }
        return player?.volume() || 0;
      },
      muted: (mute?: boolean) => {
        if (mute !== undefined && player) {
          player.muted(mute);
        }
        return player?.muted() || false;
      },
      paused: () => player?.paused() || true,
      seeking: () => player?.seeking() || false,
      ended: () => player?.ended() || false,
    };
  }, [playerRef]);
  
  // This useEffect is to handle src changes after initial load
  useEffect(() => {
    const player = playerRef.current;
    if (player && !player.isDisposed()) {
        const currentSrc = player.currentSrc();
        if (currentSrc !== src) {
            player.src({ src, type: getVideoType(src) });
        }
    }
  }, [src, playerRef]);

  return (
    <div 
      data-vjs-player 
      className={className}
      style={{ 
        width: '100%',
        height: '100%',
        minHeight: '300px',
        position: 'relative'
      }}
    >
      <div ref={videoRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
});

VideoJSPlayer.displayName = 'VideoJSPlayer';

export default VideoJSPlayer;
