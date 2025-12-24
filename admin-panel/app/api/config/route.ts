import { NextResponse } from 'next/server'

/**
 * API route для получения конфигурации backend URL
 * Используется как fallback, если NEXT_PUBLIC_* переменные не встроились в код
 * 
 * Этот route читает переменные окружения на сервере и возвращает их клиенту
 */
export async function GET() {
  // Получаем переменные окружения с сервера
  // На сервере они всегда доступны, даже если не встроились в клиентский код
  let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'http://localhost:8000'
  const useMockApi = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  
  // Убираем trailing slash
  backendUrl = backendUrl.replace(/\/+$/, '')
  
  // Убираем кавычки, если Railway их добавил
  backendUrl = backendUrl.replace(/^["']|["']$/g, '')
  
  return NextResponse.json({
    backendUrl,
    useMockApi,
  }, {
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  })
}

