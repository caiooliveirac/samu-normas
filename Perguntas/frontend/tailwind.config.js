/** @type {import('tailwindcss').Config} */
function hexToRgb(hex) {
  const clean = hex.replace('#', '').trim()
  const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean
  const r = Number.parseInt(full.slice(0, 2), 16)
  const g = Number.parseInt(full.slice(2, 4), 16)
  const b = Number.parseInt(full.slice(4, 6), 16)
  return { r, g, b }
}

function rgbToHex({ r, g, b }) {
  const to = (n) => n.toString(16).padStart(2, '0')
  return `#${to(r)}${to(g)}${to(b)}`
}

function mix(baseHex, mixHex, weight) {
  const base = hexToRgb(baseHex)
  const mixColor = hexToRgb(mixHex)
  const w = Math.max(0, Math.min(1, weight))
  return rgbToHex({
    r: Math.round(base.r * (1 - w) + mixColor.r * w),
    g: Math.round(base.g * (1 - w) + mixColor.g * w),
    b: Math.round(base.b * (1 - w) + mixColor.b * w),
  })
}

function makeScale(baseHex) {
  const white = '#ffffff'
  const black = '#000000'
  return {
    50: mix(baseHex, white, 0.92),
    100: mix(baseHex, white, 0.84),
    200: mix(baseHex, white, 0.72),
    300: mix(baseHex, white, 0.58),
    400: mix(baseHex, white, 0.40),
    500: baseHex,
    600: mix(baseHex, black, 0.12),
    700: mix(baseHex, black, 0.26),
    800: mix(baseHex, black, 0.40),
    900: mix(baseHex, black, 0.54),
  }
}

export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
    // Templates Django globbed relativos ao diretório frontend
    '../templates/**/*.html',                 // templates raiz
    '../../questions/templates/**/*.html',    // app questions
    '../../faq/templates/**/*.html'           // app faq
  ],
  theme: {
    extend: {
      colors: {
        // Identidade institucional (Prefeitura)
        brand: {
          DEFAULT: '#C73227',
          ...makeScale('#C73227'),
        },
        // Destaque secundário / status / apoio
        accent: {
          DEFAULT: '#DF4E24',
          ...makeScale('#DF4E24'),
        },
      }
    }
  },
  plugins: []
}
