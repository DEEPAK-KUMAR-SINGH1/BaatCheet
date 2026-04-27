/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          500: '#667eea',
          600: '#5a6fd6',
          700: '#4a5bc2',
        },
        purple: {
          600: '#764ba2',
        }
      }
    }
  },
  plugins: []
}
