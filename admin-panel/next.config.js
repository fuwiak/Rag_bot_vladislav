/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Next.js automatically exposes NEXT_PUBLIC_* environment variables to the browser
  // Use NEXT_PUBLIC_BACKEND_URL for client-side access
  // Railway will provide this via environment variables
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'http://localhost:8000',
  },
  // Ensure proper routing in production
  trailingSlash: false,
}

module.exports = nextConfig












