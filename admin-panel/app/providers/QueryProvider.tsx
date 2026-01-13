'use client'

import { QueryClient } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { useMemo } from 'react'

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useMemo(() => {
    return new QueryClient({
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
  }, [])

  const persister = useMemo(() => {
    // Создаем persister только на клиенте (в браузере)
    if (typeof window !== 'undefined') {
      try {
        return createSyncStoragePersister({
          storage: window.localStorage,
          key: 'REACT_QUERY_OFFLINE_CACHE',
          serialize: JSON.stringify,
          deserialize: JSON.parse,
        })
      } catch (error) {
        console.warn('Failed to create localStorage persister:', error)
        return null
      }
    }
    return null
  }, [])

  // Всегда используем PersistQueryClientProvider для стабильности структуры хуков
  // Если persister null, персистентность просто не будет работать, но провайдер останется стабильным
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
          : {
              // Фиктивный persister для TypeScript, но он не будет использоваться
              persister: {
                persistClient: async () => {},
                restoreClient: async () => undefined,
                removeClient: async () => {},
              } as any,
              maxAge: 0,
            }
      }
    >
      {children}
    </PersistQueryClientProvider>
  )
}
