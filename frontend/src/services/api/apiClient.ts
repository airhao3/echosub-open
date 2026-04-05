import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { notificationService } from '../notificationService';

// Determine the base API URL based on the current hostname
const getApiBaseUrl = (): string => {
  // Check for runtime injected environment variables (placeholders replaced by entrypoint.sh)
  const runtimeApiUrl = '__REACT_APP_API_URL__';
  if (runtimeApiUrl && !runtimeApiUrl.startsWith('__')) {
    return runtimeApiUrl;
  }

  // Prefer build-time environment variable if set
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }

  // Default: assume backend runs on same host, port 8000
  const hostname = window.location.hostname;
  return `http://${hostname}:8000`;
};

export const API_BASE_URL = getApiBaseUrl();
export const API_PREFIX = process.env.REACT_APP_API_VERSION || '/api/v1';

// Log the current configuration for debugging
console.log('API Configuration:', {
  hostname: window.location.hostname,
  REACT_APP_API_URL: process.env.REACT_APP_API_URL,
  REACT_APP_API_VERSION: process.env.REACT_APP_API_VERSION,
  selectedBaseURL: API_BASE_URL,
  apiPrefix: API_PREFIX
});

// Log the API URL being used (without sensitive info)
console.log(`API Base URL: ${API_BASE_URL}${API_PREFIX}`);

// Enable credentials for CORS
axios.defaults.withCredentials = true;

// Helper to get auth token with validation
const getAuthToken = (): string | null => {
  const token = localStorage.getItem('token');
  if (!token) {
    console.warn('No auth token found in localStorage');
    return null;
  }
  return token;
};

class ApiClient {
  private client: AxiosInstance;
  
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });
    
    // Add API version prefix to all requests
    this.client.interceptors.request.use(config => {
      // Skip for external URLs
      if (config.url?.startsWith('http')) {
        return config;
      }
      
      // Add API prefix if not already present
      if (!config.url?.startsWith(API_PREFIX)) {
        config.url = `${API_PREFIX}${config.url?.startsWith('/') ? '' : '/'}${config.url || ''}`;
      }
      
      // Add auth token if available
      const token = getAuthToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      
      return config;
    });
    
    this.initializeInterceptors();
  }
  
  private initializeInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token to all requests
        const token = getAuthToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
          
          // Special handling for media URLs that need token in query params
          if (config.url && (
              config.url.includes('/preview/video/') || 
              config.url.includes('/preview/result/')
            )) {
            config.url += (config.url.includes('?') ? '&' : '?') + `token=${token}`;
          }
        }
        
        // Log request details in development
        if (process.env.NODE_ENV === 'development') {
          console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, {
            headers: config.headers,
            data: config.data
          });
        }
        
        return config;
      },
      (error) => {
        console.error('[API] Request Error:', error);
        return Promise.reject(error);
      }
    );
    
    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        // Log successful responses in development
        if (process.env.NODE_ENV === 'development') {
          console.log(`[API] Response ${response.status} ${response.config.method?.toUpperCase()} ${response.config.url}`, response.data);
        }
        return response;
      },
      (error) => {
        const { response, config } = error;
        
        // Log detailed error info
        if (response) {
          // Server responded with error status
          console.error(`[API] Error ${response.status} on ${config?.method?.toUpperCase()} ${config?.url}`, {
            status: response.status,
            data: response.data,
            headers: response.headers
          });
          
          // Handle specific error statuses
          if (response.status === 401) {
            console.warn('[API] 401 received - open-source version, no auth redirect');
          }
          
          if (response.status === 403) {
            console.warn('[API] Forbidden - Insufficient permissions');
            return Promise.reject(new Error('You do not have permission to perform this action'));
          }

          if (response.status === 402) {
            const errorMessage = response.data?.detail || 'You have exceeded your quota. Please upgrade your plan to continue.';
            console.error('[API] Payment Required:', errorMessage);
            notificationService.showError(errorMessage);
          }
          
          // Add server error message to error object
          if (response.data?.detail) {
            error.message = response.data.detail;
          } else if (response.data?.message) {
            error.message = response.data.message;
          }
          
        } else if (error.request) {
          // Request was made but no response received
          console.error('[API] No response from server', {
            url: config?.url,
            method: config?.method,
            error: error.message
          });
          error.message = 'Unable to connect to server. Please check your network connection.';
          
        } else {
          // Request setup error
          console.error('[API] Request setup error:', error.message);
        }
        
        return Promise.reject(error);
      }
    );
  }
  
  public get<T>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.get<T>(url, config);
  }
  
  public post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.post<T>(url, data, config);
  }
  
  public put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.put<T>(url, data, config);
  }
  
  public patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.patch<T>(url, data, config);
  }
  
  public delete<T>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.delete<T>(url, config);
  }
}

export const apiClient = new ApiClient();
