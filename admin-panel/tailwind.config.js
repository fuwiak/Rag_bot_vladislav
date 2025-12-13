/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'fb-blue': '#1877f2',
        'fb-blue-dark': '#166fe5',
        'fb-blue-hover': '#42a5f5',
        'fb-gray': '#f0f2f5',
        'fb-gray-dark': '#e4e6eb',
        'fb-text': '#050505',
        'fb-text-secondary': '#65676b',
      },
    },
  },
  plugins: [],
}

