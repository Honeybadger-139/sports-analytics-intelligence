import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Navbar from './components/Navbar'
import Overview from './pages/Overview'
import Pulse    from './pages/Pulse'
import Arena    from './pages/Arena'
import Lab      from './pages/Lab'
import Scribble from './pages/Scribble'
import Chatbot  from './pages/Chatbot'
import { useSystemStatus } from './hooks/useApi'

const THEME_KEY = 'sai_v2_theme'

function AppShell() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  const { data: sys, loading } = useSystemStatus()

  useEffect(() => {
    document.body.classList.toggle('theme-light', theme === 'light')
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const sysStatus: 'healthy' | 'degraded' | 'error' | 'loading' =
    loading         ? 'loading'  :
    sys?.status === 'healthy'  ? 'healthy'  :
    sys?.status === 'error'    ? 'error'    :
    sys?.status === 'degraded' ? 'degraded' : 'loading'

  return (
    <>
      <Navbar
        systemStatus={sysStatus}
        theme={theme}
        onToggleTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
      />
      <AnimatePresence mode="wait">
        <Routes>
          <Route path="/"         element={<Overview />} />
          <Route path="/pulse/*"  element={<Pulse />} />
          <Route path="/arena/*"  element={<Arena />} />
          <Route path="/lab/*"    element={<Lab />} />
          <Route path="/scribble" element={<Scribble />} />
          <Route path="/chatbot"  element={<Chatbot />} />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
