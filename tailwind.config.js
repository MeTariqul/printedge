/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        /* Base canvas colors - dark theme foundation */
        canvas: {
          DEFAULT: '#0f172a',
          alt: '#111827',
          darker: '#0a0f1a',
        },
        /* Text colors with guaranteed contrast */
        text: {
          primary: '#f8fafc',    /* 4.5:1 on #0f172a */
          secondary: '#e2e8f0',  /* 3.5:1 on #0f172a */
          muted: '#94a3b8',      /* 2.5:1 - use on #1e293b surfaces only */
          disabled: '#64748b',   /* Disabled state */
        },
        /* Surface colors for cards, inputs, etc. */
        surface: {
          DEFAULT: '#1e293b',    /* Main card bg - #e2e8f0 has 4.5:1 contrast */
          elevated: '#253244',   /* Slightly lighter for hover states */
          border: '#334155',     /* Card borders */
          input: '#111827',      /* Input backgrounds - #f8fafc has 12:1 contrast */
        },
        /* Primary accent - cyan */
        primary: {
          DEFAULT: '#06b6d4',
          light: '#22d3ee',
          dark: '#0891b4',
          glow: 'rgba(6, 182, 212, 0.15)',
        },
        /* Status colors - designed for 4.5:1+ contrast on #1e293b */
        success: {
          DEFAULT: '#22c55e',
          text: '#86efac',
          bg: 'rgba(34, 197, 94, 0.1)',
          border: 'rgba(34, 197, 94, 0.2)',
        },
        warning: {
          DEFAULT: '#f59e0b',
          text: '#fbbf24',
          bg: 'rgba(245, 158, 11, 0.1)',
          border: 'rgba(245, 158, 11, 0.2)',
        },
        danger: {
          DEFAULT: '#ef4444',
          text: '#fca5a5',
          bg: 'rgba(239, 68, 68, 0.1)',
          border: 'rgba(239, 68, 68, 0.2)',
        },
        info: {
          DEFAULT: '#3b82f6',
          text: '#93c5fd',
          bg: 'rgba(59, 130, 246, 0.1)',
          border: 'rgba(59, 130, 246, 0.2)',
        },
        /* Semantic aliases */
        brand: {
          400: '#06b6d4',
          500: '#0891b4',
          600: '#0e7490',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        xs: ['12px', { lineHeight: '1.4' }],
        sm: ['14px', { lineHeight: '1.5' }],
        base: ['16px', { lineHeight: '1.6' }],
        lg: ['18px', { lineHeight: '1.5' }],
        xl: ['20px', { lineHeight: '1.4' }],
        '2xl': ['24px', { lineHeight: '1.3' }],
        '3xl': ['30px', { lineHeight: '1.2' }],
      },
      boxShadow: {
        card: '0 4px 24px rgba(0, 0, 0, 0.35)',
        cardHover: '0 8px 32px rgba(0, 0, 0, 0.45)',
        glow: '0 0 20px rgba(6, 182, 212, 0.15)',
        input: '0 2px 8px rgba(0, 0, 0, 0.2)',
      },
      borderRadius: {
        card: '12px',
        button: '10px',
        badge: '999px',
      },
      transitionDuration: {
        DEFAULT: '200ms',
      },
      transitionTimingFunction: {
        DEFAULT: 'ease-in-out',
      },
      backgroundImage: {
        'card-gradient': 'linear-gradient(135deg, rgba(30,41,59,0.95) 0%, rgba(17,24,39,0.98) 100%)',
      },
    },
  },
  plugins: [],
}