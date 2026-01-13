import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import { apiFetch } from '../lib/api-helpers'

interface ApiQueryOptions<T> extends Omit<UseQueryOptions<T, Error>, 'queryFn' | 'queryKey'> {
  endpoint: string
  enabled?: boolean
}

export function useApiQuery<T = any>({
  endpoint,
  enabled = true,
  ...options
}: ApiQueryOptions<T>) {
  return useQuery<T, Error>({
    queryKey: [endpoint],
    queryFn: async () => {
      const response = await apiFetch(endpoint)
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }
      return response.json() as Promise<T>
    },
    enabled,
    // Длительное кэширование для статических данных
    staleTime: 30 * 60 * 1000, // 30 минут
    gcTime: 7 * 24 * 60 * 60 * 1000, // 7 дней (сохраняется в localStorage)
    ...options,
  })
}
