/**
 * Utility functions for handling authentication
 */

/**
 * Adds the authentication token to a URL as a query parameter
 * This allows media elements like <video> and <audio> to access protected resources
 * @param url The URL to add the auth token to
 * @returns URL with auth token as query parameter
 */
export const getAuthenticatedUrl = (url: string): string => {
  const token = localStorage.getItem('token');
  if (!token) return url;
  
  // Check if URL already has query parameters
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${token}`;
};
