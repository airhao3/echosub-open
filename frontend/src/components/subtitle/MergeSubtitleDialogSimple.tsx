import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
} from '@mui/material';

interface MergeSubtitleDialogProps {
  open: boolean;
  currentSubtitle: {
    id: string;
    text: string;
    startTime: number;
    endTime: number;
  } | null;
  nextSubtitle: {
    id: string;
    text: string;
    startTime: number;
    endTime: number;
  } | null;
  onClose: () => void;
  onMerge: (mergedText: string, newEndTime: number, deleteSubtitleId: string) => void;
  onSeekTo: (time: number) => void;
}

const MergeSubtitleDialogSimple: React.FC<MergeSubtitleDialogProps> = ({
  open,
  currentSubtitle,
  nextSubtitle,
  onClose,
  onMerge,
}) => {
  // 格式化时间显示
  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    const milliseconds = Math.floor((timeInSeconds % 1) * 1000);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  const handleMerge = () => {
    if (!currentSubtitle || !nextSubtitle) return;
    
    const mergedText = currentSubtitle.text + ' ' + nextSubtitle.text;
    onMerge(mergedText, nextSubtitle.endTime, nextSubtitle.id);
    onClose();
  };

  if (!currentSubtitle || !nextSubtitle) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>合并字幕</DialogTitle>
      <DialogContent sx={{ pt: 2 }}>
        {/* 当前字幕 */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          第一条字幕
        </Typography>
        <Typography variant="body1" sx={{ mb: 1, p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
          {currentSubtitle.text}
        </Typography>
        <Typography variant="caption" sx={{ mb: 3, color: 'text.secondary', display: 'block' }}>
          时间范围: {formatTime(currentSubtitle.startTime)} - {formatTime(currentSubtitle.endTime)}
        </Typography>

        {/* 下一条字幕 */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          第二条字幕
        </Typography>
        <Typography variant="body1" sx={{ mb: 1, p: 2, bgcolor: 'secondary.light', borderRadius: 1 }}>
          {nextSubtitle.text}
        </Typography>
        <Typography variant="caption" sx={{ mb: 3, color: 'text.secondary', display: 'block' }}>
          时间范围: {formatTime(nextSubtitle.startTime)} - {formatTime(nextSubtitle.endTime)}
        </Typography>

        {/* 合并预览 */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          合并后
        </Typography>
        <Typography variant="body1" sx={{ mb: 1, p: 2, bgcolor: 'success.light', borderRadius: 1, fontWeight: 'bold' }}>
          {currentSubtitle.text + ' ' + nextSubtitle.text}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          合并后时间范围: {formatTime(currentSubtitle.startTime)} - {formatTime(nextSubtitle.endTime)}
        </Typography>
        <Typography variant="caption" sx={{ color: 'success.main', display: 'block', mt: 1 }}>
          ✓ 时间轴将自动合并，删除第二条字幕的独立时间段
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button onClick={handleMerge} variant="contained">确认合并</Button>
      </DialogActions>
    </Dialog>
  );
};

export default MergeSubtitleDialogSimple;