// Inter, served from this origin rather than from Google Fonts. A stylesheet
// and font files fetched from a third party on every page load are both a
// supply-chain surface and a record, held elsewhere, of who opened a police
// system and when. Bundling them also lets the app run with no internet.
import "@fontsource/inter/300.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
