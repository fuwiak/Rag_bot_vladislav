// Вспомогательные функции для работы с API
// Поддерживают переключение между реальным API и моками

/**
 * Получить базовый URL для API запросов
 */
export function getBackendUrl(): string {
  const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  
  if (USE_MOCK_API) {
    // В режиме моков используем локальные Next.js API routes
    if (typeof window !== 'undefined') {
      return '/api/mock'
    }
    // На сервере (SSR)
    return process.env.NEXT_PUBLIC_APP_URL 
      ? `${process.env.NEXT_PUBLIC_APP_URL}/api/mock`
      : 'http://localhost:3000/api/mock'
  }
  return API_BASE_URL
}

/**
 * Преобразовать endpoint для моков
 */
export function transformEndpoint(endpoint: string): string {
  const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  
  if (!USE_MOCK_API) {
    return endpoint
  }
  
  // Убираем /api префикс, если есть
  if (endpoint.startsWith('/api/')) {
    return endpoint.replace('/api/', '/')
  }
  
  return endpoint
}

/**
 * Получить полный URL для API запроса
 * Используйте эту функцию вместо прямого использования process.env.NEXT_PUBLIC_BACKEND_URL
 */
export function getApiUrl(endpoint: string): string {
  const baseUrl = getBackendUrl()
  const transformedEndpoint = transformEndpoint(endpoint)
  return `${baseUrl}${transformedEndpoint}`
}

