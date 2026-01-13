'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        // Данные считаются свежими 30 минут
        staleTime: 30 * 60 * 1000, // 30 минут
        // Данные остаются в кэше 24 часа
        gcTime: 24 * 60 * 60 * 1000, // 24 часа (раньше называлось cacheTime)
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

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
