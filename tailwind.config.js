/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
    "./routes/**/*.py",
    "./models/**/*.py",
    "./services/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        triton: {
          50: '#eef6f4',
          100: '#d8ebe7',
          500: '#367b71',
          600: '#1e5a52',
          700: '#194a44',
          900: '#102f2c',
        }
      },
      boxShadow: {
        '2xs': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [],
}
