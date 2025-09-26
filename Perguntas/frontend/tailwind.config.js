/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
    '../templates/**/*.html',
    '../../questions/templates/**/*.html'
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          base: '#0f172a',
          hover: '#1e293b',
          border: '#334155'
        }
      }
    }
  },
  plugins: []
}
