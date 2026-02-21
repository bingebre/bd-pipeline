/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,jsx}', './components/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cc: {
          cream: '#FAF8F5',
          green: '#2C5F2D',
          'green-light': '#3D7B3E',
          charcoal: '#36454F',
          gold: '#C9A84C',
          teal: '#1B4D4E',
        },
      },
      fontFamily: {
        serif: ['Newsreader', 'Georgia', 'serif'],
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};
