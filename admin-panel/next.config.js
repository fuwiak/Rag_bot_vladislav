/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Next.js automatically exposes NEXT_PUBLIC_* environment variables to the browser
  // Use NEXT_PUBLIC_BACKEND_URL for client-side access
  // Railway will provide this via environment variables
  env: {
    // Явно указываем переменные для встраивания в код
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'https://ragbotvladislav-backend.up.railway.app',
    NEXT_PUBLIC_USE_MOCK_API: process.env.NEXT_PUBLIC_USE_MOCK_API || 'false',
  },
  // Ensure proper routing in production
  trailingSlash: false,
}

module.exports = nextConfig












