import React from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './styles.css';
import Shell from './components/Shell';
import { ToastProvider } from './components/ui';
import Overview from './pages/Overview';
import Pond from './pages/Pond';
import RoundDetail from './pages/RoundDetail';
import { SampleStart, SampleRound } from './pages/Sample';
import Alerts from './pages/Alerts';
import Evaluation from './pages/Evaluation';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'ponds/:pondId', element: <Pond /> },
      { path: 'rounds/:roundId', element: <RoundDetail /> },
      { path: 'sample', element: <SampleStart /> },
      { path: 'sample/:roundId', element: <SampleRound /> },
      { path: 'alerts', element: <Alerts /> },
      { path: 'evaluation', element: <Evaluation /> },
      { path: 'settings', element: <Settings /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <RouterProvider router={router} />
    </ToastProvider>
  </React.StrictMode>,
);
