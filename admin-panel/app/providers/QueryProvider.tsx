'use client'

import { QueryClient } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { useState } from 'react'

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
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
    })
    return client
  })

  const [persister] = useState(() => {
    // Создаем persister только на клиенте (в браузере)
    if (typeof window !== 'undefined') {
      return createSyncStoragePersister({
        storage: window.localStorage,
        key: 'REACT_QUERY_OFFLINE_CACHE',
        serialize: JSON.stringify,
        deserialize: JSON.parse,
      })
    }
    return null
  })

  // Всегда используем PersistQueryClientProvider, даже если persister null (на сервере)
  // PersistQueryClientProvider корректно обрабатывает случай, когда persister отсутствует
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={
        persister
          ? {
              persister,
              maxAge: 7 * 24 * 60 * 60 * 1000, // 7 дней в localStorage
              buster: '', // Версия кэша (можно менять для инвалидации)
            }
          : undefined
      }
    >
      {children}
    </PersistQueryClientProvider>
  )
}
