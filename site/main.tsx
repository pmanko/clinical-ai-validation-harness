import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Navigate to="/welcome" replace />} />
          <Route path=":kind/*" element={<App />} />
          <Route path="welcome" element={<App />} />
        </Route>
      </Routes>
    </HashRouter>
  </React.StrictMode>,
);
