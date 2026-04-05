import { useEffect, useRef } from 'react';
import videojs from 'video.js';
import Player from 'video.js/dist/types/player';

/**
 * An interface for all the event callbacks that Video.js can handle.
 * Note: Only onReady receives the player instance.
 */
export interface VideoJSEventCallbacks {
  onReady?: (player: Player) => void;
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
}

/**
 * The props for the useVideoJS hook.
 */
interface UseVideoJSOptions {
  videoNodeRef: React.RefObject<HTMLDivElement>;
  options: any; // Standard video.js options
  callbacks: VideoJSEventCallbacks;
}

export const useVideoJS = ({ videoNodeRef, options, callbacks }: UseVideoJSOptions) => {
  const playerRef = useRef<Player | null>(null);
  const savedCallbacks = useRef<VideoJSEventCallbacks>(callbacks);

  // Update the saved callbacks ref on every render.
  useEffect(() => {
    savedCallbacks.current = callbacks;
  }, [callbacks]);

  useEffect(() => {
    // When options are null, we do nothing.
    if (!options) {
      return;
    }

    if (!videoNodeRef.current) {
      return;
    }

    const videoElement = document.createElement('video-js');
    videoElement.classList.add('vjs-big-play-centered');
    
    if (videoNodeRef.current) {
        videoNodeRef.current.innerHTML = '';
        videoNodeRef.current.appendChild(videoElement);
    }

    const player = videojs(videoElement, options, function(this: Player) {
      playerRef.current = this;
      
      // --- Event Listeners ---
      // We use the savedCallbacks ref to ensure we always have the latest callbacks
      // without re-triggering the useEffect hook.
      this.on('play', () => savedCallbacks.current.onPlay?.());
      this.on('pause', () => savedCallbacks.current.onPause?.());
      this.on('ended', () => savedCallbacks.current.onEnded?.());
      this.on('loadstart', () => savedCallbacks.current.onLoadStart?.());
      this.on('loadeddata', () => savedCallbacks.current.onLoadedData?.());
      this.on('canplay', () => savedCallbacks.current.onCanPlay?.());
      this.on('seeking', () => savedCallbacks.current.onSeeking?.());
      this.on('seeked', () => savedCallbacks.current.onSeeked?.());
      this.on('timeupdate', () => savedCallbacks.current.onTimeUpdate?.(this.currentTime() || 0));
      this.on('durationchange', () => savedCallbacks.current.onDurationChange?.(this.duration() || 0));
      this.on('volumechange', () => savedCallbacks.current.onVolumeChange?.(this.volume() || 0));
      this.on('error', () => savedCallbacks.current.onError?.(this.error()));

      savedCallbacks.current.onReady?.(this);
    });

    return () => {
      if (playerRef.current && !playerRef.current.isDisposed()) {
        try {
          playerRef.current.dispose();
          playerRef.current = null;
        } catch (error) {
          console.error('Error disposing video.js player:', error);
        }
      }
    };
  // The effect only re-runs if the video node ref or the stringified options change.
  }, [videoNodeRef, JSON.stringify(options)]);

  return playerRef;
};