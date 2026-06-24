/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        /* Base canvas colors */
        canvas: {
          DEFAULT: 'var(--pe-color-bg)',
          alt: 'var(--pe-color-surface)',
          darker: 'var(--pe-color-surface-soft)',
        },
        /* Text colors */
        text: {
          DEFAULT: 'var(--pe-color-text)',
          primary: 'var(--pe-color-text-strong)',
          secondary: 'var(--pe-color-text)',
          muted: 'var(--pe-color-text-muted)',
          disabled: '#94a3b8',
        },
        /* Surface colors */
        surface: {
          DEFAULT: 'var(--pe-color-surface)',
          elevated: 'var(--pe-color-surface-raised)',
          border: 'var(--pe-color-border)',
          input: 'var(--pe-color-surface)',
        },
        /* Primary accent */
        primary: {
          DEFAULT: 'var(--pe-color-primary)',
          light: 'var(--pe-color-primary-soft)',
          dark: 'var(--pe-color-primary-hover)',
          glow: 'var(--pe-color-focus)',
        },
        /* Status colors */
        success: {
          DEFAULT: 'var(--pe-status-success)',
          text: 'var(--pe-status-success)',
          bg: 'rgba(5, 150, 105, 0.1)',
          border: 'rgba(5, 150, 105, 0.2)',
        },
        warning: {
          DEFAULT: 'var(--pe-status-warning)',
          text: 'var(--pe-status-warning)',
          bg: 'rgba(217, 119, 6, 0.1)',
          border: 'rgba(217, 119, 6, 0.2)',
        },
        danger: {
          DEFAULT: 'var(--pe-status-danger)',
          text: 'var(--pe-status-danger)',
          bg: 'rgba(220, 38, 38, 0.08)',
          border: 'rgba(220, 38, 38, 0.2)',
        },
        info: {
          DEFAULT: 'var(--pe-status-info)',
          text: 'var(--pe-status-info)',
          bg: 'rgba(37, 99, 235, 0.08)',
          border: 'rgba(37, 99, 235, 0.2)',
        },
        /* Semantic aliases */
        brand: {
          400: 'var(--pe-color-primary)',
          500: 'var(--pe-color-primary)',
          600: 'var(--pe-color-primary-hover)',
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
        card: '0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04)',
        cardHover: '0 4px 12px rgba(15, 23, 42, 0.1), 0 2px 4px rgba(15, 23, 42, 0.06)',
        glow: '0 0 20px rgba(37, 99, 235, 0.15)',
        input: '0 1px 2px rgba(15, 23, 42, 0.05)',
        sm: '0 1px 2px rgba(15, 23, 42, 0.05)',
        md: '0 4px 6px rgba(15, 23, 42, 0.07)',
        lg: '0 10px 15px rgba(15, 23, 42, 0.1)',
        xl: '0 20px 25px rgba(15, 23, 42, 0.1)',
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
        'card-gradient': 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
      },
    },
  },
  plugins: [],
}
