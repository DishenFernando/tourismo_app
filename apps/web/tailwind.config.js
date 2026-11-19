/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { ink: '#082739', pine: '#086d69', aqua: '#28b9ab', citrus: '#f3a536', cream: '#fcf9f3', coral: '#ee7b40' },
      fontFamily: { sans: ['Inter', 'Segoe UI', 'sans-serif'] },
      boxShadow: { card: '0 16px 42px rgba(6,53,60,.08)' }
    }
  },
  plugins: []
}
