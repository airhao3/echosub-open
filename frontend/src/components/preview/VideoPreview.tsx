import * as React from 'react';
import { useState, useEffect } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import { Tabs, Tab, Divider } from '@mui/material';
import LightweightVideoPlayer from '../player/LightweightVideoPlayer';
import { getJobDetails } from '../../services/api/jobService';

interface VideoPreviewProps {
  jobId: number;
  jobTitle?: string;
  languages?: string[];
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`video-tabpanel-${index}`}
      aria-labelledby={`video-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function VideoPreview(props: VideoPreviewProps) {
  const { jobId, jobTitle, languages = [] } = props;
  const [tabValue, setTabValue] = useState(0);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available languages from job details
  useEffect(() => {
    const fetchJobDetails = async () => {
      try {
        setLoading(true);
        const jobDetails = await getJobDetails(jobId);
        
        // Extract available languages from job results or use provided languages
        const detectedLanguages = languages.length > 0 ? languages : ['zh'];
        setAvailableLanguages(detectedLanguages);
        
      } catch (err: any) {
        console.error('Failed to fetch job details:', err);
        setError('无法获取任务详情');
      } finally {
        setLoading(false);
      }
    };

    fetchJobDetails();
  }, [jobId, languages]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleLanguageChange = (language: string) => {
    console.log(`Language changed to: ${language}`);
  };

  if (loading) {
    return (
      <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={32} />
        <Typography variant="body2" sx={{ mt: 2 }}>
          Loading video preview...
        </Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper elevation={1} sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper elevation={1} sx={{ p: 0 }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="video preview tabs">
          <Tab label="视频预览" id="video-tab-0" aria-controls="video-tabpanel-0" />
          <Tab label="API链接" id="video-tab-1" aria-controls="video-tabpanel-1" />
        </Tabs>
      </Box>

      {/* Video Player Tab */}
      <TabPanel value={tabValue} index={0}>
        <LightweightVideoPlayer
          jobId={jobId}
          title={jobTitle}
          availableLanguages={availableLanguages}
          onLanguageChange={handleLanguageChange}
        />
      </TabPanel>

      {/* API Links Tab */}
      <TabPanel value={tabValue} index={1}>
        <Typography variant="h6" gutterBottom>API接口链接 (ID: {jobId})</Typography>
        
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Original Video */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>原始视频流</Typography>
            <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
              <code style={{ fontSize: '0.875rem', wordBreak: 'break-all' }}>
                {`/api/v1/preview/video/${jobId}`}
              </code>
            </Box>
          </Box>
          
          {/* VTT Subtitles */}
          {availableLanguages.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>字幕文件 (VTT格式)</Typography>
              {availableLanguages.map((lang) => (
                <Box key={lang} sx={{ mb: 1, p: 1.5, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
                  <Typography variant="caption" sx={{ display: 'block', mb: 0.5, color: 'text.secondary' }}>
                    {lang === 'zh' ? '中文' : lang.toUpperCase()}
                  </Typography>
                  <code style={{ fontSize: '0.875rem', wordBreak: 'break-all' }}>
                    {`/api/v1/downloads/results/${jobId}/subtitles?format=vtt&language=${lang}`}
                  </code>
                </Box>
              ))}
            </Box>
          )}

          {/* Download Original Video */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>下载原始视频</Typography>
            <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
              <code style={{ fontSize: '0.875rem', wordBreak: 'break-all' }}>
                {`/api/v1/downloads/results/${jobId}/video`}
              </code>
            </Box>
          </Box>

          <Divider sx={{ my: 2 }} />

          {/* Usage Instructions */}
          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>云端处理模式说明</Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              当前系统运行在云端处理模式下，提供高效的视频处理和智能字幕生成服务。
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              • 高效云端计算处理<br />
              • 智能字幕生成技术<br />
              • 支持多语言字幕切换<br />
              • 专业级视频处理服务
            </Typography>
          </Box>
        </Box>
      </TabPanel>
    </Paper>
  );
}

export default VideoPreview;
