import React, { useState, useEffect } from 'react';
import {
  FormControl,
  FormLabel,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Typography,
  Alert,
  Paper,
  Box,
  Divider,
} from '@mui/material';

interface SubtitleLanguageOption {
  code: string;
  name: string;
  isSource?: boolean;
}

interface SubtitleLanguageSelectorProps {
  availableLanguages: SubtitleLanguageOption[];
  sourceLanguage: string;
  selectedLanguages: string[];
  onChange: (selectedLanguageCodes: string[]) => void;
  maxSelections?: number;
}

const SubtitleLanguageSelector: React.FC<SubtitleLanguageSelectorProps> = ({
  availableLanguages,
  sourceLanguage,
  selectedLanguages,
  onChange,
  maxSelections = 2
}) => {
  // Track selected languages and enforce maximum number of selections
  const [selected, setSelected] = useState<string[]>(selectedLanguages || []);
  
  // Track if we've hit the max selections limit
  const [limitReached, setLimitReached] = useState(false);

  // Initialize with default value (source language) if no selections
  useEffect(() => {
    if (selectedLanguages.length === 0 && sourceLanguage) {
      setSelected([sourceLanguage]);
      onChange([sourceLanguage]);
    } else {
      setSelected(selectedLanguages);
    }
  }, [selectedLanguages, sourceLanguage, onChange]);

  // Update limit reached status when selection changes
  useEffect(() => {
    setLimitReached(selected.length >= maxSelections);
  }, [selected, maxSelections]);

  const handleLanguageToggle = (langCode: string) => {
    let newSelected = [...selected];
    
    if (newSelected.includes(langCode)) {
      // Remove language if already selected
      newSelected = newSelected.filter(code => code !== langCode);
    } else {
      // Add language if not already selected and under the limit
      if (newSelected.length < maxSelections) {
        newSelected.push(langCode);
      } else {
        return; // Do nothing if max limit reached
      }
    }
    
    // Update state and call parent onChange
    setSelected(newSelected);
    onChange(newSelected);
  };

  // Get language display name
  const getLanguageName = (langCode: string) => {
    const lang = availableLanguages.find(l => l.code === langCode);
    return lang ? lang.name : langCode;
  };

  // Separate languages into source and target categories
  const sourceLanguageOption = availableLanguages.find(l => l.code === sourceLanguage);
  const targetLanguageOptions = availableLanguages.filter(l => l.code !== sourceLanguage);

  return (
    <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
      <Typography variant="subtitle1" gutterBottom fontWeight="bold">
        Subtitle Language Selection
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Select up to {maxSelections} languages to include in your video subtitles
      </Typography>
      
      {limitReached && selected.length >= maxSelections && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Maximum selection limit reached ({maxSelections}). Deselect a language to choose another.
        </Alert>
      )}
      
      <Box sx={{ mt: 2 }}>
        <FormControl component="fieldset">
          <FormLabel component="legend">Source Language</FormLabel>
          <FormGroup>
            {sourceLanguageOption && (
              <FormControlLabel
                control={
                  <Checkbox 
                    checked={selected.includes(sourceLanguageOption.code)}
                    onChange={() => handleLanguageToggle(sourceLanguageOption.code)}
                  />
                }
                label={`${sourceLanguageOption.name} (Original)`}
              />
            )}
          </FormGroup>
        </FormControl>
      </Box>
      
      {targetLanguageOptions.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Divider sx={{ my: 2 }} />
          <FormControl component="fieldset">
            <FormLabel component="legend">Translation Languages</FormLabel>
            <FormGroup>
              {targetLanguageOptions.map((lang) => (
                <FormControlLabel
                  key={lang.code}
                  control={
                    <Checkbox 
                      checked={selected.includes(lang.code)}
                      onChange={() => handleLanguageToggle(lang.code)}
                      disabled={limitReached && !selected.includes(lang.code)}
                    />
                  }
                  label={`${lang.name} (Translation)`}
                />
              ))}
            </FormGroup>
          </FormControl>
        </Box>
      )}

      <Box sx={{ mt: 2 }}>
        <Typography variant="body2">
          Selected: {selected.map(getLanguageName).join(', ')}
        </Typography>
      </Box>
    </Paper>
  );
};

export default SubtitleLanguageSelector;
