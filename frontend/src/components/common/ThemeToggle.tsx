import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { useTheme } from '../../context/ThemeContext';

interface ThemeToggleProps {
  size?: 'small' | 'medium' | 'large';
  tooltipPlacement?: 'top' | 'right' | 'bottom' | 'left';
}

const ThemeToggle: React.FC<ThemeToggleProps> = ({ 
  size = 'medium',
  tooltipPlacement = 'bottom'
}) => {
  const { isDarkMode, toggleThemeMode } = useTheme();
  
  return (
    <Tooltip title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'} placement={tooltipPlacement}>
      <IconButton 
        onClick={toggleThemeMode} 
        color="inherit" 
        size={size}
        aria-label="toggle theme"
      >
        {isDarkMode ? <Brightness7Icon /> : <Brightness4Icon />}
      </IconButton>
    </Tooltip>
  );
};

export default ThemeToggle;
