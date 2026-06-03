/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        canvas: { DEFAULT: '#0f172a', alt: '#111827' },
        primary: { DEFAULT: '#06b6d4', light: '#22d3ee', dark: '#0891b2' },
        secondary: { DEFAULT: '#94a3b8' },
        accent: { DEFAULT: '#f97316', light: '#fb923c' },
        surface: {
          DEFAULT: '#1e293b',
          border: '#334155',
          muted: '#64748b',
        },
        text: { 
          DEFAULT: '#e2e8f0', 
          muted: '#94a3b8',
          secondary: '#cbd5e1',
        },
        placeholder: {
          DEFAULT: '#94a3b8',
        },
        brand: {
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 4px 24px rgba(0, 0, 0, 0.35)',
        glow: '0 0 20px rgba(6, 182, 212, 0.15)',
      },
      borderRadius: {
        card: '12px',
      },
      backgroundImage: {
        'card-gradient': 'linear-gradient(135deg, rgba(30,41,59,0.9) 0%, rgba(17,24,39,0.95) 100%)',
      },
    },
  },
  plugins: [],
};
