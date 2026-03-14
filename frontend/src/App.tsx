import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Navbar from './components/Navbar'
import Overview from './pages/Overview'
import Pulse    from './pages/Pulse'
import Arena    from './pages/Arena'
import Lab      from './pages/Lab'
import Dashboard from './pages/Dashboard'
import DashboardCreate from './pages/DashboardCreate'
import Scribble from './pages/Scribble'
import Chatbot  from './pages/Chatbot'
import ModelInsight from './pages/ModelInsight'
import DraftHelp from './pages/DraftHelp'
import ComingSoonHold from './components/ComingSoonHold'
import { useSystemStatus } from './hooks/useApi'
import { SportContextProvider, useSportContext } from './context/SportContext'
import { isLiveDataSelection } from './config/sports'

const THEME_KEY = 'sai_v2_theme'
const queryClient = new QueryClient()

function AppShell() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  const { data: sys, loading, error: sysError } = useSystemStatus()
  const { selection } = useSportContext()
  const isLiveSelection = isLiveDataSelection(selection)

  useEffect(() => {
    document.body.classList.toggle('theme-light', theme === 'light')
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const sysStatus: 'healthy' | 'degraded' | 'error' | 'loading' =
    loading                    ? 'loading'  :
    sysError && !sys           ? 'error'    :
    sys?.status === 'healthy'  ? 'healthy'  :
    sys?.status === 'degraded' ? 'degraded' :
    sys?.status === 'error'    ? 'error'    : 'error'

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
          <Route path="/pulse/*"  element={isLiveSelection ? <Pulse /> : <ComingSoonHold section="Pulse" />} />
          <Route path="/arena/*"  element={isLiveSelection ? <Arena /> : <ComingSoonHold section="Arena" />} />
          <Route path="/lab/*"    element={isLiveSelection ? <Lab /> : <ComingSoonHold section="Lab" />} />
          <Route path="/dashboard/create" element={isLiveSelection ? <DashboardCreate /> : <ComingSoonHold section="Dashboard Builder" />} />
          <Route path="/dashboard" element={isLiveSelection ? <Dashboard /> : <ComingSoonHold section="Dashboard" />} />
          <Route path="/scribble" element={isLiveSelection ? <Scribble /> : <ComingSoonHold section="Scribble" />} />
          <Route path="/chatbot"  element={isLiveSelection ? <Chatbot /> : <ComingSoonHold section="Chatbot" />} />
          <Route path="/chatbot/model-insight" element={isLiveSelection ? <ModelInsight /> : <ComingSoonHold section="Model Insight" />} />
          <Route path="/chatbot/draft-help" element={isLiveSelection ? <DraftHelp /> : <ComingSoonHold section="Draft Help" />} />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SportContextProvider>
          <AppShell />
        </SportContextProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
