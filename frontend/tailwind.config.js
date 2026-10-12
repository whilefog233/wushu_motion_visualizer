/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // 深空紫底色阶
        space: {
          950: '#070414',
          900: '#0c0720',
          850: '#110a2c',
          800: '#170f38',
          700: '#1f1548',
          600: '#2b1d60',
        },
        // 青绿高亮
        mint: {
          300: '#7ff5e2',
          400: '#3ff0cf',
          500: '#14e2bd',
          600: '#08c2a4',
        },
        // 辅助
        violet: {
          glow: '#8b7bff',
        },
        warn: '#ffb547',
        danger: '#ff5470',
        ink: {
          100: '#e9ecff',
          300: '#b9bede',
          500: '#8a8fb5',
          700: '#5d6185',
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'mint-glow': '0 0 18px rgba(20, 226, 189, 0.35)',
        'panel': '0 8px 40px rgba(0, 0, 0, 0.45)',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2.2s ease-in-out infinite',
        sweep: 'sweep 2.5s linear infinite',
      },
    },
  },
  plugins: [],
}
