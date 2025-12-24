import { NextResponse } from 'next/server'

/**
 * API route для получения конфигурации backend URL
 * Используется как fallback, если NEXT_PUBLIC_* переменные не встроились в код
 */
export async function GET() {
  return NextResponse.json({
    backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'http://localhost:8000',
    useMockApi: process.env.NEXT_PUBLIC_USE_MOCK_API === 'true',
  })
}

