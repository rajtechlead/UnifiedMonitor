/**
 * ErrorBoundary — React class component that catches unhandled render errors.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeComponent />
 *   </ErrorBoundary>
 *
 *   // With a custom fallback:
 *   <ErrorBoundary fallback={<p>Something went wrong.</p>}>
 *     <SomeComponent />
 *   </ErrorBoundary>
 *
 *   // With an error handler:
 *   <ErrorBoundary onError={(err, info) => logger.error(err, info)}>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */

import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
interface Props {
  /** Content to render when no error has occurred. */
  children: ReactNode

  /**
   * Custom fallback UI.  Receives the caught error and a reset callback.
   * When omitted the built-in fallback card is shown.
   */
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode)

  /** Called with the error and React component stack on each caught error. */
  onError?: (error: Error, info: ErrorInfo) => void

  /**
   * Optional key — changing it will reset the boundary.
   * Useful when you want to reset after navigation.
   */
  resetKey?: unknown
}

interface State {
  hasError: boolean
  error: Error | null
}

// ─────────────────────────────────────────────────────────────────────────────
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
    this.reset = this.reset.bind(this)
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, info.componentStack)
    this.props.onError?.(error, info)
  }

  componentDidUpdate(prevProps: Props) {
    // Reset whenever the resetKey changes (e.g. after route navigation)
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.reset()
    }
  }

  reset() {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError || !this.state.error) {
      return this.props.children
    }

    const { fallback } = this.props
    const { error } = this.state

    if (fallback !== undefined) {
      return typeof fallback === 'function' ? fallback(error, this.reset) : fallback
    }

    return <DefaultFallback error={error} reset={this.reset} />
  }
}

// ─────────────────────────────────────────────────────────────────────────────
function DefaultFallback({ error, reset }: { error: Error; reset: () => void }) {
  const isDev = import.meta.env.DEV

  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 320,
        padding: '32px 24px',
        textAlign: 'center',
        color: 'var(--color-text, #1a1a1a)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 56,
          height: 56,
          borderRadius: '50%',
          background: 'rgba(239,68,68,0.1)',
          marginBottom: 20,
        }}
      >
        <AlertTriangle size={28} color="#EF4444" />
      </div>

      <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 8px' }}>
        Something went wrong
      </h2>

      <p style={{ fontSize: 14, color: 'var(--color-text-muted, #6b7280)', margin: '0 0 24px', maxWidth: 420 }}>
        An unexpected error occurred in this part of the application. You can try
        refreshing the page or clicking the button below to recover.
      </p>

      {isDev && (
        <details
          style={{
            marginBottom: 24,
            maxWidth: 600,
            width: '100%',
            textAlign: 'left',
          }}
        >
          <summary
            style={{
              cursor: 'pointer',
              fontSize: 13,
              color: 'var(--color-text-muted, #6b7280)',
              marginBottom: 8,
            }}
          >
            Error details (development only)
          </summary>
          <pre
            style={{
              fontSize: 12,
              overflowX: 'auto',
              padding: '12px 16px',
              borderRadius: 8,
              background: 'var(--color-surface-2, #f9fafb)',
              border: '1px solid var(--color-border, #e5e7eb)',
              color: '#EF4444',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {error.name}: {error.message}
            {'\n\n'}
            {error.stack}
          </pre>
        </details>
      )}

      <div style={{ display: 'flex', gap: 12 }}>
        <button
          onClick={reset}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 20px',
            fontSize: 14,
            fontWeight: 600,
            background: 'var(--color-brand, #1776D2)',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} />
          Try again
        </button>

        <button
          onClick={() => window.location.assign('/')}
          style={{
            padding: '9px 20px',
            fontSize: 14,
            fontWeight: 600,
            background: 'transparent',
            color: 'var(--color-text-muted, #6b7280)',
            border: '1px solid var(--color-border, #e5e7eb)',
            borderRadius: 8,
            cursor: 'pointer',
          }}
        >
          Go to dashboard
        </button>
      </div>
    </div>
  )
}

export default ErrorBoundary
