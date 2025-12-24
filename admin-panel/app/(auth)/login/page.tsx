'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true) // Начинаем с loading=true
  const [autoLoginAttempted, setAutoLoginAttempted] = useState(false)
  const router = useRouter()

  // Автоматический вход при загрузке страницы
  useEffect(() => {
    // Проверяем, нет ли уже токена
    const token = localStorage.getItem('token')
    if (token) {
      console.log('Token already exists, redirecting to dashboard')
      router.push('/dashboard')
      return
    }

    // Автоматический вход
    const autoLogin = async () => {
      if (autoLoginAttempted) return
      setAutoLoginAttempted(true)
      
      try {
        // Получаем URL из переменной окружения или используем дефолтный
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 
                          (typeof window !== 'undefined' ? window.location.origin.replace(/:\d+$/, ':8000') : 'http://localhost:8000')
        
        console.log('='.repeat(60))
        console.log('🔐 AUTO-LOGIN DEBUG INFO')
        console.log('='.repeat(60))
        console.log('📍 Environment:')
        console.log('  - NEXT_PUBLIC_BACKEND_URL:', process.env.NEXT_PUBLIC_BACKEND_URL || 'NOT SET')
        console.log('  - NODE_ENV:', process.env.NODE_ENV || 'NOT SET')
        console.log('  - Window location:', typeof window !== 'undefined' ? window.location.href : 'N/A')
        console.log('  - Computed backendUrl:', backendUrl)
        console.log('  - Full login URL:', `${backendUrl}/api/auth/login`)
        console.log('')
        
        // Тест 1: Проверка доступности backend
        console.log('🧪 TEST 1: Health check')
        try {
          const healthUrl = `${backendUrl}/health`
          console.log('  - URL:', healthUrl)
          const healthCheck = await fetch(healthUrl, { 
            method: 'GET',
            signal: AbortSignal.timeout(5000)
          })
          console.log('  - Status:', healthCheck.status)
          const healthData = await healthCheck.text()
          console.log('  - Response:', healthData)
          console.log('  ✅ Health check: OK')
        } catch (healthErr) {
          console.error('  ❌ Health check: FAILED')
          console.error('  - Error:', healthErr)
          console.error('  - Error type:', healthErr instanceof Error ? healthErr.constructor.name : typeof healthErr)
          console.error('  - Error message:', healthErr instanceof Error ? healthErr.message : String(healthErr))
        }
        console.log('')
        
        // Тест 2: Проверка CORS
        console.log('🧪 TEST 2: CORS check')
        try {
          const corsUrl = `${backendUrl}/api/test-cors`
          console.log('  - URL:', corsUrl)
          const corsCheck = await fetch(corsUrl, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
          })
          console.log('  - Status:', corsCheck.status)
          console.log('  ✅ CORS check: OK')
        } catch (corsErr) {
          console.error('  ❌ CORS check: FAILED')
          console.error('  - Error:', corsErr)
          if (corsErr instanceof TypeError && corsErr.message.includes('CORS')) {
            console.error('  ⚠️ CORS policy blocked the request!')
          }
        }
        console.log('')
        
        // Тест 3: Логин
        console.log('🧪 TEST 3: Login attempt')
        const loginUrl = `${backendUrl}/api/auth/login`
        console.log('  - URL:', loginUrl)
        console.log('  - Method: POST')
        console.log('  - Body:', JSON.stringify({ username: 'admin', password: 'any' }))
        
        const response = await fetch(loginUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ username: 'admin', password: 'any' }),
          signal: AbortSignal.timeout(10000)
        })

        console.log('  - Response status:', response.status)
        console.log('  - Response statusText:', response.statusText)
        console.log('  - Response headers:', Object.fromEntries(response.headers.entries()))
        
        const responseText = await response.text()
        console.log('  - Response body (raw):', responseText)
        
        if (response.ok) {
          try {
            const data = JSON.parse(responseText)
            console.log('  - Response body (parsed):', data)
            console.log('  ✅ Login: SUCCESS')
            console.log('  - Token received:', data.access_token ? 'YES' : 'NO')
            
            if (data.access_token) {
              localStorage.setItem('token', data.access_token)
              console.log('  💾 Token saved to localStorage')
              console.log('='.repeat(60))
              window.location.href = '/dashboard'
            } else {
              console.error('  ❌ Login: NO TOKEN IN RESPONSE')
              console.log('='.repeat(60))
              setError('Токен не получен от сервера')
              setLoading(false)
            }
          } catch (parseErr) {
            console.error('  ❌ Login: JSON PARSE ERROR')
            console.error('  - Error:', parseErr)
            console.log('='.repeat(60))
            setError(`Ошибка парсинга ответа: ${responseText.substring(0, 100)}`)
            setLoading(false)
          }
        } else {
          console.error('  ❌ Login: FAILED')
          console.error('  - Status:', response.status)
          console.error('  - Response:', responseText)
          console.log('='.repeat(60))
          setError(`Ошибка автоматического входа: ${response.status} - ${responseText.substring(0, 200)}`)
          setLoading(false)
        }
      } catch (err) {
        console.error('='.repeat(60))
        console.error('❌ AUTO-LOGIN ERROR')
        console.error('='.repeat(60))
        console.error('Error type:', err instanceof Error ? err.constructor.name : typeof err)
        console.error('Error name:', err instanceof Error ? err.name : 'N/A')
        console.error('Error message:', err instanceof Error ? err.message : String(err))
        console.error('Error stack:', err instanceof Error ? err.stack : 'N/A')
        console.error('Full error object:', err)
        console.error('='.repeat(60))
        
        const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка'
        
        // Более детальная информация об ошибке
        let detailedError = errorMessage
        if (err instanceof TypeError) {
          if (err.message.includes('fetch')) {
            detailedError = `Не удалось подключиться к backend. Проверьте NEXT_PUBLIC_BACKEND_URL в Railway. Текущий URL: ${process.env.NEXT_PUBLIC_BACKEND_URL || 'не установлен'}`
          } else if (err.message.includes('Failed to fetch')) {
            detailedError = `Сеть недоступна или CORS блокирует запрос. Backend URL: ${process.env.NEXT_PUBLIC_BACKEND_URL || 'не установлен'}`
          }
        } else if (err instanceof Error && err.name === 'AbortError') {
          detailedError = 'Таймаут подключения к серверу. Backend может быть недоступен или медленно отвечает.'
        } else if (err instanceof DOMException && err.name === 'AbortError') {
          detailedError = 'Запрос был отменен (таймаут). Проверьте доступность backend.'
        }
        
        setError(`Ошибка подключения: ${detailedError}`)
        setLoading(false)
      }
    }

    // Запускаем автоматический вход с небольшой задержкой
    const timer = setTimeout(() => {
      autoLogin()
    }, 100)

    return () => clearTimeout(timer)
  }, [router, autoLoginAttempted])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { getApiUrl } = await import('../../lib/api-helpers')
      const response = await fetch(getApiUrl('/api/auth/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: username || 'admin', password: password || 'admin' }),
      })

      if (response.ok) {
        const data = await response.json()
        localStorage.setItem('token', data.access_token)
        router.push('/dashboard')
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Ошибка авторизации')
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  if (loading && !error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fb-gray">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-fb-blue mb-4"></div>
          <p className="text-fb-text-secondary text-lg">Автоматический вход...</p>
          <p className="text-fb-text-secondary text-sm mt-2">Откройте консоль браузера (F12) для деталей</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-fb-gray">
      <div className="max-w-md w-full space-y-6 p-8 bg-white rounded-lg shadow-lg">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-fb-blue rounded-full mb-4">
            <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-4xl font-bold text-fb-blue mb-2">RAG Bot Admin</h1>
          <p className="text-fb-text-secondary text-lg">
            Войдите в свой аккаунт
          </p>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded">
              <p className="font-medium">{error}</p>
            </div>
          )}
          <div>
            <input
              id="username"
              name="username"
              type="text"
              required
              placeholder="Имя пользователя"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 border border-fb-gray-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
            />
          </div>
          <div>
            <input
              id="password"
              name="password"
              type="password"
              required
              placeholder="Пароль"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-fb-gray-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
            />
          </div>
          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-fb-blue hover:bg-fb-blue-dark text-white font-semibold rounded-lg shadow-md transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Вход...' : 'Войти'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

