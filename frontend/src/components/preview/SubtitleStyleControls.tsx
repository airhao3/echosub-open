import React from 'react';
import {
  Box,
  Typography,
  Slider,
  FormControl,
  FormLabel,
  ToggleButton,
  ToggleButtonGroup,
  Popover,
  Button,
  Grid,
  Divider
} from '@mui/material';
import {
  FormatBold,
  FormatItalic,
  FormatSize,
  Palette,
  TextFields
} from '@mui/icons-material';

export interface SubtitleStyle {
  fontSize: number;
  fontFamily: string;
  fontWeight: 'normal' | 'bold';
  fontStyle: 'normal' | 'italic';
  color: string;
  backgroundColor: string;
  backgroundOpacity: number;
  strokeColor: string;
  strokeWidth: number;
  position: 'bottom' | 'top' | 'center';
  alignment: 'left' | 'center' | 'right';
}

interface SubtitleStyleControlsProps {
  style: SubtitleStyle;
  onChange: (style: SubtitleStyle) => void;
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
}

const defaultColors = [
  '#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF', 
  '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080'
];

const fontFamilies = [
  'Arial', 'Helvetica', 'Georgia', 'Times New Roman', 
  'Courier New', 'Verdana', 'Impact', 'Comic Sans MS'
];

const SubtitleStyleControls: React.FC<SubtitleStyleControlsProps> = ({
  style,
  onChange,
  anchorEl,
  open,
  onClose
}) => {
  const handleStyleChange = (key: keyof SubtitleStyle, value: any) => {
    onChange({ ...style, [key]: value });
  };

  const ColorPicker: React.FC<{ 
    value: string; 
    onChange: (color: string) => void; 
    label: string 
  }> = ({ value, onChange, label }) => (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" sx={{ mb: 1 }}>{label}</Typography>
      <Grid container spacing={0.5}>
        {defaultColors.map((color) => (
          <Grid item key={color}>
            <Button
              sx={{
                minWidth: '32px',
                width: '32px',
                height: '32px',
                backgroundColor: color,
                border: value === color ? '3px solid #1976d2' : '1px solid #ccc',
                '&:hover': {
                  backgroundColor: color,
                  opacity: 0.8
                }
              }}
              onClick={() => onChange(color)}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'left',
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'left',
      }}
    >
      <Box sx={{ 
        p: 3, 
        minWidth: '350px', 
        maxWidth: '400px',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(0, 0, 0, 0.1)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
      }}>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextFields />
          Subtitle Style Settings
        </Typography>

        {/* Font Size */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormatSize fontSize="small" />
            Font Size: {style.fontSize}px
          </Typography>
          <Slider
            value={style.fontSize}
            onChange={(_, value) => handleStyleChange('fontSize', value)}
            min={12}
            max={48}
            step={2}
            marks={[
              { value: 12, label: '12px' },
              { value: 24, label: '24px' },
              { value: 36, label: '36px' },
              { value: 48, label: '48px' }
            ]}
          />
        </Box>

        {/* Font Style */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>Font Style</Typography>
          <ToggleButtonGroup
            size="small"
            value={[
              ...(style.fontWeight === 'bold' ? ['bold'] : []),
              ...(style.fontStyle === 'italic' ? ['italic'] : [])
            ]}
            onChange={(_, newFormats) => {
              handleStyleChange('fontWeight', newFormats.includes('bold') ? 'bold' : 'normal');
              handleStyleChange('fontStyle', newFormats.includes('italic') ? 'italic' : 'normal');
            }}
          >
            <ToggleButton value="bold" aria-label="bold">
              <FormatBold />
            </ToggleButton>
            <ToggleButton value="italic" aria-label="italic">
              <FormatItalic />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Font Family */}
        <Box sx={{ mb: 3 }}>
          <FormControl size="small" fullWidth>
            <FormLabel sx={{ mb: 1 }}>Font Family</FormLabel>
            <ToggleButtonGroup
              size="small"
              value={style.fontFamily}
              exclusive
              onChange={(_, value) => value && handleStyleChange('fontFamily', value)}
              sx={{ flexWrap: 'wrap', gap: 0.5 }}
            >
              {fontFamilies.slice(0, 4).map((font) => (
                <ToggleButton key={font} value={font} sx={{ fontSize: '0.75rem' }}>
                  {font}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </FormControl>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Color Settings */}
        <ColorPicker
          value={style.color}
          onChange={(color) => handleStyleChange('color', color)}
          label="Text Color"
        />

        <ColorPicker
          value={style.backgroundColor}
          onChange={(color) => handleStyleChange('backgroundColor', color)}
          label="Background Color"
        />

        {/* Background Opacity */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Background Opacity: {Math.round(style.backgroundOpacity * 100)}%
          </Typography>
          <Slider
            value={style.backgroundOpacity}
            onChange={(_, value) => handleStyleChange('backgroundOpacity', value)}
            min={0}
            max={1}
            step={0.1}
            marks={[
              { value: 0, label: '0%' },
              { value: 0.5, label: '50%' },
              { value: 1, label: '100%' }
            ]}
          />
        </Box>

        {/* Stroke Settings */}
        <ColorPicker
          value={style.strokeColor}
          onChange={(color) => handleStyleChange('strokeColor', color)}
          label="Stroke Color"
        />

        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Stroke Width: {style.strokeWidth}px
          </Typography>
          <Slider
            value={style.strokeWidth}
            onChange={(_, value) => handleStyleChange('strokeWidth', value)}
            min={0}
            max={4}
            step={0.5}
            marks={[
              { value: 0, label: 'None' },
              { value: 1, label: '1px' },
              { value: 2, label: '2px' },
              { value: 4, label: '4px' }
            ]}
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Position Settings */}
        <Box sx={{ mb: 3 }}>
          <FormLabel sx={{ mb: 1, display: 'block' }}>Subtitle Position</FormLabel>
          <ToggleButtonGroup
            size="small"
            value={style.position}
            exclusive
            onChange={(_, value) => value && handleStyleChange('position', value)}
          >
            <ToggleButton value="top">Top</ToggleButton>
            <ToggleButton value="center">Center</ToggleButton>
            <ToggleButton value="bottom">Bottom</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Alignment */}
        <Box sx={{ mb: 2 }}>
          <FormLabel sx={{ mb: 1, display: 'block' }}>Text Alignment</FormLabel>
          <ToggleButtonGroup
            size="small"
            value={style.alignment}
            exclusive
            onChange={(_, value) => value && handleStyleChange('alignment', value)}
          >
            <ToggleButton value="left">Left</ToggleButton>
            <ToggleButton value="center">Center</ToggleButton>
            <ToggleButton value="right">Right</ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>
    </Popover>
  );
};

export default SubtitleStyleControls;