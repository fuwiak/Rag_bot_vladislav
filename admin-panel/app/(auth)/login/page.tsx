'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch } from '../../lib/api-helpers'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка авторизации' }))
        setError(errorData.detail || 'Неверное имя пользователя или пароль')
        setLoading(false)
        return
      }

      const data = await response.json()
      
      // Сохраняем токен
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', data.access_token)
    }

      // Перенаправляем на dashboard
        router.push('/dashboard')
    } catch (err) {
      console.error('Login error:', err)
      setError('Ошибка подключения к серверу')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-fb-gray">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-fb-blue rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-fb-text">RAG Bot Admin</h1>
            <p className="text-fb-text-secondary mt-2">Войдите в систему</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-fb-text mb-2">
                Имя пользователя
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-4 py-2 border border-fb-gray-dark rounded-lg focus:ring-2 focus:ring-fb-blue focus:border-transparent outline-none"
                placeholder="admin"
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-fb-text mb-2">
                Пароль
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 border border-fb-gray-dark rounded-lg focus:ring-2 focus:ring-fb-blue focus:border-transparent outline-none"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-fb-blue text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {loading ? (
                <>
                  <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Вход...
                </>
              ) : (
                'Войти'
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-fb-text-secondary">
            <p>По умолчанию: admin / admin</p>
          </div>
        </div>
      </div>
    </div>
  )
}
