import { createTheme, ThemeOptions } from '@mui/material/styles';
import { PaletteMode } from '@mui/material';

declare module '@mui/material/styles' {
  interface Theme {
    customShadows: {
      card: string;
      primary: string;
      secondary: string;
    };
  }
  // Allow configuration using `createTheme`
  interface ThemeOptions {
    customShadows?: {
      card: string;
      primary: string;
      secondary: string;
    };
  }
}

// Common theme settings shared between light and dark modes
const getBaseTheme = (mode: PaletteMode): ThemeOptions => ({
  customShadows: {
    card: mode === 'light'
      ? '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)'
      : '0 2px 8px rgba(0, 0, 0, 0.32), 0 1px 3px rgba(0, 0, 0, 0.16)',
    primary: mode === 'light'
      ? '0 2px 8px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04)'
      : '0 2px 12px rgba(0, 0, 0, 0.2), 0 1px 4px rgba(0, 0, 0, 0.1)',
    secondary: mode === 'light'
      ? '0 2px 8px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.03)'
      : '0 2px 12px rgba(0, 0, 0, 0.2), 0 1px 4px rgba(0, 0, 0, 0.1)',
  },
  shape: {
    borderRadius: 12,
  },
  palette: {
    mode,
    divider: mode === 'light' ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)',
    primary: {
      main: mode === 'light' ? '#4A7C8A' : '#7AB8C9',
      light: mode === 'light' ? '#6FA3B0' : '#9FD0DD',
      dark: mode === 'light' ? '#2E5A66' : '#5B99AA',
      contrastText: '#ffffff',
    },
    secondary: {
      main: mode === 'light' ? '#8E9EAB' : '#98A8B5',
      light: mode === 'light' ? '#B0BEC5' : '#B8C8D0',
      dark: mode === 'light' ? '#607D8B' : '#78909C',
      contrastText: '#ffffff',
    },
    error: {
      main: mode === 'light' ? '#FF3B30' : '#FF453A',
      light: mode === 'light' ? '#FF6961' : '#FF6D65',
      dark: mode === 'light' ? '#D70015' : '#D70015',
      contrastText: '#ffffff',
    },
    warning: {
      main: mode === 'light' ? '#FF9500' : '#FF9F0A',
      light: mode === 'light' ? '#FFAA33' : '#FFB340',
      dark: mode === 'light' ? '#CC7700' : '#CC7F08',
      contrastText: '#ffffff',
    },
    info: {
      main: mode === 'light' ? '#5AC8FA' : '#64D2FF',
      light: mode === 'light' ? '#7DD5FB' : '#89DDFF',
      dark: mode === 'light' ? '#32B5F8' : '#32B5F8',
      contrastText: '#ffffff',
    },
    success: {
      main: mode === 'light' ? '#34C759' : '#30D158',
      light: mode === 'light' ? '#5DD57A' : '#5DDA7E',
      dark: mode === 'light' ? '#248A3D' : '#248A3D',
      contrastText: '#ffffff',
    },
    ...(mode === 'light'
      ? {
        background: {
          default: '#F7F8FA',
          paper: '#FFFFFF',
        },
        text: {
          primary: '#2C3E50',
          secondary: '#7F8C9B',
          disabled: '#BDC3C7',
        },
      }
      : {
        background: {
          default: '#000000',
          paper: '#1C1C1E',
        },
        text: {
          primary: '#F5F5F7',
          secondary: '#86868B',
          disabled: '#48484A',
        },
      }),

  },
  typography: {
    fontFamily: '"Inter", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Helvetica Neue", "Arial", sans-serif',
    h1: {
      fontSize: '2.25rem',
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.025em',
    },
    h2: {
      fontSize: '1.875rem',
      fontWeight: 700,
      lineHeight: 1.25,
      letterSpacing: '-0.02em',
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.015em',
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontSize: '1.0625rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h6: {
      fontSize: '0.9375rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    body1: {
      fontSize: '0.9375rem',
      fontWeight: 400,
      lineHeight: 1.65,
    },
    body2: {
      fontSize: '0.8125rem',
      fontWeight: 400,
      lineHeight: 1.6,
    },
    button: {
      fontWeight: 500,
      letterSpacing: '0.01em',
    }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {},
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: '16px',
          border: mode === 'light'
            ? '1px solid rgba(0, 0, 0, 0.06)'
            : '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: mode === 'light'
            ? '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)'
            : '0 2px 8px rgba(0, 0, 0, 0.32)',
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#1C1C1E',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '10px',
          fontWeight: 500,
          letterSpacing: '0.01em',
          '&:focus-visible': {
            outline: `2px solid ${mode === 'light' ? '#4A7C8A' : '#7AB8C9'}`,
            outlineOffset: '2px',
          },
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
        outlined: {
          borderWidth: '1px',
          borderColor: mode === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.15)',
          color: mode === 'light' ? '#1D1D1F' : '#F5F5F7',
          '&:hover': {
            borderWidth: '1px',
            borderColor: mode === 'light' ? 'rgba(0, 0, 0, 0.25)' : 'rgba(255, 255, 255, 0.25)',
            backgroundColor: mode === 'light' ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.05)',
          },
        },
        sizeLarge: {
          padding: '11px 24px',
          fontSize: '0.9375rem',
        },
        sizeMedium: {
          padding: '8px 18px',
          fontSize: '0.8125rem',
        },
        sizeSmall: {
          padding: '5px 12px',
          fontSize: '0.75rem',
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : undefined,
          borderRadius: '10px',
        },
        input: {
          color: mode === 'dark' ? '#F5F5F7' : undefined,
          '&:-webkit-autofill': {
            WebkitBoxShadow: mode === 'dark' ? '0 0 0 100px #1C1C1E inset !important' : undefined,
            WebkitTextFillColor: mode === 'dark' ? '#F5F5F7 !important' : undefined,
          },
          '&::placeholder': {
            color: mode === 'dark' ? 'rgba(235, 235, 245, 0.3)' : 'rgba(60, 60, 67, 0.3)',
            opacity: 1,
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.12)',
            borderWidth: '1px',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.22)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? '#7AB8C9' : '#4A7C8A',
            borderWidth: '2px',
          },
          '&.Mui-error .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? '#FF453A' : '#FF3B30',
          },
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: 'small',
        variant: 'outlined',
        fullWidth: true,
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          fontWeight: 500,
          backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)',
          color: mode === 'dark' ? '#F5F5F7' : '#2C3E50',
          border: 'none',
          '&:hover': {
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.07)',
          },
        },
        colorPrimary: {
          backgroundColor: mode === 'dark' ? 'rgba(122, 184, 201, 0.15)' : 'rgba(74, 124, 138, 0.08)',
          color: mode === 'dark' ? '#7AB8C9' : '#4A7C8A',
        },
        colorSecondary: {
          backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)',
          color: mode === 'dark' ? '#98989D' : '#8E8E93',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          border: '1px solid',
        },
        standardSuccess: {
          backgroundColor: mode === 'dark' ? 'rgba(48, 209, 88, 0.08)' : 'rgba(52, 199, 89, 0.06)',
          color: mode === 'dark' ? '#30D158' : '#248A3D',
          borderColor: mode === 'dark' ? 'rgba(48, 209, 88, 0.15)' : 'rgba(52, 199, 89, 0.15)',
        },
        standardError: {
          backgroundColor: mode === 'dark' ? 'rgba(255, 69, 58, 0.08)' : 'rgba(255, 59, 48, 0.06)',
          color: mode === 'dark' ? '#FF453A' : '#D70015',
          borderColor: mode === 'dark' ? 'rgba(255, 69, 58, 0.15)' : 'rgba(255, 59, 48, 0.15)',
        },
        standardWarning: {
          backgroundColor: mode === 'dark' ? 'rgba(255, 159, 10, 0.08)' : 'rgba(255, 149, 0, 0.06)',
          color: mode === 'dark' ? '#FF9F0A' : '#CC7700',
          borderColor: mode === 'dark' ? 'rgba(255, 159, 10, 0.15)' : 'rgba(255, 149, 0, 0.15)',
        },
        standardInfo: {
          backgroundColor: mode === 'dark' ? 'rgba(100, 210, 255, 0.08)' : 'rgba(90, 200, 250, 0.06)',
          color: mode === 'dark' ? '#64D2FF' : '#404040',
          borderColor: mode === 'dark' ? 'rgba(100, 210, 255, 0.15)' : 'rgba(90, 200, 250, 0.15)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'dark' ? '#1C1C1E' : '#FFFFFF',
          borderBottom: mode === 'dark'
            ? '1px solid rgba(255, 255, 255, 0.06)'
            : '1px solid rgba(0, 0, 0, 0.06)',
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: mode === 'dark' ? '#1C1C1E' : '#FFFFFF',
          borderRight: mode === 'dark'
            ? '1px solid rgba(255, 255, 255, 0.06)'
            : '1px solid rgba(0, 0, 0, 0.06)',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: '10px',
          margin: '2px 8px',
          '&:hover': {
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
          },
          '&.Mui-selected': {
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)',
            '&:hover': {
              backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.07)',
            },
          },
        },
      },
    },
  },
});

export const lightTheme = createTheme(getBaseTheme('light'));
export const darkTheme = createTheme(getBaseTheme('dark'));

// For backward compatibility
export default lightTheme;
