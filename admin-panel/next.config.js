/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  env: {
    BACKEND_URL: process.env.BACKEND_URL || 'http://localhost:8000',
  },
}

module.exports = nextConfig

