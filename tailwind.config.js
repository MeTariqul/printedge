/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        /* Base canvas colors - light theme foundation */
        canvas: {
          DEFAULT: '#f8fafc',
          alt: '#ffffff',
          darker: '#f1f5f9',
        },
        /* Text colors with guaranteed contrast on light surfaces */
        text: {
          primary: '#0f172a',    /* 15:1 on #ffffff */
          secondary: '#475569',  /* 7.5:1 on #ffffff */
          muted: '#64748b',      /* 4.5:1 on #ffffff */
          disabled: '#94a3b8',
        },
        /* Surface colors for cards, inputs, etc. */
        surface: {
          DEFAULT: '#ffffff',    /* Main card bg */
          elevated: '#ffffff',   /* Slightly elevated surfaces */
          border: '#e2e8f0',     /* Card borders */
          input: '#ffffff',      /* Input backgrounds */
        },
        /* Primary accent - blue */
        primary: {
          DEFAULT: '#2563eb',
          light: '#3b82f6',
          dark: '#1d4ed8',
          glow: 'rgba(37, 99, 235, 0.12)',
        },
        /* Status colors - designed for 4.5:1+ contrast on white */
        success: {
          DEFAULT: '#059669',
          text: '#047857',
          bg: 'rgba(5, 150, 105, 0.1)',
          border: 'rgba(5, 150, 105, 0.2)',
        },
        warning: {
          DEFAULT: '#d97706',
          text: '#b45309',
          bg: 'rgba(217, 119, 6, 0.1)',
          border: 'rgba(217, 119, 6, 0.2)',
        },
        danger: {
          DEFAULT: '#dc2626',
          text: '#b91c1c',
          bg: 'rgba(220, 38, 38, 0.08)',
          border: 'rgba(220, 38, 38, 0.2)',
        },
        info: {
          DEFAULT: '#2563eb',
          text: '#1d4ed8',
          bg: 'rgba(37, 99, 235, 0.08)',
          border: 'rgba(37, 99, 235, 0.2)',
        },
        /* Semantic aliases - brand stays blue */
        brand: {
          400: '#3b82f6',
          500: '#2563eb',
          600: '#1d4ed8',
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
