#!/bin/sh

# entrypoint.sh - Runtime environment variable injection for React app

# Function to replace placeholders in JavaScript files
replace_env_vars() {
    echo "Injecting runtime environment variables..."
    
    # Find all JavaScript files in the build directory
    find /usr/share/nginx/html -name "*.js" -type f -exec sed -i \
        -e "s|__REACT_APP_API_URL__|${REACT_APP_API_URL:-}|g" \
        -e "s|__REACT_APP_API_BASE_URL__|${REACT_APP_API_BASE_URL:-}|g" \
        -e "s|__REACT_APP_API_VERSION__|${REACT_APP_API_VERSION:-/api/v1}|g" \
        {} +
    
    # Also replace in any HTML files
    find /usr/share/nginx/html -name "*.html" -type f -exec sed -i \
        -e "s|__REACT_APP_API_URL__|${REACT_APP_API_URL:-}|g" \
        -e "s|__REACT_APP_API_BASE_URL__|${REACT_APP_API_BASE_URL:-}|g" \
        -e "s|__REACT_APP_API_VERSION__|${REACT_APP_API_VERSION:-/api/v1}|g" \
        {} +
    
    echo "Environment variables injected successfully"
    echo "REACT_APP_API_URL: ${REACT_APP_API_URL:-'not set'}"
    echo "REACT_APP_API_BASE_URL: ${REACT_APP_API_BASE_URL:-'not set'}"
    echo "REACT_APP_API_VERSION: ${REACT_APP_API_VERSION:-'/api/v1'}"
}

# Replace environment variables
replace_env_vars

# Start nginx in the foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"
