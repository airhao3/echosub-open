import React from 'react';
import {
  Box,
  Typography,
  Grid,
  TextField,
  Slider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  SelectChangeEvent,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

interface EnhancementSettings {
  brightness?: number;
  contrast?: number;
  rotation?: number;
  border_color?: string;
  border_width?: number;
}

interface EnhancementEditorProps {
  value: EnhancementSettings;
  onChange: (newValue: EnhancementSettings) => void;
}

const EnhancementEditor: React.FC<EnhancementEditorProps> = ({ value, onChange }) => {
  const handleSliderChange = (name: keyof EnhancementSettings, sliderValue: number | number[]) => {
    onChange({ ...value, [name]: sliderValue as number });
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value: inputValue } = event.target;
    onChange({ ...value, [name]: inputValue });
  };

  const handleSelectChange = (event: SelectChangeEvent<number>) => {
    const name = event.target.name as keyof EnhancementSettings;
    if (name) {
      onChange({ ...value, [name]: event.target.value as number });
    }
  };

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="h6">Video Enhancement (Optional)</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <Typography gutterBottom>Brightness</Typography>
            <Slider
              name="brightness"
              value={value.brightness || 0}
              onChange={(e, val) => handleSliderChange('brightness', val)}
              aria-labelledby="brightness-slider"
              valueLabelDisplay="auto"
              step={0.01}
              min={-0.5}
              max={0.5}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography gutterBottom>Contrast</Typography>
            <Slider
              name="contrast"
              value={value.contrast || 1}
              onChange={(e, val) => handleSliderChange('contrast', val)}
              aria-labelledby="contrast-slider"
              valueLabelDisplay="auto"
              step={0.1}
              min={0.5}
              max={2.5}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Rotation</InputLabel>
              <Select
                name="rotation"
                value={value.rotation || 0}
                onChange={handleSelectChange}
                label="Rotation"
              >
                <MenuItem value={0}>None</MenuItem>
                <MenuItem value={90}>90 degrees clockwise</MenuItem>
                <MenuItem value={-90}>90 degrees counter-clockwise</MenuItem>
                <MenuItem value={180}>180 degrees</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3}>
            <TextField
              fullWidth
              name="border_color"
              label="Border Color"
              value={value.border_color || 'black'}
              onChange={handleInputChange}
              helperText="e.g., black, #FF0000"
            />
          </Grid>
          <Grid item xs={12} sm={3}>
            <TextField
              fullWidth
              name="border_width"
              label="Border Width (px)"
              type="number"
              value={value.border_width || 0}
              onChange={handleInputChange}
            />
          </Grid>
        </Grid>
      </AccordionDetails>
    </Accordion>
  );
};

export default EnhancementEditor;
