import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { ThemeProvider } from './context/ThemeContext';
import MainLayout from './components/layout/MainLayout';
import Notifier from './components/Notifier';
import NotificationProvider from './components/common/NotificationProvider';

// Lazy loaded pages
const Dashboard = React.lazy(() => import('./pages/dashboard/Dashboard'));
const Projects = React.lazy(() => import('./pages/dashboard/Projects'));
const Preview = React.lazy(() => import('./pages/dashboard/Preview'));
const Settings = React.lazy(() => import('./pages/dashboard/Settings'));
const Jobs = React.lazy(() => import('./pages/jobs/Jobs'));
const NewJob = React.lazy(() => import('./pages/jobs/NewJob'));
const Upload = React.lazy(() => import('./pages/dashboard/Upload'));
const JobProcessingPage = React.lazy(() => import('./pages/dashboard/JobProcessingPage'));
const NotFound = React.lazy(() => import('./pages/NotFound'));

const App: React.FC = () => {
  return (
    <ThemeProvider>
      <NotificationProvider>
        <Notifier />
        <React.Suspense
          fallback={
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
              <CircularProgress />
            </Box>
          }
        >
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/auth/*" element={<Navigate to="/dashboard" replace />} />

            <Route path="/dashboard" element={<MainLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="projects" element={<Projects />} />
              <Route path="upload" element={<Upload />} />
              <Route path="preview/:jobId" element={<Preview />} />
              <Route path="settings" element={<Settings />} />
              <Route path="jobs" element={<Jobs />} />
              <Route path="jobs/new" element={<NewJob />} />
              <Route path="job-processing/:jobId" element={<JobProcessingPage />} />
            </Route>

            <Route path="*" element={<NotFound />} />
          </Routes>
        </React.Suspense>
      </NotificationProvider>
    </ThemeProvider>
  );
};

export default App;
