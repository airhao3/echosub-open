
export const getVideoType = (src: string): string => {
  if (!src) return 'video/mp4';

  // 提取URL路径中的扩展名，忽略查询参数
  const pathname = src.split('?')[0];
  const extension = pathname.split('.').pop()?.toLowerCase();

  switch (extension) {
    case 'mp4':
      return 'video/mp4';
    case 'webm':
      return 'video/webm';
    case 'ogg':
      return 'video/ogg';
    case 'm3u8':
      return 'application/x-mpegURL';
    case 'mpd':
      return 'application/dash+xml';
    default:
      // 对于没有明确扩展名或无法识别的，返回一个通用类型，
      // Video.js 通常也能处理或自动检测。
      return 'video/mp4';
  }
};
