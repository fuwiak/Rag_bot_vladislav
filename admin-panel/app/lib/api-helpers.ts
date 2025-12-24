// Вспомогательные функции для работы с API
// Поддерживают переключение между реальным API и моками

// Кэш для конфигурации (загружается один раз)
let configCache: { backendUrl: string; useMockApi: boolean } | null = null
let configPromise: Promise<{ backendUrl: string; useMockApi: boolean }> | null = null

/**
 * Загрузить конфигурацию из API route (fallback если переменные не встроились)
 */
async function loadConfig(): Promise<{ backendUrl: string; useMockApi: boolean }> {
  if (configCache) {
    return configCache
  }
  
  if (configPromise) {
    return configPromise
  }
  
  configPromise = (async () => {
    try {
      // Загружаем конфигурацию из API route (читает переменные на сервере)
      const response = await fetch('/api/config', {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache',
        },
      })
      if (response.ok) {
        const config = await response.json()
        // Убираем trailing slash
        const backendUrl = (config.backendUrl || '').replace(/\/+$/, '')
        
        // Проверяем, что получили валидный URL
        if (backendUrl && backendUrl !== 'https://ragbotvladislav-backend.up.railway.app' && !backendUrl.includes('localhost')) {
          configCache = {
            backendUrl,
            useMockApi: config.useMockApi === true || config.useMockApi === 'true',
          }
          console.log('[API Helpers] Config loaded from API route:', configCache)
          return configCache
        }
      }
    } catch (err) {
      console.warn('[API Helpers] Failed to load config from API route:', err)
    }
    
    // Fallback к переменным окружения или дефолтным значениям
    const backendUrl = (typeof window !== 'undefined' 
      ? (window as any).__NEXT_DATA__?.env?.NEXT_PUBLIC_BACKEND_URL
      : null) || process.env.NEXT_PUBLIC_BACKEND_URL || 'https://ragbotvladislav-backend.up.railway.app'
    
    const useMockApi = (typeof window !== 'undefined'
      ? (window as any).__NEXT_DATA__?.env?.NEXT_PUBLIC_USE_MOCK_API === 'true'
      : false) || process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
    
    const fallbackConfig = {
      backendUrl: backendUrl.replace(/\/+$/, ''),
      useMockApi,
    }
    console.warn('[API Helpers] Using fallback config:', fallbackConfig)
    return fallbackConfig
  })()
  
  return configPromise
}

/**
 * Получить базовый URL для API запросов
 */
export async function getBackendUrl(): Promise<string> {
  // Сначала пробуем получить из встроенных переменных Next.js
  let API_BASE_URL: string | undefined
  let USE_MOCK_API: boolean | undefined
  
  if (typeof window !== 'undefined') {
    // В браузере переменные доступны через __NEXT_DATA__ или встроены в код
    const nextData = (window as any).__NEXT_DATA__
    API_BASE_URL = nextData?.env?.NEXT_PUBLIC_BACKEND_URL
    USE_MOCK_API = nextData?.env?.NEXT_PUBLIC_USE_MOCK_API === 'true'
  }
  
  // Если не нашли, используем process.env (для SSR или если встроено)
  if (!API_BASE_URL) {
    API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL
  }
  if (USE_MOCK_API === undefined) {
    USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  }
  
  // Если переменные не найдены, загружаем из API route (runtime конфигурация)
  // Это критично для Railway, где переменные могут не встроиться в сборку
  if (!API_BASE_URL || API_BASE_URL.includes('localhost')) {
    try {
      const config = await loadConfig()
      if (config.backendUrl && !config.backendUrl.includes('localhost')) {
        API_BASE_URL = config.backendUrl
        USE_MOCK_API = config.useMockApi
      }
    } catch (err) {
      console.warn('[API Helpers] Failed to load config from API route:', err)
    }
  }
  
  // Убеждаемся, что у нас есть URL
  if (!API_BASE_URL) {
    API_BASE_URL = 'https://ragbotvladislav-backend.up.railway.app'
  }
  
  // Убираем trailing slash
  API_BASE_URL = API_BASE_URL.replace(/\/+$/, '')
  
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
 * Синхронная версия (использует кэш или дефолтные значения)
 * Используйте только если уверены, что конфигурация уже загружена
 */
export function getBackendUrlSync(): string {
  if (configCache) {
    if (configCache.useMockApi && typeof window !== 'undefined') {
      return '/api/mock'
    }
    return configCache.backendUrl
  }
  
  // Пробуем получить из встроенных переменных
  let API_BASE_URL: string | undefined
  
  if (typeof window !== 'undefined') {
    const nextData = (window as any).__NEXT_DATA__
    API_BASE_URL = nextData?.env?.NEXT_PUBLIC_BACKEND_URL
  }
  
  API_BASE_URL = API_BASE_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'https://ragbotvladislav-backend.up.railway.app'
  API_BASE_URL = API_BASE_URL.replace(/\/+$/, '')
  
  const USE_MOCK_API = (typeof window !== 'undefined'
    ? (window as any).__NEXT_DATA__?.env?.NEXT_PUBLIC_USE_MOCK_API === 'true'
    : false) || process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  
  if (USE_MOCK_API && typeof window !== 'undefined') {
    return '/api/mock'
  }
  
  return API_BASE_URL
}

/**
 * Преобразовать endpoint для моков
 */
export function transformEndpoint(endpoint: string, useMockApi?: boolean): string {
  // Если useMockApi передан явно, используем его, иначе проверяем переменную окружения
  let USE_MOCK_API: boolean
  if (useMockApi !== undefined) {
    USE_MOCK_API = useMockApi
  } else {
    USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true'
  }
  
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
 * Получить полный URL для API запроса (асинхронная версия)
 * Используйте эту функцию вместо прямого использования process.env.NEXT_PUBLIC_BACKEND_URL
 */
export async function getApiUrl(endpoint: string): Promise<string> {
  const baseUrl = await getBackendUrl()
  // Определяем, используем ли моки, на основе baseUrl
  const useMockApi = baseUrl.includes('/api/mock')
  const transformedEndpoint = transformEndpoint(endpoint, useMockApi)
  return `${baseUrl}${transformedEndpoint}`
}

/**
 * Получить полный URL для API запроса (синхронная версия)
 * Используйте только если уверены, что конфигурация уже загружена
 */
export function getApiUrlSync(endpoint: string): string {
  const baseUrl = getBackendUrlSync()
  const transformedEndpoint = transformEndpoint(endpoint)
  return `${baseUrl}${transformedEndpoint}`
}

/**
 * Выполнить API запрос с автоматическим добавлением токена авторизации
 * Используйте эту функцию вместо прямого fetch для всех API запросов
 */
export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const apiUrl = await getApiUrl(endpoint)
  
  // Получаем токен из localStorage (только в браузере)
  let token: string | null = null
  if (typeof window !== 'undefined') {
    token = localStorage.getItem('token')
  }
  
  // Формируем заголовки
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  
  // Добавляем токен авторизации, если он есть
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  // Выполняем запрос
  return fetch(apiUrl, {
    ...options,
    headers,
  })
}

