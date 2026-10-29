import React from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './styles.css';
import Shell, { RoleGate } from './components/Shell';
import { ToastProvider } from './components/ui';
import { AuthProvider, can } from './lib/auth';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Pond from './pages/Pond';
import NewRound from './pages/NewRound';
import Round from './pages/Round';
import Review from './pages/Review';
import Evaluation from './pages/Evaluation';
import Maintenance from './pages/Maintenance';
import ContentPage from './pages/ContentPage';
import Profile from './pages/Profile';
import NotFound from './pages/NotFound';

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'ponds/:pondId', element: <Pond /> },
      { path: 'sample', element: <RoleGate allow={can.sample}><NewRound /></RoleGate> },
      { path: 'rounds/:roundId', element: <Round /> },
      { path: 'review', element: <RoleGate allow={can.review}><Review /></RoleGate> },
      { path: 'evaluation', element: <RoleGate allow={can.evaluate}><Evaluation /></RoleGate> },
      { path: 'maintenance', element: <RoleGate allow={can.admin}><Maintenance /></RoleGate> },
      { path: 'faqs', element: <ContentPage contentKey="faqs" /> },
      { path: 'about', element: <ContentPage contentKey="about" /> },
      { path: 'profile', element: <Profile /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  </React.StrictMode>,
);
