import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

// StrictMode is on: the fabric engine is created once per mount and fully
// disposed on unmount, so the double-mount in dev rebuilds cleanly.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
