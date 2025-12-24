// Вспомогательные функции для работы с API
// Поддерживают переключение между реальным API и моками

/**
 * Получить базовый URL для API запросов
 */
export function getBackendUrl(): string {
  // В браузере переменные окружения доступны через window.__ENV__ или process.env
  // Next.js встраивает NEXT_PUBLIC_* переменные в код во время сборки
  const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  
  // Получаем URL из переменной окружения
  // В браузере это будет встроено в код при сборке
  // На сервере это будет из process.env
  let API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  
  // Убираем trailing slash, если есть
  API_BASE_URL = API_BASE_URL.replace(/\/+$/, '')
  
  // Отладочная информация (только в development)
  if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    console.log('[API Helpers] Backend URL:', API_BASE_URL)
    console.log('[API Helpers] Use Mock API:', USE_MOCK_API)
    console.log('[API Helpers] NEXT_PUBLIC_BACKEND_URL:', process.env.NEXT_PUBLIC_BACKEND_URL)
  }
  
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
    let transformed = endpoint.replace('/api/', '/')
    
    // Специальная обработка для документов:
    // /api/documents/{projectId} -> /documents/project/{projectId}
    // /api/documents/{projectId}/upload -> /documents/project/{projectId}/upload
    // /api/documents/{id} (DELETE) -> /documents/{id} (остается как есть)
    if (transformed.startsWith('/documents/')) {
      const uploadMatch = transformed.match(/^\/documents\/([^\/]+)\/upload$/)
      if (uploadMatch) {
        // Путь для загрузки: /documents/{projectId}/upload -> /documents/project/{projectId}/upload
        transformed = `/documents/project/${uploadMatch[1]}/upload`
      } else {
        // Проверяем, это получение документов проекта или удаление конкретного документа
        const documentsMatch = transformed.match(/^\/documents\/([^\/]+)$/)
        if (documentsMatch) {
          // Это путь для получения документов проекта (GET)
          // В реальном API это /api/documents/{projectId}, в моках /documents/project/{projectId}
          transformed = `/documents/project/${documentsMatch[1]}`
        }
        // Если это /documents/{id} с методом DELETE, оставляем как есть
      }
    }
    
    return transformed
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

