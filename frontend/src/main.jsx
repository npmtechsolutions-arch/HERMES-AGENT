import React from 'react'
import ReactDOM from 'react-dom/client'
// HashRouter (URLs like /#/login) so deep links work on any static host
// (Render, etc.) and in the packaged desktop app without server rewrite rules.
import { HashRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import { initTheme } from './theme'
import { initMode } from './mode'
import './styles.css'

initTheme()
initMode()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </HashRouter>
  </React.StrictMode>
)
