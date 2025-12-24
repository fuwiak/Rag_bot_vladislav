/**
 * Простой кэш данных для фронтенда
 * Использует stale-while-revalidate паттерн
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number // Time to live в миллисекундах
}

class DataCache {
  private cache: Map<string, CacheEntry<any>> = new Map()
  private defaultTTL = 5 * 60 * 1000 // 5 минут по умолчанию

  /**
   * Получить данные из кэша
   * @param key Ключ кэша
   * @returns Данные или null если нет в кэше или истек срок
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key)
    if (!entry) {
      return null
    }

    const now = Date.now()
    if (now - entry.timestamp > entry.ttl) {
      // Данные устарели, но возвращаем их (stale-while-revalidate)
      return entry.data
    }

    return entry.data
  }

  /**
   * Проверить, есть ли данные в кэше (даже устаревшие)
   */
  has(key: string): boolean {
    return this.cache.has(key)
  }

  /**
   * Сохранить данные в кэш
   * @param key Ключ кэша
   * @param data Данные для сохранения
   * @param ttl Time to live в миллисекундах (по умолчанию 5 минут)
   */
  set<T>(key: string, data: T, ttl?: number): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTTL,
    })
  }

  /**
   * Удалить данные из кэша
   */
  delete(key: string): void {
    this.cache.delete(key)
  }

  /**
   * Очистить весь кэш
   */
  clear(): void {
    this.cache.clear()
  }

  /**
   * Очистить устаревшие записи
   */
  cleanup(): void {
    const now = Date.now()
    for (const [key, entry] of this.cache.entries()) {
      // Удаляем только очень старые записи (старше 2x TTL)
      if (now - entry.timestamp > entry.ttl * 2) {
        this.cache.delete(key)
      }
    }
  }
}

// Глобальный экземпляр кэша
export const cache = new DataCache()

// Периодическая очистка устаревших записей
if (typeof window !== 'undefined') {
  setInterval(() => {
    cache.cleanup()
  }, 10 * 60 * 1000) // Каждые 10 минут
}

// Ключи для кэша
export const cacheKeys = {
  projects: 'projects',
  project: (id: string) => `project:${id}`,
  projectDocuments: (id: string) => `project:${id}:documents`,
  projectUsers: (id: string) => `project:${id}:users`,
  botsInfo: 'bots:info',
  models: 'models:available',
  globalSettings: 'models:global-settings',
  allUsers: 'users:all',
}

