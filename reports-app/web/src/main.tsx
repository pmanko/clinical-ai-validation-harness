import React from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

import { CatalogRoute } from './routes/catalog';
import { LiveRoute } from './routes/live';
import { ReportRoute } from './routes/report';
import { ReviewRoute } from './routes/review';
import './styles.css';

const router = createBrowserRouter([
  { path: '/', element: <CatalogRoute /> },
  { path: '/runs/:runId', element: <ReportRoute /> },
  { path: '/runs/:runId/live', element: <LiveRoute /> },
  { path: '/runs/:runId/review', element: <ReviewRoute /> }
]);

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
