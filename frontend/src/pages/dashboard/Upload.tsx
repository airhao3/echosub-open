import React, { useState, useCallback, useEffect } from 'react';
import { getSourceLanguages, getTargetLanguages, SupportedLanguage } from '../../services/api/languageService';
import { API_BASE_URL, API_PREFIX } from '../../services/api/apiClient';
import { useDropzone } from 'react-dropzone';
import { 
  Box, 
  Typography, 
  Button, 
  TextField, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem, 
  Grid,
  CircularProgress,
  SelectChangeEvent,
  Alert,
  FormControlLabel,
  Checkbox,
  Tabs,
  Tab,
  InputAdornment,
  Container,
  useTheme,
  alpha,
  Card,
  CardContent,
  Chip,
  FormHelperText,
} from '@mui/material';
import { 
  Link as LinkIcon,
  CloudUpload as UploadIcon, 
  VideoLibrary as VideoLibraryIcon,
  Language as LanguageIcon,
  Info as InfoIcon,
  Movie as MovieIcon,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';

// Styled Components for enhanced visual design
const StyledCard = styled(Card)(({ theme }) => ({
  borderRadius: '20px',
  background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(255,255,255,0.85))',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(255,255,255,0.3)',
  overflow: 'hidden',
  boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
  position: 'relative',
  '&:hover': {
    
    boxShadow: '0 12px 40px rgba(0,0,0,0.15)',
  },
  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(theme.palette.secondary.main, 0.05)} 100%)`,
    opacity: 0.6,
    transition: 'opacity 0.3s ease',
    zIndex: 0,
  },
}));

const GradientCard = styled(Card)(({ theme }) => ({
  borderRadius: '24px',
  background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
  color: 'white',
  overflow: 'hidden',
  position: 'relative',
  boxShadow: `0 20px 60px ${alpha(theme.palette.primary.main, 0.3)}`,
  '&::before': {
    content: '""',
    position: 'absolute',
    top: '-50%',
    right: '-50%',
    width: '200%',
    height: '200%',
    background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
    zIndex: 0,
  },
}));

const UploadZone = styled(Box)(({ theme }) => ({
  border: `2px dashed ${alpha(theme.palette.primary.main, 0.3)}`,
  borderRadius: '20px',
  background: `linear-gradient(145deg, ${alpha(theme.palette.primary.main, 0.02)}, ${alpha(theme.palette.secondary.main, 0.02)})`,
  backdropFilter: 'blur(10px)',
  cursor: 'pointer',
  position: 'relative',
  overflow: 'hidden',
  '&:hover': {
    borderColor: theme.palette.primary.main,
    background: `linear-gradient(145deg, ${alpha(theme.palette.primary.main, 0.08)}, ${alpha(theme.palette.secondary.main, 0.08)})`,
    
    boxShadow: `0 10px 30px ${alpha(theme.palette.primary.main, 0.15)}`,
  },
  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: '-100%',
    width: '100%',
    height: '100%',
    background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.1)}, transparent)`,
    transition: 'left 0.5s ease',
  },
  '&:hover::before': {
    left: '100%',
  },
}));

const SectionCard = styled(Card)(({ theme }) => ({
  borderRadius: '16px',
  background: alpha(theme.palette.background.paper, 0.8),
  backdropFilter: 'blur(10px)',
  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
  boxShadow: theme.customShadows?.card || '0 4px 6px rgba(0,0,0,0.05)',
  position: 'relative',
  zIndex: 1,
}));


const Upload: React.FC = () => {
  console.log('🚀 [Upload Component] Component is loading - MODIFIED VERSION');
  const theme = useTheme();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [isUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file');
  
  const [sourceLanguages, setSourceLanguages] = useState<SupportedLanguage[]>([]);
  const [targetLanguages, setTargetLanguages] = useState<SupportedLanguage[]>([]);
  
  // Animation trigger
  useEffect(() => {
  }, []);

  // Load languages from API
  useEffect(() => {
    const fetchLanguages = async () => {
      // Define fallback languages at the top
      const fallbackSource = [
        {"code": "auto", "name": "自动检测"},
        {"code": "en", "name": "英语"},
        {"code": "zh", "name": "中文"},
        {"code": "es", "name": "西班牙语"},
        {"code": "fr", "name": "法语"},
        {"code": "de", "name": "德语"}
      ];
      const fallbackTarget = [
        {"code": "zh", "name": "中文"},
        {"code": "en", "name": "英语"},
        {"code": "es", "name": "西班牙语"},
        {"code": "fr", "name": "法语"},
        {"code": "de", "name": "德语"},
        {"code": "ja", "name": "日语"},
        {"code": "ko", "name": "韩语"},
        {"code": "pt", "name": "葡萄牙语"},
        {"code": "ru", "name": "俄语"},
        {"code": "it", "name": "意大利语"},
        {"code": "ar", "name": "阿拉伯语"},
        {"code": "hi", "name": "印地语"},
        {"code": "nl", "name": "荷兰语"},
        {"code": "pl", "name": "波兰语"},
        {"code": "uk", "name": "乌克兰语"},
        {"code": "tr", "name": "土耳其语"},
        {"code": "sv", "name": "瑞典语"},
        {"code": "da", "name": "丹麦语"},
        {"code": "no", "name": "挪威语"},
        {"code": "fi", "name": "芬兰语"},
        {"code": "el", "name": "希腊语"},
        {"code": "cs", "name": "捷克语"},
        {"code": "hu", "name": "匈牙利语"},
        {"code": "ro", "name": "罗马尼亚语"},
        {"code": "bg", "name": "保加利亚语"},
        {"code": "hr", "name": "克罗地亚语"},
        {"code": "sk", "name": "斯洛伐克语"},
        {"code": "sl", "name": "斯洛文尼亚语"},
        {"code": "et", "name": "爱沙尼亚语"},
        {"code": "lv", "name": "拉脱维亚语"},
        {"code": "lt", "name": "立陶宛语"},
        {"code": "vi", "name": "越南语"},
        {"code": "th", "name": "泰语"},
        {"code": "id", "name": "印尼语"},
        {"code": "ms", "name": "马来语"},
        {"code": "tl", "name": "菲律宾语"},
        {"code": "bn", "name": "孟加拉语"},
        {"code": "ur", "name": "乌尔都语"},
        {"code": "ta", "name": "Tamil"},
        {"code": "te", "name": "Telugu"},
        {"code": "ml", "name": "Malayalam"},
        {"code": "kn", "name": "Kannada"},
        {"code": "gu", "name": "Gujarati"},
        {"code": "pa", "name": "Punjabi"},
        {"code": "mr", "name": "Marathi"},
        {"code": "ne", "name": "Nepali"},
        {"code": "si", "name": "Sinhala"},
        {"code": "my", "name": "Burmese"},
        {"code": "km", "name": "Khmer"},
        {"code": "lo", "name": "Lao"},
        {"code": "he", "name": "Hebrew"},
        {"code": "fa", "name": "Persian"},
        {"code": "sw", "name": "Swahili"},
        {"code": "am", "name": "Amharic"},
        {"code": "zu", "name": "Zulu"},
        {"code": "af", "name": "Afrikaans"},
        {"code": "ca", "name": "Catalan"},
        {"code": "eu", "name": "Basque"},
        {"code": "gl", "name": "Galician"},
        {"code": "is", "name": "Icelandic"},
        {"code": "mt", "name": "Maltese"},
        {"code": "cy", "name": "Welsh"},
        {"code": "ga", "name": "Irish"},
        {"code": "mk", "name": "Macedonian"},
        {"code": "sq", "name": "Albanian"},
        {"code": "be", "name": "Belarusian"},
        {"code": "kk", "name": "Kazakh"},
        {"code": "ky", "name": "Kyrgyz"},
        {"code": "uz", "name": "Uzbek"},
        {"code": "az", "name": "Azerbaijani"},
        {"code": "hy", "name": "Armenian"},
        {"code": "ka", "name": "Georgian"},
        {"code": "mn", "name": "Mongolian"}
      ];

      try {
        console.log('[Upload Component] 🚀 Loading languages...');
        console.log('[Upload Component] 🌐 Testing API connection to:', `${API_BASE_URL}${API_PREFIX}/languages/target`);
        
        // Test if backend is running first
        const testResponse = await fetch(`${API_BASE_URL}${API_PREFIX}/health`).catch(e => {
          console.log('[Upload Component] ⚠️ Backend health check failed:', e.message);
          return null;
        });
        
        if (testResponse) {
          console.log('[Upload Component] ✅ Backend is running, health check passed');
        } else {
          console.log('[Upload Component] ❌ Backend is not running, will use fallback');
          throw new Error('Backend not available');
        }
        
        const [sourceLangs, targetLangs] = await Promise.all([
          getSourceLanguages(),
          getTargetLanguages(),
        ]);
        console.log('[Upload Component] ✅ API Response - Source:', sourceLangs?.length || 0, 'Target:', targetLangs?.length || 0);
        
        // Use API response if valid, otherwise use fallback
        if (Array.isArray(sourceLangs) && sourceLangs.length > 0) {
          console.log('[Upload Component] ✅ API call successful for Source languages. Count:', sourceLangs.length);
          setSourceLanguages(sourceLangs);
        } else {
          console.log('🔄 Using fallback source languages');
          setSourceLanguages(fallbackSource);
        }
        
        if (Array.isArray(targetLangs) && targetLangs.length > 0) {
          console.log('[Upload Component] ✅ API call successful for Target languages. Count:', targetLangs.length);
          setTargetLanguages(targetLangs);
        } else {
          console.log('🔄 Using fallback target languages');
          setTargetLanguages(fallbackTarget);
        }
      } catch (error) {
        console.error('[Upload Component] ❌ Failed to fetch languages:', error);
        
        // Log detailed error information
        if (error instanceof Error) {
          console.error('[Upload Component] Error message:', error.message);
          console.error('[Upload Component] Error stack:', error.stack);
        }
        
        // Check if it's a network error
        if (error && typeof error === 'object' && 'response' in error) {
          const axiosError = error as any;
          console.error('[Upload Component] HTTP Status:', axiosError.response?.status);
          console.error('[Upload Component] HTTP Response:', axiosError.response?.data);
          console.error('[Upload Component] Request URL:', axiosError.config?.url);
        }
        
        console.log('[Upload Component] 🔄 Using fallback language lists');
        setSourceLanguages(fallbackSource);
        setTargetLanguages(fallbackTarget);
      }
    };
    fetchLanguages();
  }, []);

  // Debug log when uploadMethod changes
  useEffect(() => {
    console.log('uploadMethod changed to:', uploadMethod);
    // Force re-render when component mounts
    console.log('Component mounted with uploadMethod:', uploadMethod);
  }, [uploadMethod]);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    source_language: 'auto', // Default to Auto Detect
    target_languages: ['zh'], // Default to Chinese
    generate_subtitles: true,
  });


  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles && acceptedFiles.length > 0) {
      const currentFile = acceptedFiles[0];
      setFile(currentFile);
      if (!formData.title) {
        const fileName = currentFile.name;
        const lastDot = fileName.lastIndexOf('.');
        const baseName = lastDot > -1 ? fileName.substring(0, lastDot) : fileName;
        setFormData(prev => ({ ...prev, title: baseName }));
      }
    }
  }, [formData.title]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv']
    },
    maxFiles: 1,
    multiple: false
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    const checked = (e.target as HTMLInputElement).checked;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleLanguageChange = (event: SelectChangeEvent<string[]>) => {
    const { target: { value } } = event;
    setFormData(prev => ({
        ...prev,
        target_languages: typeof value === 'string' ? value.split(',') : value,
    }));
  };
  
  const handleSourceLanguageChange = (event: SelectChangeEvent) => {
    setFormData(prev => ({
        ...prev,
        source_language: event.target.value,
    }));
  };

  const handleTargetLanguageChange = (event: SelectChangeEvent<string[]>) => {
    const { target: { value } } = event;
    setFormData(prev => ({
        ...prev,
        target_languages: typeof value === 'string' ? value.split(',') : value,
    }));
  };


  const validateUrl = (url: string): boolean => {
    try {
      const urlObj = new URL(url);
      return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch (e) {
      return false;
    }
  };

  // Define the pending upload type outside the function to avoid redeclaration
  interface PendingUpload {
    file: File | null;
    videoUrl: string | null;
    fileUrl?: string;
    formData: any;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // Validate either file or URL is provided
    if (uploadMethod === 'file' && !file) {
      setError('请选择要上传的视频文件');
      return;
    }
    
    if (uploadMethod === 'url' && !videoUrl.trim()) {
      setError('请输入有效的视频链接');
      return;
    }
    
    if (uploadMethod === 'url' && !validateUrl(videoUrl)) {
      setError('请输入有效的链接（须包含 http:// 或 https://）');
      return;
    }
    
    // Validate target languages
    if (!formData.target_languages || formData.target_languages.length === 0) {
      setError('请选择至少一种目标语言');
      return;
    }
    
    // Prepare the data for upload
    const jobData = {
      ...formData,
      target_languages: formData.target_languages.join(','),
      source_type: uploadMethod === 'file' ? 'file' : 'url',
      source_url: uploadMethod === 'url' ? videoUrl : undefined
    };
  
    // Create a properly typed pending upload object
    const pendingUpload: PendingUpload = {
      file: uploadMethod === 'file' ? file : null,
      videoUrl: uploadMethod === 'url' ? videoUrl : null,
      formData: jobData,
      fileUrl: undefined
    };

    // If it's a file upload, create a temporary URL for the file
    if (uploadMethod === 'file' && file) {
      pendingUpload.fileUrl = URL.createObjectURL(file);
    }

    // Navigate to the job processing page with the pending upload
    const tempJobId = 'new';
    navigate(`/dashboard/job-processing/${tempJobId}`, { 
      state: { 
        pendingUpload: pendingUpload
      },
      replace: true
    });
  };

  return (
    <Box
      sx={{
        background: theme.palette.background.default,
        minHeight: 'calc(100vh - 64px)',
        pb: 2,
        position: 'relative',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 50%)',
          zIndex: 0,
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          top: '15%',
          right: '8%',
          width: '180px',
          height: '180px',
          borderRadius: '50%',
          background: `conic-gradient(from 0deg, 
            ${alpha(theme.palette.primary.main, 0.12)} 0deg,
            ${alpha(theme.palette.secondary.main, 0.08)} 90deg,
            ${alpha(theme.palette.primary.light, 0.06)} 180deg,
            ${alpha(theme.palette.secondary.light, 0.1)} 270deg,
            ${alpha(theme.palette.primary.main, 0.12)} 360deg
          )`,
          zIndex: 0,
        },
      }}
    >
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
        
          <Box pt={2} pb={1}>
            {/* Header Section */}
            <Box mb={2}>
              
                <Box>
                  <Typography 
                    variant="h3" 
                    component="h1" 
                    gutterBottom
                    sx={{
                      fontWeight: 700,
                      color: 'text.primary',
                      mb: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 2,
                    }}
                  >
                    <VideoLibraryIcon sx={{ fontSize: 36, color: 'primary.main' }} />
                    新建视频任务
                  </Typography>
                  <Typography
                    variant="body1"
                    sx={{
                      mb: 2,
                      color: 'text.secondary',
                      textAlign: 'center'
                    }}
                  >
                    AI 驱动的视频翻译与字幕生成
                  </Typography>
                </Box>
              
            </Box>

          {error && (
              <Alert
                severity="error"
                sx={{ mb: 2, borderRadius: '12px' }}
              >
                {error}
              </Alert>
          )}

          <StyledCard sx={{ mb: 2, backgroundColor: 'rgba(255, 255, 255, 0.95)', backdropFilter: 'blur(10px)' }}>
            <CardContent sx={{ p: 3, position: 'relative', zIndex: 1 }}>
              <form onSubmit={handleSubmit}>
                <Grid container spacing={3}>
                  {/* Upload Section - Moved to top for better UX */}
                  <Grid item xs={12}>
                    
                      <SectionCard sx={{ p: 3 }}>
                        <Box display="flex" alignItems="center" mb={3}>
                          <UploadIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                          <Typography variant="h5" fontWeight={600}>
                            上传视频
                          </Typography>
                        </Box>
                        
                        <UploadZone {...getRootProps()}>
                          <input {...getInputProps()} />
                            {file ? (
                              <>
                                <Box textAlign="center">
                                  <Box display="flex" alignItems="center" justifyContent="center" mb={2}>
                                    <MovieIcon 
                                      sx={{ 
                                        fontSize: 48, 
                                        mr: 2, 
                                        color: 'primary.main',
                                        filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.1))'
                                      }} 
                                    />
                                    <Box textAlign="left">
                                      <Typography variant="h6" fontWeight={600}>
                                        {file.name}
                                      </Typography>
                                      <Typography variant="body2" color="text.secondary">
                                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                                      </Typography>
                                    </Box>
                                  </Box>
                                  <Typography variant="body2" color="success.main" fontWeight={500}>
                                    ✓ File ready for processing
                                  </Typography>
                                </Box>
                              </>
                            ) : (
                              <Box textAlign="center">
                                <UploadIcon 
                                  sx={{ 
                                    fontSize: 64, 
                                    mb: 2, 
                                    color: 'primary.main',
                                    opacity: 0.8,
                                    filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.1))'
                                  }} 
                                />
                                <Typography variant="h5" fontWeight={600} gutterBottom>
                                  拖拽或点击上传
                                </Typography>
                                <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
                                  支持格式: MP4, MOV, AVI, MKV, WebM
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  Maximum size: 500 MB
                                </Typography>
                              </Box>
                            )}
                        </UploadZone>
                      </SectionCard>
                    
                  </Grid>

                  {/* Basic Information & Language Configuration - Combined */}
                  <Grid item xs={12}>
                    
                      <SectionCard sx={{ p: 3 }}>
                        <Grid container spacing={2}>
                          {/* Basic Information */}
                          <Grid item xs={12} md={6}>
                            <Box display="flex" alignItems="center" mb={3}>
                              <InfoIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                              <Typography variant="h5" fontWeight={600}>
                                Basic Information
                              </Typography>
                            </Box>
                            <Grid container spacing={2}>
                              <Grid item xs={12}>
                                <TextField
                                  fullWidth
                                  required
                                  size="small"
                                  label="任务标题"
                                  name="title"
                                  value={formData.title}
                                  onChange={handleInputChange}
                                  placeholder="输入任务标题"
                                  sx={{ 
                                    '& .MuiOutlinedInput-root': {
                                      borderRadius: '8px',
                                    }
                                  }}
                                />
                              </Grid>
                              <Grid item xs={12}>
                                <TextField
                                  fullWidth
                                  size="small"
                                  label="描述（可选）"
                                  name="description"
                                  value={formData.description}
                                  onChange={handleInputChange}
                                  multiline
                                  rows={2}
                                  placeholder="输入简要描述"
                                  sx={{ 
                                    '& .MuiOutlinedInput-root': {
                                      borderRadius: '8px',
                                    }
                                  }}
                                />
                              </Grid>
                            </Grid>
                          </Grid>
                          
                          {/* Language Configuration */}
                          <Grid item xs={12} md={6}>
                            <Box display="flex" alignItems="center" mb={3}>
                              <LanguageIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                              <Typography variant="h5" fontWeight={600}>
                                Language Configuration
                              </Typography>
                            </Box>
                            <Grid container spacing={2}>
                              <Grid item xs={12}>
                                <FormControl fullWidth required size="small">
                                  <InputLabel>源语言</InputLabel>
                                  <Select
                                    name="source_language"
                                    value={formData.source_language}
                                    label="源语言"
                                    onChange={handleSourceLanguageChange}
                                    sx={{ 
                                      '& .MuiOutlinedInput-root': {
                                        borderRadius: '8px',
                                      }
                                    }}
                                  >
                                    {sourceLanguages.map((lang) => (
                                      <MenuItem key={lang.code} value={lang.code}>
                                        {lang.name}
                                      </MenuItem>
                                    ))}
                                  </Select>
                                </FormControl>
                              </Grid>
                              <Grid item xs={12}>
                                <FormControl fullWidth required size="small">
                                  <InputLabel>目标语言</InputLabel>
                                  <Select
                                    name="target_languages"
                                    multiple
                                    value={formData.target_languages || []}
                                    label="目标语言"
                                    onChange={handleTargetLanguageChange}
                                    renderValue={(selected) => (
                                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {selected.map((value) => (
                                          <Chip 
                                            key={value} 
                                            label={targetLanguages.find(l => l.code === value)?.name || value}
                                            size="small"
                                          />
                                        ))}
                                      </Box>
                                    )}
                                    sx={{ 
                                      '& .MuiOutlinedInput-root': {
                                        borderRadius: '8px',
                                      }
                                    }}
                                  >
                                    {targetLanguages.filter(lang => lang.code !== 'auto' && lang.code !== formData.source_language).map((lang) => (
                                      <MenuItem key={lang.code} value={lang.code}>
                                        {lang.name}
                                      </MenuItem>
                                    ))}
                                  </Select>
                                  {formData.target_languages && formData.target_languages.length > 0 && (
                                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                      已选 {formData.target_languages.length} 种语言
                                    </Typography>
                                  )}
                                </FormControl>
                              </Grid>
                            </Grid>
                          </Grid>
                        </Grid>
                      </SectionCard>
                    
                  </Grid>

                  {/* Processing Options - Simplified */}
                  <Grid item xs={12}>
                    
                      <SectionCard sx={{ p: 3 }}>
                        <Box display="flex" alignItems="center" justifyContent="space-between">
                          <Box display="flex" alignItems="center">
                            <VideoLibraryIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                            <Typography variant="h5" fontWeight={600}>
                              Processing Options
                            </Typography>
                          </Box>
                          <FormControlLabel
                            control={
                              <Checkbox 
                                checked={formData.generate_subtitles} 
                                onChange={handleInputChange} 
                                name="generate_subtitles" 
                                color="primary"
                                size="small"
                              />
                            }
                            label={
                              <Typography variant="body2" fontWeight={500}>
                                生成字幕
                              </Typography>
                            }
                          />
                        </Box>
                      </SectionCard>
                    
                  </Grid>

                  {/* Submit Button */}
                  <Grid item xs={12}>
                    
                      <Box textAlign="center" mt={1}>
                        <Button
                          type="submit"
                          variant="contained"
                          size="large"
                          disabled={!file || !formData.title || formData.target_languages.length === 0 || isUploading}
                          startIcon={isUploading ? <CircularProgress size={18} color="inherit" /> : <VideoLibraryIcon />}
                          sx={{
                            px: 4,
                            py: 1.5,
                            borderRadius: '12px',
                            fontSize: '1rem',
                            fontWeight: 600,
                            minWidth: 180,
                            background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                            boxShadow: `0 4px 12px ${alpha(theme.palette.primary.main, 0.3)}`,
                            '&:hover': {
                              background: `linear-gradient(135deg, ${theme.palette.primary.dark} 0%, ${theme.palette.secondary.main} 100%)`,
                              boxShadow: `0 6px 16px ${alpha(theme.palette.primary.main, 0.4)}`,
                              
                            },
                            '&:disabled': {
                              background: theme.palette.action.disabledBackground,
                              color: theme.palette.action.disabled,
                            },
                          }}
                        >
                          {isUploading ? '创建中...' : '创建视频任务'}
                        </Button>
                      </Box>
                    
                  </Grid>
                </Grid>
              </form>
            </CardContent>
          </StyledCard>
          </Box>
        
      </Container>
    </Box>
  );
};

export default Upload;
