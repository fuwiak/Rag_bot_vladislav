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
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
        console.log('🔐 Auto-login attempt to:', `${backendUrl}/api/auth/login`)
        
        const response = await fetch(`${backendUrl}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ username: 'admin', password: 'any' }),
        })

        console.log('📡 Auto-login response status:', response.status)
        console.log('📡 Auto-login response headers:', Object.fromEntries(response.headers.entries()))

        if (response.ok) {
          const data = await response.json()
          console.log('✅ Auto-login success, token received:', data.access_token ? 'YES' : 'NO')
          
          if (data.access_token) {
            localStorage.setItem('token', data.access_token)
            console.log('💾 Token saved to localStorage')
            window.location.href = '/dashboard' // Используем window.location вместо router для надежности
          } else {
            console.error('❌ No token in response:', data)
            setError('Токен не получен от сервера')
            setLoading(false)
          }
        } else {
          const errorText = await response.text()
          console.error('❌ Auto-login failed:', response.status, errorText)
          setError(`Ошибка автоматического входа: ${response.status} - ${errorText}`)
          setLoading(false)
        }
      } catch (err) {
        console.error('❌ Auto-login error:', err)
        const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка'
        setError(`Ошибка подключения: ${errorMessage}`)
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
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const response = await fetch(`${backendUrl}/api/auth/login`, {
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

