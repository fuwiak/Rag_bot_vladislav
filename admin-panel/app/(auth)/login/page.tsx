'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()

  // Автоматически перенаправляем на dashboard без проверки авторизации
  useEffect(() => {
    // Устанавливаем фиктивный токен для совместимости
    if (typeof window !== 'undefined' && !localStorage.getItem('token')) {
      localStorage.setItem('token', 'auto-login-token')
    }
    // Немедленно перенаправляем на dashboard
        router.push('/dashboard')
  }, [router])
  // Показываем только загрузку во время редиректа
  return (
    <div className="min-h-screen flex items-center justify-center bg-fb-gray">
        <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-fb-blue mb-4"></div>
        <p className="text-fb-text-secondary text-lg">Перенаправление...</p>
      </div>
    </div>
  )
}

