import { apiClient } from './apiClient';

export interface SupportedLanguage {
  code: string;
  name: string;
  isSource?: boolean;
}

/**
 * Fetches the list of supported source languages for transcription.
 */
export const getSourceLanguages = async (): Promise<SupportedLanguage[]> => {
  const response = await apiClient.get<SupportedLanguage[]>('/languages/source');
  return response.data;
};

/**
 * Fetches the list of supported target languages for translation.
 */
export const getTargetLanguages = async (): Promise<SupportedLanguage[]> => {
  const response = await apiClient.get<SupportedLanguage[]>('/languages/target');
  return response.data;
};
