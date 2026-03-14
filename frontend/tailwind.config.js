/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ── Colors bridged from CSS custom properties ──────────────────────
      colors: {
        // Backgrounds
        'bg-base':     'var(--bg-base)',
        'bg-surface':  'var(--bg-surface)',
        'bg-panel':    'var(--bg-panel)',
        'bg-elevated': 'var(--bg-elevated)',
        'bg-card':     'var(--bg-card)',
        'bg-hover':    'var(--bg-hover)',

        // Borders
        'border-base':   'var(--border)',
        'border-mid':    'var(--border-mid)',
        'border-strong': 'var(--border-strong)',

        // Text
        'text-1': 'var(--text-1)',
        'text-2': 'var(--text-2)',
        'text-3': 'var(--text-3)',

        // Accents
        accent:            'var(--accent)',
        'accent-arena':    'var(--accent-arena)',
        'accent-lab':      'var(--accent-lab)',
        'accent-scrib':    'var(--accent-scrib)',
        'accent-chat':     'var(--accent-chat)',
        'accent-dashboard':'var(--accent-dashboard)',
        'accent-green':    'var(--accent-green)',
        'accent-red':      'var(--accent-red)',

        // Accent dim fills
        'accent-dim':            'var(--accent-dim)',
        'accent-arena-dim':      'var(--accent-arena-dim)',
        'accent-lab-dim':        'var(--accent-lab-dim)',
        'accent-scrib-dim':      'var(--accent-scrib-dim)',
        'accent-chat-dim':       'var(--accent-chat-dim)',
        'accent-dashboard-dim':  'var(--accent-dashboard-dim)',

        // Semantic
        success: 'var(--success)',
        error:   'var(--error)',
        warning: 'var(--warning)',
      },

      // ── Border radius bridged from CSS tokens ──────────────────────────
      borderRadius: {
        sm: 'var(--r-sm)',
        md: 'var(--r-md)',
        lg: 'var(--r-lg)',
        xl: 'var(--r-xl)',
      },

      // ── Box shadows ────────────────────────────────────────────────────
      boxShadow: {
        sm:         'var(--shadow-sm)',
        md:         'var(--shadow-md)',
        lg:         'var(--shadow-lg)',
        'glow-orange': 'var(--shadow-glow-orange)',
        'glow-cyan':   'var(--shadow-glow-cyan)',
      },

      // ── Typography ─────────────────────────────────────────────────────
      fontFamily: {
        display: ['var(--font-display)', 'sans-serif'],
        ui:      ['var(--font-ui)',      'sans-serif'],
        mono:    ['var(--font-mono)',    'monospace'],
      },

      // ── Layout constraints ─────────────────────────────────────────────
      maxWidth: {
        content: 'var(--content-w)',
      },

      spacing: {
        'navbar':         'var(--navbar-h)',
        'navbar-main':    'var(--navbar-main-h)',
        'navbar-context': 'var(--navbar-context-h)',
      },
    },
  },
  // Disable Tailwind's CSS reset (preflight) to avoid conflicting with the
  // existing hand-crafted global resets in index.css.
  corePlugins: {
    preflight: false,
  },
  plugins: [],
}
