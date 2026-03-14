import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  section: string
}

interface ErrorBoundaryState {
  hasError: boolean
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void error
    void info
    // Route-level fallback is enough here; request tracing on the backend
    // covers API errors and React will surface local stack traces in dev.
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div style={{
        maxWidth: 'var(--content-w)',
        margin: '0 auto',
        padding: '48px 28px',
      }}>
        <div style={{
          background: 'var(--bg-panel)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--r-md)',
          padding: '24px',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--error)', marginBottom: 8 }}>
            {this.props.section}
          </p>
          <h2 style={{ margin: 0, fontSize: '1.1rem', fontFamily: 'var(--font-display)', color: 'var(--text-1)' }}>
            Something went wrong
          </h2>
          <p style={{ margin: '10px 0 18px', fontSize: '0.9rem', color: 'var(--text-2)' }}>
            Reload this section to recover from the latest render error.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--r-sm)',
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-1)',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Reload section
          </button>
        </div>
      </div>
    )
  }
}
