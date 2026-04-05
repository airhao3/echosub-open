import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import {
  Box,
  Typography,
  TextField,
  Button,
  Grid,
  FormControlLabel,
  Switch,
  MenuItem,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Container,
  Fade,
  Slide,
  useTheme,
  alpha,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  OutlinedInput,
  Chip,
  FormHelperText,
} from '@mui/material';
import { 
  ArrowBack as ArrowBackIcon, 
  Upload as UploadIcon, 
  Movie as MovieIcon, 
  Info as InfoIcon,
  VideoLibrary as VideoLibraryIcon,
  Language as LanguageIcon,
  Settings as SettingsIcon,
  Subtitles as SubtitlesIcon,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { useDropzone } from 'react-dropzone';

import { createJob, JobCreationResponse, reprocessJob } from '../../services/api/jobService';
import { getSourceLanguages, getTargetLanguages, SupportedLanguage } from '../../services/api/languageService';
import SubtitleLanguageSelector from '../../components/jobs/SubtitleLanguageSelector';
import SubtitleStyleEditor from '../../components/jobs/SubtitleStyleEditor';

// 5MB in bytes
const FILE_SIZE_LIMIT = 500 * 1024 * 1024;

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
    transform: 'translateY(-2px)',
    boxShadow: '0 12px 40px rgba(0,0,0,0.15)',
  },
  transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
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
    animation: 'float 6s ease-in-out infinite',
    zIndex: 0,
  },
  '@keyframes float': {
    '0%, 100%': { transform: 'translate(0, 0) rotate(0deg)' },
    '33%': { transform: 'translate(30px, -30px) rotate(120deg)' },
    '66%': { transform: 'translate(-20px, 20px) rotate(240deg)' },
  },
}));

const UploadZone = styled(Box)(({ theme }) => ({
  border: `2px dashed ${alpha(theme.palette.primary.main, 0.3)}`,
  borderRadius: '20px',
  background: `linear-gradient(145deg, ${alpha(theme.palette.primary.main, 0.02)}, ${alpha(theme.palette.secondary.main, 0.02)})`,
  backdropFilter: 'blur(10px)',
  transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
  cursor: 'pointer',
  position: 'relative',
  overflow: 'hidden',
  '&:hover': {
    borderColor: theme.palette.primary.main,
    background: `linear-gradient(145deg, ${alpha(theme.palette.primary.main, 0.08)}, ${alpha(theme.palette.secondary.main, 0.08)})`,
    transform: 'translateY(-2px)',
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
  transition: 'all 0.3s ease',
  position: 'relative',
  zIndex: 1,
}));

// Validation schema
const validationSchema = Yup.object({
  title: Yup.string().required('Title is required'),
  description: Yup.string(),
  source_language: Yup.string().required('Source language is required'),
  target_languages: Yup.array().of(Yup.string()).min(1, 'At least one target language is required').required('Target language is required'),
  generate_subtitles: Yup.boolean(),
  generate_dubbing: Yup.boolean(),
  subtitle_languages: Yup.array().when('generate_subtitles', {
    is: true,
    then: (schema) => schema.min(1, 'Select at least one subtitle language'),
  }),
  video_format: Yup.string(),
  resolution: Yup.string(),
  subtitle_style: Yup.string().test(
    'is-json',
    'Subtitle style must be a valid JSON object',
    (value) => {
      if (!value) return true;
      try {
        JSON.parse(value);
      } catch (e) {
        return false;
      }
      return true;
    }
  ),
});

const NewJob: React.FC = () => {
  console.log('[NewJob Component] 🚀 Component rendering...');
  const navigate = useNavigate();
  const theme = useTheme();
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateResponse, setDuplicateResponse] = useState<JobCreationResponse | null>(null);
  const [slideIn, setSlideIn] = useState(false);
  const [sourceLanguages, setSourceLanguages] = useState<SupportedLanguage[]>([]);
  const [targetLanguages, setTargetLanguages] = useState<SupportedLanguage[]>([]);
  const [availableSubtitleLanguages, setAvailableSubtitleLanguages] = useState<SupportedLanguage[]>([]);

  // Animation trigger
  React.useEffect(() => {
    setSlideIn(true);
  }, []);

  // Fetch languages from API on component mount
  React.useEffect(() => {
    const fetchLanguages = async () => {
      // Define comprehensive language lists
      const fallbackTargetLanguages = [
        {"code": "en", "name": "English"},
        {"code": "zh", "name": "Chinese (Simplified)"},
        {"code": "zh-TW", "name": "Chinese (Traditional)"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "ru", "name": "Russian"},
        {"code": "it", "name": "Italian"},
        {"code": "ar", "name": "Arabic"},
        {"code": "hi", "name": "Hindi"},
        {"code": "nl", "name": "Dutch"},
        {"code": "pl", "name": "Polish"},
        {"code": "uk", "name": "Ukrainian"},
        {"code": "tr", "name": "Turkish"},
        {"code": "sv", "name": "Swedish"},
        {"code": "da", "name": "Danish"},
        {"code": "no", "name": "Norwegian"},
        {"code": "fi", "name": "Finnish"},
        {"code": "el", "name": "Greek"},
        {"code": "cs", "name": "Czech"},
        {"code": "hu", "name": "Hungarian"},
        {"code": "ro", "name": "Romanian"},
        {"code": "bg", "name": "Bulgarian"},
        {"code": "hr", "name": "Croatian"},
        {"code": "sk", "name": "Slovak"},
        {"code": "sl", "name": "Slovenian"},
        {"code": "et", "name": "Estonian"},
        {"code": "lv", "name": "Latvian"},
        {"code": "lt", "name": "Lithuanian"},
        {"code": "vi", "name": "Vietnamese"},
        {"code": "th", "name": "Thai"},
        {"code": "id", "name": "Indonesian"},
        {"code": "ms", "name": "Malay"},
        {"code": "tl", "name": "Filipino"},
        {"code": "bn", "name": "Bengali"},
        {"code": "ur", "name": "Urdu"},
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
      
      const fallbackSourceLanguages = [
        {"code": "auto", "name": "Auto Detect"},
        {"code": "en", "name": "English"},
        {"code": "zh", "name": "Chinese"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "ru", "name": "Russian"}
      ];

      console.log('[NewJob Component] Fetching languages from API...');
      try {
        const [sourceLangs, targetLangs] = await Promise.all([
          getSourceLanguages(),
          getTargetLanguages(),
        ]);
        console.log('🔍 API Response - Source languages:', sourceLangs?.length || 0, sourceLangs);
        console.log('🔍 API Response - Target languages:', targetLangs?.length || 0, targetLangs);
        
        // Use API response if valid, otherwise use fallback
        if (Array.isArray(sourceLangs) && sourceLangs.length > 0) {
          console.log('[NewJob Component] ✅ API call successful for Source languages. Count:', sourceLangs.length);
          setSourceLanguages(sourceLangs);
        } else {
          console.log('🔄 Using fallback source languages');
          setSourceLanguages(fallbackSourceLanguages);
        }
        
        if (Array.isArray(targetLangs) && targetLangs.length > 0) {
          console.log('[NewJob Component] ✅ API call successful for Target languages. Count:', targetLangs.length);
          setTargetLanguages(targetLangs);
        } else {
          console.log('🔄 Using fallback target languages');
          setTargetLanguages(fallbackTargetLanguages);
        }
      } catch (error) {
        console.error("Failed to fetch languages:", error);
        console.log("🔄 Using fallback language lists due to API error");
        setSourceLanguages(fallbackSourceLanguages);
        setTargetLanguages(fallbackTargetLanguages);
      }
      

    };
    fetchLanguages();
  }, []);

  // Dropzone configuration
  const { getRootProps, getInputProps } = useDropzone({
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    },
    maxSize: FILE_SIZE_LIMIT,
    multiple: false,
    onDropAccepted: (files) => {
      const file = files[0];
      setVideoFile(file);
      setFileError(null);
      
      if (file) {
        // Automatically set the title to the filename (without extension)
        const fileName = file.name;
        const fileNameWithoutExt = fileName.includes('.') 
          ? fileName.substring(0, fileName.lastIndexOf('.')) 
          : fileName;
        const truncatedTitle = fileNameWithoutExt.substring(0, 50);
        formik.setFieldValue('title', truncatedTitle);
      }
    },
    onDropRejected: (fileRejections) => {
      const error = fileRejections[0]?.errors[0];
      if (error) {
        if (error.code === 'file-too-large') {
          setFileError(`File is too large. Maximum size is ${FILE_SIZE_LIMIT / (1024 * 1024)} MB`);
        } else if (error.code === 'file-invalid-type') {
          setFileError('Invalid file type. Please upload a video file');
        } else {
          setFileError(error.message);
        }
      }
    }
  });
  
  const formik = useFormik({
    initialValues: {
      title: '',
      description: '',
      source_language: 'auto',
      target_languages: ['zh'],
      generate_subtitles: true,
      generate_dubbing: false,
      subtitle_languages: ['auto', 'zh'],
      video_format: 'mp4',
      resolution: '1080p',
      subtitle_style: JSON.stringify({
        "font_size": 10,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0.5)",
        "position": "bottom"
      }, null, 2),
    },
    validationSchema: validationSchema,
    onSubmit: async (values) => {
      if (!videoFile) {
        setFileError('Please upload a video file');
        return;
      }
      
      setIsSubmitting(true);
      try {
        const response = await createJob({ ...values, target_languages: values.target_languages.join(',') }, videoFile);
        console.log('Job creation response:', response);
        
        // Get job ID from response
        const jobId = response.job_id;
        
        if (jobId) {
          // Check if this is a duplicate video upload
          if (response.status === 'duplicate_completed' && response.options) {
            // Show confirmation dialog with options
            handleDuplicateVideo(response);
          } else {
            // Regular response - navigate to job processing page
            console.log(`Navigating to job processing: /dashboard/job-processing/${response.user_job_number}`);
            navigate(`/dashboard/job-processing/${response.user_job_number}`);
          }
        } else {
          console.error('Invalid job ID in response:', response);
          setFileError('Job created but received invalid ID. Please check your jobs list.');
        }
      } catch (error: any) {
        console.error('Error creating job:', error);
        setFileError(error.response?.data?.detail || 'Failed to create job. Please try again later.');
      } finally {
        setIsSubmitting(false);
      }
    },
  });
  
    // Update available subtitle languages when source or target languages change
    React.useEffect(() => {
      const sourceLanguage = sourceLanguages.find(l => l.code === formik.values.source_language);
      const selectedTargetLanguages = formik.values.target_languages
        .map(code => targetLanguages.find(l => l.code === code))
        .filter((l): l is SupportedLanguage => !!l);
  
      const newAvailableLanguages: SupportedLanguage[] = [];
  
      // Add source language if it's not auto
      if (sourceLanguage && sourceLanguage.code !== 'auto') {
        newAvailableLanguages.push({ ...sourceLanguage, isSource: true });
      } else {
        // If source is auto, add a placeholder
        newAvailableLanguages.push({ code: 'auto', name: 'Original (Auto Detected)', isSource: true });
      }
  
      // Add target languages
      selectedTargetLanguages.forEach(targetLanguage => {
        if (targetLanguage) {
          newAvailableLanguages.push(targetLanguage);
        }
      });
  
      setAvailableSubtitleLanguages(newAvailableLanguages);
  
      // Update subtitle languages if current selection contains removed languages
      const updatedSelection = formik.values.subtitle_languages.filter(
        lang => newAvailableLanguages.some(l => l.code === lang)
      );
  
      // Ensure at least one language is selected
      if (updatedSelection.length === 0 && newAvailableLanguages.length > 0) {
        updatedSelection.push(newAvailableLanguages[0].code);
      }
  
      if (JSON.stringify(updatedSelection) !== JSON.stringify(formik.values.subtitle_languages)) {
        formik.setFieldValue('subtitle_languages', updatedSelection);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [formik.values.source_language, formik.values.target_languages, sourceLanguages, targetLanguages]);
  // Function to handle duplicate video upload response
  const handleDuplicateVideo = (response: JobCreationResponse) => {
    setDuplicateResponse(response);
    setDuplicateDialogOpen(true);
  };

  // Handle user selection from the duplicate dialog
  const handleDuplicateAction = async (url: string, isReprocess: boolean) => {
    setDuplicateDialogOpen(false);
    setIsSubmitting(true);
    
    try {
      // Extract job ID from URL regardless of format
      const jobIdMatch = url.match(/\/jobs\/(\d+)/);
      
      if (jobIdMatch && jobIdMatch[1]) {
        const jobId = parseInt(jobIdMatch[1], 10);
        
        if (isReprocess) {
          // Call the reprocess endpoint
          console.log(`Calling reprocess endpoint for job ${jobId}`);
          const response = await reprocessJob(jobId);
          console.log('Reprocess response:', response);
        
        // Navigate to the job details page to show processing status
        navigate(`/dashboard/job-processing/${jobId}`);
        } else {
          // Simply navigate to the job page to view results  
          navigate(`/dashboard/jobs/${jobId}`);
        }
      } else {
        // If we couldn't extract a job ID, try to use the URL directly
        if (url.startsWith('/')) {
          // For relative URLs, use React Router navigation
          navigate(url);
        } else {
          // For complete URLs with domain, use window.location
          window.location.href = url;
        }
      }
    } catch (error) {
      console.error('Error handling duplicate action:', error);
      setFileError('Failed to process your request. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoBack = () => {
    navigate('/dashboard/jobs');
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Duplicate Video Dialog */}
      <Dialog
        open={duplicateDialogOpen}
        onClose={() => setDuplicateDialogOpen(false)}
        aria-labelledby="duplicate-video-dialog-title"
        PaperProps={{
          sx: {
            borderRadius: '20px',
            backdropFilter: 'blur(20px)',
            background: alpha(theme.palette.background.paper, 0.95),
          }
        }}
      >
        <DialogTitle id="duplicate-video-dialog-title">
          <Box display="flex" alignItems="center">
            <InfoIcon sx={{ mr: 1, color: 'info.main' }} />
            Video Already Processed
          </Box>
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {duplicateResponse?.user_prompt || 'This video has already been processed.'}
          </DialogContentText>
          <Box mt={2}>
            <Typography variant="subtitle2" color="text.secondary">
              Choose an option:
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions sx={{ padding: 2, display: 'flex', justifyContent: 'space-evenly' }}>
          {duplicateResponse?.options?.map((option, index) => (
            <Button
              key={index}
              variant={option.primary ? 'contained' : 'outlined'}
              color={option.primary ? 'primary' : 'secondary'}
              onClick={() => handleDuplicateAction(option.url, option.label === 'Reprocess Video')}
              sx={{ borderRadius: '12px' }}
            >
              {option.label}
            </Button>
          ))}
        </DialogActions>
      </Dialog>

      <Slide direction="down" in={slideIn} mountOnEnter unmountOnExit timeout={600}>
        <Box>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={handleGoBack}
            sx={{ 
              mb: 3,
              borderRadius: '12px',
              color: theme.palette.text.secondary,
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                color: theme.palette.primary.main,
              }
            }}
          >
            Back to Jobs
          </Button>
          
          {/* Header Section */}
          <Box textAlign="center" mb={4}>
            <Fade in={slideIn} timeout={800}>
              <GradientCard sx={{ p: 4, mb: 4 }}>
                <CardContent sx={{ position: 'relative', zIndex: 1 }}>
                  <VideoLibraryIcon sx={{ fontSize: 48, mb: 2, opacity: 0.9 }} />
                  <Typography variant="h3" component="h1" gutterBottom fontWeight={700}>
                    Create New Video Job
                  </Typography>
                  <Typography variant="h6" sx={{ opacity: 0.9 }}>
                    Transform your videos with AI-powered translation and subtitles
                  </Typography>
                </CardContent>
              </GradientCard>
            </Fade>
          </Box>

          <StyledCard sx={{ mb: 3 }}>
            <CardContent sx={{ p: 4, position: 'relative', zIndex: 1 }}>
              <form onSubmit={formik.handleSubmit}>
          <Grid container spacing={4}>
            {/* Upload Section */}
            <Grid item xs={12}>
              <Fade in={slideIn} timeout={1000}>
                <SectionCard sx={{ p: 3 }}>
                  <Box display="flex" alignItems="center" mb={3}>
                    <UploadIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                    <Typography variant="h5" fontWeight={600}>
                      Upload Video
                    </Typography>
                  </Box>
              
                  <UploadZone
                    sx={{ p: 4, mb: 2, textAlign: 'center' }}
                    {...getRootProps()}
                  >
                    <input {...getInputProps()} />
                    
                    {videoFile ? (
                      <Fade in timeout={500}>
                        <Box>
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
                                {videoFile.name}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                {(videoFile.size / (1024 * 1024)).toFixed(2)} MB
                              </Typography>
                            </Box>
                          </Box>
                          <Typography variant="body2" color="success.main" fontWeight={500}>
                            ✓ File ready for processing
                          </Typography>
                        </Box>
                      </Fade>
                    ) : (
                      <Box>
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
                          Drag & Drop or Click to Upload
                        </Typography>
                        <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
                          Supported formats: MP4, MOV, AVI, MKV, WebM
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Maximum size: {FILE_SIZE_LIMIT / (1024 * 1024)} MB
                        </Typography>
                      </Box>
                    )}
                  </UploadZone>
              
                  {fileError && (
                    <Alert severity="error" sx={{ mt: 2, borderRadius: '12px' }}>
                      {fileError}
                    </Alert>
                  )}
                </SectionCard>
              </Fade>
            </Grid>

            {/* Basic Info Section */}
            <Grid item xs={12}>
              <Fade in={slideIn} timeout={1200}>
                <SectionCard sx={{ p: 3 }}>
                  <Box display="flex" alignItems="center" mb={3}>
                    <InfoIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                    <Typography variant="h5" fontWeight={600}>
                      Basic Information
                    </Typography>
                  </Box>
                  
                  <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                      <TextField
                        id="title"
                        name="title"
                        label="Title"
                        value={formik.values.title}
                        onChange={formik.handleChange}
                        error={formik.touched.title && Boolean(formik.errors.title)}
                        helperText={formik.touched.title && formik.errors.title}
                        required
                        sx={{ 
                          '& .MuiOutlinedInput-root': {
                            borderRadius: '12px',
                          }
                        }}
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <TextField
                        id="description"
                        name="description"
                        label="Description (Optional)"
                        value={formik.values.description}
                        onChange={formik.handleChange}
                        error={formik.touched.description && Boolean(formik.errors.description)}
                        helperText={formik.touched.description && formik.errors.description}
                        multiline
                        rows={1}
                        sx={{ 
                          '& .MuiOutlinedInput-root': {
                            borderRadius: '12px',
                          }
                        }}
                      />
                    </Grid>
                  </Grid>
                </SectionCard>
              </Fade>
            </Grid>

            {/* Language Configuration */}
            <Grid item xs={12}>
              <Fade in={slideIn} timeout={1400}>
                <SectionCard sx={{ p: 3 }}>
                  <Box display="flex" alignItems="center" mb={3}>
                    <LanguageIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                    <Typography variant="h5" fontWeight={600}>
                      Language Configuration
                    </Typography>
                  </Box>
                  
                  <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                      <TextField
                        select
                        id="source_language"
                        name="source_language"
                        label="Source Language"
                        value={formik.values.source_language}
                        onChange={formik.handleChange}
                        error={formik.touched.source_language && Boolean(formik.errors.source_language)}
                        helperText={formik.touched.source_language && formik.errors.source_language}
                        required
                        sx={{ 
                          '& .MuiOutlinedInput-root': {
                            borderRadius: '12px',
                          }
                        }}
                      >
                        {sourceLanguages.map((lang) => (
                          <MenuItem key={lang.code} value={lang.code}>
                            {lang.name}
                          </MenuItem>
                        ))}
                      </TextField>
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControl fullWidth>
                        <InputLabel id="target-languages-label">Target Languages</InputLabel>
                        <Select
                          labelId="target-languages-label"
                          id="target_languages"
                          name="target_languages"
                          multiple
                          value={formik.values.target_languages}
                          onChange={formik.handleChange}
                          input={<OutlinedInput label="Target Languages" />}
                          renderValue={(selected) => (
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                              {selected.map((value) => (
                                <Chip key={value} label={targetLanguages.find(l => l.code === value)?.name || value} />
                              ))}
                            </Box>
                          )}
                          error={formik.touched.target_languages && Boolean(formik.errors.target_languages)}
                          sx={{ borderRadius: '12px' }}
                        >
                          {(() => {
                            console.log('[NewJob Component] 렌더링 직전 데이터:', targetLanguages);
                            const filteredLangs = targetLanguages.filter(lang => lang.code !== 'auto' && lang.code !== formik.values.source_language);
                            console.log('🎯 Rendering dropdown with', filteredLangs.length, 'languages out of', targetLanguages.length, 'total');
                            return filteredLangs.map((lang) => (
                              <MenuItem key={lang.code} value={lang.code}>
                                {lang.name}
                              </MenuItem>
                            ));
                          })()}
                        </Select>
                        {formik.touched.target_languages && formik.errors.target_languages && (
                          <FormHelperText error>{formik.errors.target_languages as string}</FormHelperText>
                        )}
                      </FormControl>
                    </Grid>
                  </Grid>
                </SectionCard>
              </Fade>
            </Grid>
            {/* Processing Options */}
            <Grid item xs={12}>
              <Fade in={slideIn} timeout={1600}>
                <SectionCard sx={{ p: 3 }}>
                  <Box display="flex" alignItems="center" mb={3}>
                    <SettingsIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                    <Typography variant="h5" fontWeight={600}>
                      Processing Options
                    </Typography>
                  </Box>
                  
                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={6}>
                      <Box 
                        sx={{ 
                          p: 2, 
                          border: '1px solid', 
                          borderColor: 'divider',
                          borderRadius: '12px',
                          transition: 'all 0.3s ease',
                          '&:hover': {
                            borderColor: 'primary.main',
                            backgroundColor: alpha(theme.palette.primary.main, 0.02),
                          }
                        }}
                      >
                        <FormControlLabel
                          control={
                            <Switch
                              checked={formik.values.generate_subtitles}
                              onChange={formik.handleChange}
                              name="generate_subtitles"
                              color="primary"
                            />
                          }
                          label={
                            <Box>
                              <Typography variant="subtitle1" fontWeight={600}>
                                Generate Subtitles
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                Create subtitle files for your video
                              </Typography>
                            </Box>
                          }
                        />
                      </Box>
                    </Grid>
                    
                    <Grid item xs={12} sm={6}>
                      <Box 
                        sx={{ 
                          p: 2, 
                          border: '1px solid', 
                          borderColor: 'divider',
                          borderRadius: '12px',
                          transition: 'all 0.3s ease',
                          '&:hover': {
                            borderColor: 'primary.main',
                            backgroundColor: alpha(theme.palette.primary.main, 0.02),
                          }
                        }}
                      >
                        <FormControlLabel
                          control={
                            <Switch
                              checked={formik.values.generate_dubbing}
                              onChange={formik.handleChange}
                              name="generate_dubbing"
                              color="primary"
                            />
                          }
                          label={
                            <Box>
                              <Typography variant="subtitle1" fontWeight={600}>
                                Generate Dubbing
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                Create dubbed audio track
                              </Typography>
                            </Box>
                          }
                        />
                      </Box>
                    </Grid>
                  </Grid>
                </SectionCard>
              </Fade>
            </Grid>
            {/* Subtitle Options */}
            {formik.values.generate_subtitles && (
              <Grid item xs={12}>
                <Fade in={slideIn} timeout={1800}>
                  <SectionCard sx={{ p: 3 }}>
                    <Box display="flex" alignItems="center" mb={3}>
                      <SubtitlesIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                      <Typography variant="h5" fontWeight={600}>
                        Subtitle Options
                      </Typography>
                    </Box>
                    
                    <SubtitleLanguageSelector
                      availableLanguages={availableSubtitleLanguages}
                      sourceLanguage={formik.values.source_language === 'auto' ? 'auto' : formik.values.source_language}
                      selectedLanguages={formik.values.subtitle_languages}
                      onChange={(languages) => formik.setFieldValue('subtitle_languages', languages)}
                      maxSelections={2}
                    />
                    
                    {formik.touched.subtitle_languages && formik.errors.subtitle_languages && (
                      <Alert severity="error" sx={{ mt: 2, borderRadius: '12px' }}>
                        {formik.errors.subtitle_languages as string}
                      </Alert>
                    )}
                  </SectionCard>
                </Fade>
              </Grid>
            )}

            {/* Video Output Options */}
            {formik.values.generate_subtitles && (
              <Grid item xs={12}>
                <Fade in={slideIn} timeout={2000}>
                  <SectionCard sx={{ p: 3 }}>
                    <Box display="flex" alignItems="center" mb={3}>
                      <MovieIcon sx={{ fontSize: 28, mr: 1, color: 'primary.main' }} />
                      <Typography variant="h5" fontWeight={600}>
                        Video Output Options
                      </Typography>
                    </Box>
                    
                    <Grid container spacing={3}>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          select
                          id="video_format"
                          name="video_format"
                          label="Video Format"
                          value={formik.values.video_format}
                          onChange={formik.handleChange}
                          sx={{ 
                            '& .MuiOutlinedInput-root': {
                              borderRadius: '12px',
                            }
                          }}
                        >
                          <MenuItem value="mp4">MP4</MenuItem>
                          <MenuItem value="mov">MOV</MenuItem>
                          <MenuItem value="mkv">MKV</MenuItem>
                        </TextField>
                      </Grid>
                      
                      <Grid item xs={12} sm={6}>
                        <TextField
                          select
                          id="resolution"
                          name="resolution"
                          label="Resolution"
                          value={formik.values.resolution}
                          onChange={formik.handleChange}
                          sx={{ 
                            '& .MuiOutlinedInput-root': {
                              borderRadius: '12px',
                            }
                          }}
                        >
                          <MenuItem value="1080p">1080p</MenuItem>
                          <MenuItem value="720p">720p</MenuItem>
                          <MenuItem value="480p">480p</MenuItem>
                        </TextField>
                      </Grid>
                      
                      <Grid item xs={12}>
                        <SubtitleStyleEditor
                          value={formik.values.subtitle_style}
                          onChange={(newValue) => formik.setFieldValue('subtitle_style', newValue)}
                        />
                        {formik.touched.subtitle_style && formik.errors.subtitle_style && (
                          <Alert severity="error" sx={{ mt: 2, borderRadius: '12px' }}>
                            {formik.errors.subtitle_style as string}
                          </Alert>
                        )}
                      </Grid>
                    </Grid>
                  </SectionCard>
                </Fade>
              </Grid>
            )}
            
            {/* Submit Button */}
            <Grid item xs={12}>
              <Fade in={slideIn} timeout={2200}>
                <Box textAlign="center" mt={2}>
                  <Button
                    type="submit"
                    variant="contained"
                    size="large"
                    disabled={isSubmitting}
                    startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : <VideoLibraryIcon />}
                    sx={{
                      px: 6,
                      py: 2,
                      borderRadius: '20px',
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                      boxShadow: `0 8px 24px ${alpha(theme.palette.primary.main, 0.4)}`,
                      '&:hover': {
                        background: `linear-gradient(135deg, ${theme.palette.primary.dark} 0%, ${theme.palette.secondary.main} 100%)`,
                        boxShadow: `0 12px 32px ${alpha(theme.palette.primary.main, 0.5)}`,
                        transform: 'translateY(-2px)',
                      },
                      '&:disabled': {
                        background: theme.palette.action.disabledBackground,
                        color: theme.palette.action.disabled,
                      },
                      transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
                    }}
                  >
                    {isSubmitting ? 'Creating Job...' : 'Create Video Job'}
                  </Button>
                </Box>
              </Fade>
            </Grid>
          </Grid>
                </form>
              </CardContent>
            </StyledCard>

            {/* Information Card */}
            <Fade in={slideIn} timeout={2400}>
              <Alert 
                severity="info" 
                sx={{ 
                  mt: 3,
                  borderRadius: '16px',
                  background: `linear-gradient(145deg, ${alpha(theme.palette.info.main, 0.08)}, ${alpha(theme.palette.info.main, 0.04)})`,
                  border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
                  backdropFilter: 'blur(10px)',
                  '& .MuiAlert-icon': {
                    color: theme.palette.info.main,
                  }
                }}
              >
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  Important Notes
                </Typography>
                <Box component="ul" sx={{ pl: 2, m: 0 }}>
                  <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                    Video processing may take several minutes depending on length and complexity
                  </Typography>
                  <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                    Source language can be auto-detected for many common languages
                  </Typography>
                  <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                    For subtitle generation, you can select up to 2 languages simultaneously
                  </Typography>
                  <Typography component="li" variant="body2">
                    Higher resolutions will take longer to process but provide better quality
                  </Typography>
                </Box>
              </Alert>
            </Fade>
          </Box>
        </Slide>
      </Container>
    );
};

export default NewJob;
