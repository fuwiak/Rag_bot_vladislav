// API клиент с поддержкой моков
const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

/**
 * Получить базовый URL для API запросов
 * Если включены моки, использует локальные Next.js API routes
 */
function getApiBaseUrl(): string {
  if (USE_MOCK_API) {
    // В режиме моков используем локальные API routes
    if (typeof window !== 'undefined') {
      // В браузере используем относительный путь
      return '/api/mock'
    }
    // На сервере (SSR) используем полный URL
    return process.env.NEXT_PUBLIC_APP_URL 
      ? `${process.env.NEXT_PUBLIC_APP_URL}/api/mock`
      : 'http://localhost:3000/api/mock'
  }
  return API_BASE_URL
}

/**
 * Преобразовать endpoint для моков
 * Например: /api/projects -> /projects
 */
function transformEndpointForMock(endpoint: string): string {
  if (!USE_MOCK_API) {
    return endpoint
  }
  
  // Убираем /api префикс, если есть
  if (endpoint.startsWith('/api/')) {
    return endpoint.replace('/api/', '/')
  }
  
  return endpoint
}

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const baseUrl = getApiBaseUrl()
  const transformedEndpoint = transformEndpointForMock(endpoint)
  const url = `${baseUrl}${transformedEndpoint}`
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  
  // В режиме моков не добавляем Authorization заголовок
  if (!USE_MOCK_API && typeof window !== 'undefined') {
    const token = localStorage.getItem('token')
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  })
  
  return response
}
