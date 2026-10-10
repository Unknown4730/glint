import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ToastProvider } from './hooks/useToast'

const container = document.getElementById('root')

if (!container) {
  throw new Error('Glint could not start: the #root element is missing from index.html.')
}

createRoot(container).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
