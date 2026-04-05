# EchoSub Frontend

React-based web interface for EchoSub video translation platform.

## Quick Start

```bash
# Install dependencies
npm install

# Copy and edit environment config
cp .env.example .env

# Start development server
npm start
```

Open http://localhost:3000 in your browser.

## Environment Variables

See `.env.example`. Key settings:

- `REACT_APP_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `REACT_APP_API_VERSION` - API version prefix (default: `/api/v1`)

## Features

- Video upload and processing
- Job management with real-time progress
- Multi-language subtitle generation
- Video preview with subtitle overlay
- Subtitle editing and export (SRT, VTT)
- Responsive Material-UI design

## Tech Stack

React 18, TypeScript, Material-UI v5, Video.js, React Router v6, Axios
