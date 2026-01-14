/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
    // Templates Django globbed relativos ao diretório frontend
    '../templates/**/*.html',                 // templates raiz
    '../../questions/templates/**/*.html',    // app questions
    '../../scoreboard/templates/**/*.html',   // app scoreboard (ranking, etc.)
    '../../faq/templates/**/*.html'           // app faq
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#345271',
          50: '#f2f6f9',
          100: '#e4ecf3',
          200: '#c3d4e3',
          300: '#a2bcd3',
          400: '#6f90b6',
          500: '#345271', // principal
          600: '#2f4a66',
          700: '#273e55',
          800: '#203244',
          900: '#1a2938'
        }
      }
    }
  },
  plugins: []
}
