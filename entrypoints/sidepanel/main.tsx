import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import { initApiBase } from './lib/apiBase';
import '../../assets/tailwind.css';

// Resolve the backend URL (stored override or build-time default) before the
// first render, so the initial health probe already targets the right host.
initApiBase().finally(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
