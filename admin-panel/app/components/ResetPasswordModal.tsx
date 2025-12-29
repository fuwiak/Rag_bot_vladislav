'use client'

import { useState } from 'react'
import { apiFetch } from '../lib/api-helpers'

interface ResetPasswordModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function ResetPasswordModal({ isOpen, onClose }: ResetPasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    // Валидация
    if (newPassword !== confirmPassword) {
      setError('Новые пароли не совпадают')
      setLoading(false)
      return
    }

    if (newPassword.length < 1) {
      setError('Пароль не может быть пустым')
      setLoading(false)
      return
    }

    try {
      const response = await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка сброса пароля' }))
        setError(errorData.detail || 'Ошибка сброса пароля')
        setLoading(false)
        return
      }

      setSuccess('Пароль успешно изменен!')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      
      // Закрываем модальное окно через 2 секунды
      setTimeout(() => {
        onClose()
        setSuccess('')
      }, 2000)
    } catch (err) {
      console.error('Reset password error:', err)
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-fb-text">Сброс пароля</h2>
          <button
            onClick={onClose}
            className="text-fb-text-secondary hover:text-fb-text"
            disabled={loading}
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
              {success}
            </div>
          )}

          <div>
            <label htmlFor="current-password" className="block text-sm font-medium text-fb-text mb-2">
              Текущий пароль
            </label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-fb-gray-dark rounded-lg focus:ring-2 focus:ring-fb-blue focus:border-transparent outline-none"
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-fb-text mb-2">
              Новый пароль
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-fb-gray-dark rounded-lg focus:ring-2 focus:ring-fb-blue focus:border-transparent outline-none"
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-fb-text mb-2">
              Подтвердите новый пароль
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-fb-gray-dark rounded-lg focus:ring-2 focus:ring-fb-blue focus:border-transparent outline-none"
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-fb-text-secondary hover:text-fb-text font-medium rounded-lg hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-fb-blue text-white font-medium rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {loading ? (
                <>
                  <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Сохранение...
                </>
              ) : (
                'Сохранить'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

