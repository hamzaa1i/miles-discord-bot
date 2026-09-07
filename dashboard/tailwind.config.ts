import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Veloura design system (PART 2 of the dashboard spec)
        veloura: {
          pink: '#FFC0CB',
          'pink-soft': '#F4A8B8',
          lavender: '#E6E6FA',
          'lavender-dim': '#C3C3E5',
          navy: '#1A1D29',
          'navy-deep': '#12141D',
          card: '#242938',
          'card-hover': '#2B3145',
          border: '#333A4E',
          text: '#F5F5F5',
          muted: '#9CA3AF',
          success: '#A8E6CF',
          danger: '#F4A8A8',
        },
      },
      borderRadius: {
        DEFAULT: '12px',
        card: '16px',
      },
      fontFamily: {
        heading: ['"Playfair Display"', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 24px rgba(255, 192, 203, 0.15)',
        'glow-strong': '0 0 32px rgba(230, 230, 250, 0.22)',
        soft: '0 4px 16px rgba(0, 0, 0, 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.35s ease-out',
        'float-slow': 'floatSlow 7s ease-in-out infinite',
        'pulse-soft': 'pulseSoft 2.4s ease-in-out infinite',
        rise: 'rise 0.5s ease-out both',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        floatSlow: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
        rise: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
