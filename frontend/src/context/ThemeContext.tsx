import React, { createContext, useState, useContext, useEffect } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { lightTheme, darkTheme } from '../theme/theme';

type ThemeMode = 'light' | 'dark';

interface ThemeContextType {
  mode: ThemeMode;
  toggleThemeMode: () => void;
  isDarkMode: boolean;
}

const ThemeContext = createContext<ThemeContextType>({
  mode: 'light',
  toggleThemeMode: () => {},
  isDarkMode: false
});

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Use localStorage to persist theme preference
  const [mode, setMode] = useState<ThemeMode>(() => {
    const savedTheme = localStorage.getItem('themeMode');
    // Check if system prefers dark mode if no saved preference
    if (!savedTheme) {
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
    }
    return (savedTheme as ThemeMode) || 'light';
  });

  // Effect to save theme preference when it changes
  useEffect(() => {
    localStorage.setItem('themeMode', mode);
  }, [mode]);

  // Toggle between light and dark modes
  const toggleThemeMode = () => {
    setMode((prevMode) => (prevMode === 'light' ? 'dark' : 'light'));
  };

  // Calculate the current theme
  const theme = mode === 'light' ? lightTheme : darkTheme;

  // Add isDarkMode helper
  const isDarkMode = mode === 'dark';

  return (
    <ThemeContext.Provider value={{ mode, toggleThemeMode, isDarkMode }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};
