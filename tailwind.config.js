/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './entrypoints/**/*.{html,ts,tsx,js,jsx}',
    './components/**/*.{ts,tsx,js,jsx}',
  ],
  theme: {
    extend: {
      // ── Themed via CSS variables (swap between Trabahero dark + Tactile Verdance light) ──
      colors: {
        background:                  'var(--color-background)',
        surface:                     'var(--color-surface)',
        'surface-dim':               'var(--color-surface-dim)',
        'surface-bright':            'var(--color-surface-bright)',
        'surface-container-lowest':  'var(--color-surface-container-lowest)',
        'surface-container-low':     'var(--color-surface-container-low)',
        'surface-container':         'var(--color-surface-container)',
        'surface-container-high':    'var(--color-surface-container-high)',
        'surface-container-highest': 'var(--color-surface-container-highest)',
        'surface-variant':           'var(--color-surface-variant)',
        'surface-tint':              'var(--color-surface-tint)',
        'on-background':             'var(--color-on-background)',
        'on-surface':                'var(--color-on-surface)',
        'on-surface-variant':        'var(--color-on-surface-variant)',
        'inverse-surface':           'var(--color-inverse-surface)',
        'inverse-on-surface':        'var(--color-inverse-on-surface)',
        'inverse-primary':           'var(--color-inverse-primary)',
        outline:                     'var(--color-outline)',
        'outline-variant':           'var(--color-outline-variant)',
        primary:                     'var(--color-primary)',
        'on-primary':                'var(--color-on-primary)',
        'primary-container':         'var(--color-primary-container)',
        'on-primary-container':      'var(--color-on-primary-container)',
        'primary-fixed':             'var(--color-primary-fixed)',
        'primary-fixed-dim':         'var(--color-primary-fixed-dim)',
        'on-primary-fixed':          'var(--color-on-primary-fixed)',
        'on-primary-fixed-variant':  'var(--color-on-primary-fixed-variant)',
        secondary:                   'var(--color-secondary)',
        'on-secondary':              'var(--color-on-secondary)',
        'secondary-container':       'var(--color-secondary-container)',
        'on-secondary-container':    'var(--color-on-secondary-container)',
        'secondary-fixed':           'var(--color-secondary-fixed)',
        'secondary-fixed-dim':       'var(--color-secondary-fixed-dim)',
        'on-secondary-fixed':        'var(--color-on-secondary-fixed)',
        'on-secondary-fixed-variant':'var(--color-on-secondary-fixed-variant)',
        tertiary:                    'var(--color-tertiary)',
        'on-tertiary':               'var(--color-on-tertiary)',
        'tertiary-container':        'var(--color-tertiary-container)',
        'on-tertiary-container':     'var(--color-on-tertiary-container)',
        'tertiary-fixed':            'var(--color-tertiary-fixed)',
        'tertiary-fixed-dim':        'var(--color-tertiary-fixed-dim)',
        'on-tertiary-fixed':         'var(--color-on-tertiary-fixed)',
        'on-tertiary-fixed-variant': 'var(--color-on-tertiary-fixed-variant)',
        error:                       'var(--color-error)',
        'on-error':                  'var(--color-on-error)',
        'error-container':           'var(--color-error-container)',
        'on-error-container':        'var(--color-on-error-container)',
      },
      // ── Typography ──────────────────────────────────────────────────
      fontFamily: {
        'headline': ['"Hanken Grotesk"', 'sans-serif'],
        'body':     ['Inter', 'sans-serif'],
        'label':    ['Inter', 'sans-serif'],
      },
      fontSize: {
        'headline-xl': ['48px', { lineHeight: '56px', letterSpacing: '-0.02em', fontWeight: '800' }],
        'headline-lg': ['32px', { lineHeight: '40px', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-md': ['24px', { lineHeight: '32px', fontWeight: '700' }],
        'headline-sm': ['18px', { lineHeight: '24px', fontWeight: '700' }],
        'headline-xs': ['16px', { lineHeight: '22px', fontWeight: '600' }],
        'body-lg':     ['16px', { lineHeight: '24px', fontWeight: '400' }],
        'body-md':     ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'body-sm':     ['13px', { lineHeight: '18px', fontWeight: '400' }],
        'label-md':    ['12px', { lineHeight: '16px', letterSpacing: '0.02em', fontWeight: '600' }],
        'label-sm':    ['11px', { lineHeight: '14px', letterSpacing: '0.03em', fontWeight: '500' }],
      },
      // ── Border Radius ────────────────────────────────────────────────
      borderRadius: {
        'sm':      '0.125rem',   // 2px
        DEFAULT:   '0.25rem',    // 4px
        'md':      '0.375rem',   // 6px
        'lg':      '0.5rem',     // 8px
        'xl':      '0.75rem',    // 12px
        '2xl':     '1rem',       // 16px
        'full':    '9999px',
      },
      // ── Spacing ──────────────────────────────────────────────────────
      spacing: {
        'compact':           '4px',
        'inline-gap':        '8px',
        'stack-gap':         '12px',
        'container-padding': '16px',
        'section-margin':    '20px',
        'stack-md':          '16px',
        'stack-lg':          '32px',
        'base':              '8px',
        'stack-sm':          '8px',
        'gutter':            '24px',
      },
      // ── Animation ────────────────────────────────────────────────────
      keyframes: {
        'spin-once': {
          '0%':   { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'pulse-ring': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(74, 222, 128, 0.4)' },
          '50%':       { boxShadow: '0 0 0 6px rgba(74, 222, 128, 0)' },
        },
        'slide-in': {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-left': {
          '0%':   { opacity: '0', transform: 'translateX(-16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'loading-bar': {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
      },
      animation: {
        'spin-once':   'spin-once 0.6s ease-in-out',
        'pulse-ring':  'pulse-ring 2s ease-in-out infinite',
        'slide-in':      'slide-in 0.3s ease-out',
        'slide-in-left': 'slide-in-left 0.25s ease-out',
        'loading-bar':   'loading-bar 1.5s ease-in-out infinite',
      },
      // ── Box Shadow (3D tactile) ───────────────────────────────────────
      boxShadow: {
        'tactile':        '0 4px 0 0 rgba(0,0,0,0.4), inset 0 1px 0 0 rgba(255,255,255,0.1)',
        'tactile-gold':   '0 6px 0 0 #14532d, 0 8px 15px rgba(0,0,0,0.3)',
        'tactile-active': '0 0 0 2px #4ade80, 0 4px 0 0 rgba(0,0,0,0.4)',
        'card':           '0 4px 0 0 rgba(0,0,0,0.3)',
      },
    },
  },
  plugins: [],
};
