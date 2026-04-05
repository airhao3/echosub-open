import React, { useState, useEffect } from 'react';
import { Snackbar, Alert as MuiAlert, Box, Typography, Grow } from '@mui/material';
import { TransitionProps } from '@mui/material/transitions';
import { notificationService, Notification } from '../services/notificationService';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import InfoIcon from '@mui/icons-material/Info';
import WarningIcon from '@mui/icons-material/Warning';

const Notifier: React.FC = () => {
  const [notification, setNotification] = useState<Notification | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = notificationService.subscribe(newNotification => {
      console.log('Notification received:', newNotification);
      setNotification(newNotification);
      setOpen(true);
    });
    
    return () => unsubscribe();
  }, []);

  const handleClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    console.log('Notification closing, reason:', reason);
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  if (!notification) {
    return null;
  }

  // Get appropriate icon and color based on severity
  const getIconAndColor = () => {
    switch (notification.severity) {
      case 'success':
        return { 
          icon: <CheckCircleIcon sx={{ fontSize: 40, animation: 'pulse 1.5s infinite' }} />,
          color: '#2e7d32',
          bgColor: '#e8f5e9'
        };
      case 'error':
        return { 
          icon: <ErrorIcon sx={{ fontSize: 40 }} />,
          color: '#d32f2f',
          bgColor: '#ffebee'
        };
      case 'info':
        return { 
          icon: <InfoIcon sx={{ fontSize: 40 }} />,
          color: '#0288d1',
          bgColor: '#e1f5fe'
        };
      case 'warning':
        return { 
          icon: <WarningIcon sx={{ fontSize: 40 }} />,
          color: '#ed6c02',
          bgColor: '#fff3e0'
        };
      default:
        return { 
          icon: <InfoIcon sx={{ fontSize: 40 }} />,
          color: '#0288d1',
          bgColor: '#e1f5fe'
        };
    }
  };

  const { icon, color, bgColor } = getIconAndColor();
  
  return (
    <Snackbar
      key={notification.key}
      open={open}
      autoHideDuration={7000}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      sx={{
        zIndex: 9999, // Ensure it's on top of everything
        '& .MuiSnackbarContent-root': {
          minWidth: '400px',
          padding: '0',
        },
      }}
      TransitionComponent={Grow}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          padding: '16px 24px',
          borderRadius: '8px',
          backgroundColor: bgColor,
          border: `2px solid ${color}`,
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
          width: '100%',
          maxWidth: '500px',
        }}
      >
        <Box 
          sx={{
            mr: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: color,
            '@keyframes pulse': {
              '0%': { opacity: 1, transform: 'scale(0.95)' },
              '50%': { opacity: 0.8, transform: 'scale(1.05)' },
              '100%': { opacity: 1, transform: 'scale(0.95)' },
            },
            '@keyframes bounce': {
              '0%, 20%, 50%, 80%, 100%': { transform: 'translateY(0)' },
              '40%': { transform: 'translateY(-20px)' },
              '60%': { transform: 'translateY(-10px)' },
            },
          }}
        >
          {icon}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography 
            variant="h6" 
            sx={{ 
              fontWeight: 700,
              fontSize: '1.2rem',
              color: color,
              mb: 0.5,
            }}
          >
            {notification.severity === 'success' ? 'Success!' : 
             notification.severity === 'error' ? 'Error!' :
             notification.severity === 'warning' ? 'Warning!' : 'Information'}
          </Typography>
          <Typography 
            variant="body1"
            sx={{ 
              fontSize: '1rem',
              fontWeight: 500,
              color: 'text.primary' 
            }}
          >
            {notification.message}
          </Typography>
        </Box>
      </Box>
    </Snackbar>
  );
};

export default Notifier;
