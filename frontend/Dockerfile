# --- Stage 1: Build the React application ---
FROM node:18-alpine AS build

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json to leverage Docker cache
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Set build-time environment variables
ARG REACT_APP_API_URL
ARG REACT_APP_API_BASE_URL
ARG REACT_APP_API_VERSION=/api/v1

# Set environment variables for the build
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_API_VERSION=$REACT_APP_API_VERSION

# Build the application for production
RUN npm run build


# --- Stage 2: Serve the application with Nginx ---
FROM nginx:stable-alpine

# Copy the static files from the build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy the custom Nginx configuration
# This will replace the default Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the entrypoint script for runtime environment variable injection
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port 80
EXPOSE 80

# Use custom entrypoint that injects environment variables at runtime
ENTRYPOINT ["/entrypoint.sh"]