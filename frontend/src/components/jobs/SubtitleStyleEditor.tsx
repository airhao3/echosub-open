import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  TextField,
  Typography,
  MenuItem,
  Slider,
} from '@mui/material';

interface SubtitleStyle {
  font_size: number;
  font_color: string;
  background_color: string;
  position: 'top' | 'middle' | 'bottom';
}

interface SubtitleStyleEditorProps {
  value: string; // JSON string
  onChange: (value: string) => void;
}

const SubtitleStyleEditor: React.FC<SubtitleStyleEditorProps> = ({ value, onChange }) => {
  const [style, setStyle] = useState<SubtitleStyle>(() => {
    try {
      return JSON.parse(value);
    } catch (e) {
      return {
        font_size: 10,
        font_color: '#FFFFFF',
        background_color: 'rgba(0,0,0,0.5)',
        position: 'bottom',
      };
    }
  });

  useEffect(() => {
    try {
      const parsedValue = JSON.parse(value);
      setStyle(parsedValue);
    } catch (e) {
      // Keep local state if external value is invalid
    }
  }, [value]);

  const handleStyleChange = (field: keyof SubtitleStyle, fieldValue: any) => {
    const newStyle = { ...style, [field]: fieldValue };
    setStyle(newStyle);
    onChange(JSON.stringify(newStyle, null, 2));
  };

  return (
    <Box>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>Font Size</Typography>
          <Slider
            value={style.font_size}
            onChange={(_, newValue) => handleStyleChange('font_size', newValue)}
            aria-labelledby="font-size-slider"
            valueLabelDisplay="auto"
            step={1}
            marks
            min={10}
            max={15}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            select
            label="Position"
            value={style.position}
            onChange={(e) => handleStyleChange('position', e.target.value)}
          >
            <MenuItem value="top">Top</MenuItem>
            <MenuItem value="middle">Middle</MenuItem>
            <MenuItem value="bottom">Bottom</MenuItem>
          </TextField>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>Font Color</Typography>
          <input
            type="color"
            value={style.font_color}
            onChange={(e) => handleStyleChange('font_color', e.target.value)}
            style={{ width: '100%', height: '56px', border: '1px solid #ccc', borderRadius: '4px', padding: '5px' }}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>Background Color</Typography>
          <input
            type="color"
            value={style.background_color}
            onChange={(e) => handleStyleChange('background_color', e.target.value)}
            style={{ width: '100%', height: '56px', border: '1px solid #ccc', borderRadius: '4px', padding: '5px' }}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default SubtitleStyleEditor;
