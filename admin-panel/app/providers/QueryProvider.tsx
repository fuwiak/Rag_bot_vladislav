'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { useState, useEffect } from 'react'

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        // Данные считаются свежими 30 минут
        staleTime: 30 * 60 * 1000, // 30 минут
        // Данные остаются в кэше 7 дней (для долгоживущего кэша)
        gcTime: 7 * 24 * 60 * 60 * 1000, // 7 дней
        // Повторные попытки при ошибке
        retry: 1,
        // Не обновлять данные при фокусе окна
        refetchOnWindowFocus: false,
        // Не обновлять данные при переподключении
        refetchOnReconnect: false,
        // Не обновлять данные при монтировании, если данные свежие
        refetchOnMount: false,
      },
    },
  }))

  const [persister, setPersister] = useState<any>(null)

  useEffect(() => {
    // Создаем persister только на клиенте
    if (typeof window !== 'undefined') {
      const localStoragePersister = createSyncStoragePersister({
        storage: window.localStorage,
        key: 'REACT_QUERY_OFFLINE_CACHE',
        // Сериализация/десериализация для localStorage
        serialize: JSON.stringify,
        deserialize: JSON.parse,
      })
      setPersister(localStoragePersister)
    }
  }, [])

  // Если persister еще не готов, используем обычный провайдер
  if (!persister) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }

  // Используем PersistQueryClientProvider для сохранения кэша в localStorage
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 7 * 24 * 60 * 60 * 1000, // 7 дней в localStorage
        buster: '', // Версия кэша (можно менять для инвалидации)
      }}
    >
      {children}
    </PersistQueryClientProvider>
  )
}
