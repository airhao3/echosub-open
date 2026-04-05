/**
 * Defines the structure for a single subtitle entry.
 */
export interface Subtitle {
  id: string;
  startTime: number;
  endTime: number;
  text: string;
  isEditing?: boolean;
}

/**
 * Formats a duration in seconds into a VTT timestamp string (HH:MM:SS.mmm).
 * @param seconds The duration in seconds.
 * @returns The formatted VTT timestamp.
 */
export const formatTime = (seconds: number): string => {
  const pad = (num: number, size: number) => num.toString().padStart(size, '0');

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);

  return `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(secs, 2)}.${pad(ms, 3)}`;
};

/**
 * Parses a VTT timestamp string (HH:MM:SS.mmm) into seconds.
 * @param timeStr The VTT timestamp string.
 * @returns The time in seconds.
 */
export const parseTime = (timeStr: string): number => {
  // Normalize comma to period for milliseconds
  const normalizedTimeStr = timeStr.replace(',', '.');
  
  // Regex to match HH:MM:SS.mmm or MM:SS.mmm
  const match = normalizedTimeStr.match(/(?:(\d+):)?(\d+):(\d+)[,.](\d+)/);
  if (!match) return 0;

  const hours = parseInt(match[1], 10) || 0;
  const minutes = parseInt(match[2], 10);
  const seconds = parseInt(match[3], 10);
  const milliseconds = parseInt(match[4], 10);

  return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000;
};
