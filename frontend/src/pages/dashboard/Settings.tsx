import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  Divider,
  Snackbar,
  Alert,
  CircularProgress,
  Container,
  useTheme,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { Tune as TuneIcon } from '@mui/icons-material';
import Slider from '@mui/material/Slider';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import { styled } from '@mui/material/styles';
import { API_BASE_URL } from '../../services/api/apiClient';

const StyledCard = styled(Card)(({ theme }) => ({
  borderRadius: '12px',
  background: theme.palette.background.paper,
  border: `1px solid ${theme.palette.divider}`,
  overflow: 'hidden',
  boxShadow: 'none',
}));

const DEFAULT_PREFS: Record<string, any> = {
  split_trigger_duration: 2.5,
  split_trigger_words: 8,
  pause_split_threshold: 0.3,
  max_words_per_segment: 7,
  split_on_comma: true,
  llm_base_url: '',
  llm_api_key: '',
  llm_api_key_display: '',
  llm_model: '',
  llm_temperature: 0.7,
  llm_max_tokens: 8000,
  whisper_api_url: '',
  whisper_api_key: '',
  whisper_model: '',
};

const Settings: React.FC = () => {
  const theme = useTheme();
  
  const [loading, setLoading] = useState(false);
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/account/preferences`)
      .then(r => r.ok ? r.json() : DEFAULT_PREFS)
      .then(setPrefs)
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/api/v1/account/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      });
      if (res.ok) {
        setPrefs(await res.json());
        setSnackbar({ open: true, message: '设置已保存', severity: 'success' });
      } else throw new Error();
    } catch {
      setSnackbar({ open: true, message: '保存失败', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const [llmTest, setLlmTest] = useState<{loading: boolean, status: string, message: string, models: string[]}>({loading: false, status: '', message: '', models: []});
  const [whisperTest, setWhisperTest] = useState<{loading: boolean, status: string, message: string}>({loading: false, status: '', message: ''});

  const handleTestLlm = async () => {
    setLlmTest({loading: true, status: '', message: '', models: []});
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/account/test-api`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({base_url: prefs.llm_base_url, api_key: prefs.llm_api_key, model: prefs.llm_model, type: 'llm'}),
      });
      const data = await res.json();
      setLlmTest({loading: false, ...data});
    } catch { setLlmTest({loading: false, status: 'error', message: '请求失败', models: []}); }
  };

  const handleTestWhisper = async () => {
    setWhisperTest({loading: true, status: '', message: ''});
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/account/test-api`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({base_url: prefs.whisper_api_url, model: prefs.whisper_model, type: 'whisper'}),
      });
      const data = await res.json();
      setWhisperTest({loading: false, status: data.status, message: data.message});
    } catch { setWhisperTest({loading: false, status: 'error', message: '请求失败'}); }
  };

  return (
    <Box sx={{
      background: theme.palette.background.default,
      height: '100vh', overflow: 'auto', pb: 2,
    }}>
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
        
          <Box pt={2} pb={1}>
            
              <Box mb={2}>
                <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', mb: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
                  <TuneIcon sx={{ fontSize: 36, color: 'primary.main' }} />
                  系统设置
                </Typography>
                <Typography variant="body1" sx={{ color: 'text.secondary' }}>
                  配置字幕分割参数和 AI 模型
                </Typography>
              </Box>
            

            
              <StyledCard>
                <CardContent sx={{ p: 3, position: 'relative', zIndex: 1 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={12}>
                      <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>字幕分割</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        控制转录结果如何分割为字幕行。数值越小，字幕越短、越易读。
                      </Typography>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography gutterBottom>分割触发时长: <strong>{prefs.split_trigger_duration}s</strong></Typography>
                      <Typography variant="caption" color="text.secondary">超过此时长的片段会被分割</Typography>
                      <Slider value={prefs.split_trigger_duration} onChange={(_, v) => setPrefs({ ...prefs, split_trigger_duration: v as number })}
                        min={1.0} max={8.0} step={0.5} marks={[{ value: 1, label: '1s' }, { value: 4, label: '4s' }, { value: 8, label: '8s' }]} valueLabelDisplay="auto" />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography gutterBottom>分割触发词数: <strong>{prefs.split_trigger_words}</strong></Typography>
                      <Typography variant="caption" color="text.secondary">超过此词数的片段会被分割</Typography>
                      <Slider value={prefs.split_trigger_words} onChange={(_, v) => setPrefs({ ...prefs, split_trigger_words: v as number })}
                        min={4} max={20} step={1} marks={[{ value: 4, label: '4' }, { value: 12, label: '12' }, { value: 20, label: '20' }]} valueLabelDisplay="auto" />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography gutterBottom>停顿分割阈值: <strong>{prefs.pause_split_threshold}s</strong></Typography>
                      <Typography variant="caption" color="text.secondary">词间停顿超过此值时分割</Typography>
                      <Slider value={prefs.pause_split_threshold} onChange={(_, v) => setPrefs({ ...prefs, pause_split_threshold: v as number })}
                        min={0.1} max={1.0} step={0.05} marks={[{ value: 0.1, label: '0.1s' }, { value: 0.5, label: '0.5s' }, { value: 1.0, label: '1s' }]} valueLabelDisplay="auto" />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography gutterBottom>每行最大词数: <strong>{prefs.max_words_per_segment}</strong></Typography>
                      <Typography variant="caption" color="text.secondary">单行字幕的词数硬性上限</Typography>
                      <Slider value={prefs.max_words_per_segment} onChange={(_, v) => setPrefs({ ...prefs, max_words_per_segment: v as number })}
                        min={3} max={15} step={1} marks={[{ value: 3, label: '3' }, { value: 7, label: '7' }, { value: 15, label: '15' }]} valueLabelDisplay="auto" />
                    </Grid>

                    <Grid item xs={12}>
                      <FormControlLabel
                        control={<Switch checked={prefs.split_on_comma} onChange={(e) => setPrefs({ ...prefs, split_on_comma: e.target.checked })} />}
                        label="在逗号处分割（除句号、问号等之外）"
                      />
                    </Grid>

                    {/* LLM API Configuration */}
                    <Grid item xs={12}>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="h6" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>翻译大模型</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        用于内容分析和翻译的 OpenAI 兼容 API。支持 OpenAI、Gemini、DeepSeek、本地模型等。
                      </Typography>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth label="接口地址" placeholder="https://api.openai.com/v1"
                        value={prefs.llm_base_url || ''} onChange={(e) => setPrefs({ ...prefs, llm_base_url: e.target.value })}
                        size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth label="API 密钥" type="password" placeholder="sk-..."
                        value={prefs.llm_api_key || ''} onChange={(e) => setPrefs({ ...prefs, llm_api_key: e.target.value })}
                        helperText={prefs.llm_api_key_display ? `当前: ${prefs.llm_api_key_display}` : '未设置'}
                        size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                        {llmTest.models.length > 0 ? (
                          <FormControl fullWidth size="small">
                            <InputLabel>模型</InputLabel>
                            <Select value={prefs.llm_model || ''} label="模型"
                              onChange={(e) => setPrefs({ ...prefs, llm_model: e.target.value })}
                              sx={{ borderRadius: '10px' }}>
                              {llmTest.models.map((m: string) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                            </Select>
                          </FormControl>
                        ) : (
                          <TextField fullWidth label="模型名称" placeholder="点击测试获取模型列表"
                            value={prefs.llm_model || ''} onChange={(e) => setPrefs({ ...prefs, llm_model: e.target.value })}
                            size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                        )}
                      </Box>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, height: '40px' }}>
                        <Button variant="outlined" size="small" onClick={handleTestLlm} disabled={llmTest.loading || !prefs.llm_base_url}
                          sx={{ borderRadius: '8px', whiteSpace: 'nowrap' }}>
                          {llmTest.loading ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
                          测试连接
                        </Button>
                        {llmTest.status && (
                          <Typography variant="body2" noWrap sx={{ color: llmTest.status === 'ok' ? 'success.main' : 'error.main' }}>
                            {llmTest.message}
                          </Typography>
                        )}
                      </Box>
                    </Grid>

                    {/* Whisper API Configuration */}
                    <Grid item xs={12}>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="h6" sx={{ mt: 2, mb: 1, fontWeight: 600 }}>语音识别 (Whisper)</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        用于音频转录的语音识别 API，兼容 OpenAI Whisper 接口。
                      </Typography>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth label="Whisper 接口地址" placeholder="https://api.openai.com/v1"
                        value={prefs.whisper_api_url || ''} onChange={(e) => setPrefs({ ...prefs, whisper_api_url: e.target.value })}
                        size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth label="Whisper API 密钥（可留空）" type="password" placeholder="sk-..."
                        value={prefs.whisper_api_key || ''} onChange={(e) => setPrefs({ ...prefs, whisper_api_key: e.target.value })}
                        size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField fullWidth label="Whisper 模型" placeholder="whisper-large-v3-turbo"
                        value={prefs.whisper_model || ''} onChange={(e) => setPrefs({ ...prefs, whisper_model: e.target.value })}
                        size="small" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }} />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, height: '40px' }}>
                        <Button variant="outlined" size="small" onClick={handleTestWhisper} disabled={whisperTest.loading || !prefs.whisper_api_url}
                          sx={{ borderRadius: '8px', whiteSpace: 'nowrap' }}>
                          {whisperTest.loading ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
                          测试连接
                        </Button>
                        {whisperTest.status && (
                          <Typography variant="body2" noWrap sx={{ color: whisperTest.status === 'ok' ? 'success.main' : 'error.main' }}>
                            {whisperTest.message}
                          </Typography>
                        )}
                      </Box>
                    </Grid>

                    <Grid item xs={12}>
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 2 }}>
                        <Button variant="outlined" onClick={() => setPrefs(DEFAULT_PREFS)} sx={{ borderRadius: '12px', px: 3 }}>
                          恢复默认
                        </Button>
                        <Button variant="contained" size="large" disabled={loading} onClick={handleSave}
                          startIcon={loading ? <CircularProgress size={20} /> : null}
                          sx={{
                            borderRadius: '10px', px: 4, py: 1.5,
                            boxShadow: 'none',
                            '&:hover': { boxShadow: 'none' },
                          }}
                        >
                          {loading ? '保存中...' : '保存设置'}
                        </Button>
                      </Box>
                    </Grid>
                  </Grid>
                </CardContent>
              </StyledCard>
            
          </Box>
        
      </Container>

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
};

export default Settings;
