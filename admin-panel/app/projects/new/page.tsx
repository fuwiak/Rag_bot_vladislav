'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../../components/Sidebar'

export default function NewProjectPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    access_password: '',
    prompt_template: `Ты помощник, который отвечает на вопросы строго на основе предоставленных документов.

Контекст из документов:
{chunks}

Вопрос пользователя: {question}

Правила:
1. Отвечай ТОЛЬКО на основе предоставленного контекста
2. Если информации нет в контексте, скажи: "В загруженных документах нет информации по этому вопросу"
3. Будь кратким и структурированным
4. Максимальная длина ответа: {max_length} символов
5. Если возможно, укажи из какого раздела документа информация

Ответ:`,
    max_response_length: 1000,
    bot_token: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { apiFetch } = await import('../../lib/api-helpers')
      
      // Убеждаемся, что max_response_length - это число
      const dataToSend = {
        ...formData,
        max_response_length: Number(formData.max_response_length) || 1000,
      }
      
      // Убираем пустые строки для опциональных полей
      if (dataToSend.bot_token === '') {
        dataToSend.bot_token = null
      }
      if (dataToSend.description === '') {
        dataToSend.description = null
      }
      
      console.log('Sending project data:', dataToSend)
      
      const response = await apiFetch('/api/projects', {
        method: 'POST',
        body: JSON.stringify(dataToSend),
      })

      if (response.ok) {
        router.push('/dashboard')
      } else {
        const errorData = await response.json().catch(() => ({}))
        // Обработка ошибок валидации Pydantic (422)
        if (response.status === 422 && errorData.detail) {
          const validationErrors = Array.isArray(errorData.detail) 
            ? errorData.detail.map((err: any) => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
            : errorData.detail
          setError(`Ошибка валидации: ${validationErrors}`)
        } else {
          setError(errorData.detail || errorData.message || 'Ошибка создания проекта')
        }
        console.error('Error creating project:', errorData)
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-fb-gray">
      <Sidebar />
      <div className="ml-64">
        <div className="min-h-screen bg-fb-gray py-4">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
            <Link href="/dashboard" className="inline-flex items-center text-fb-blue hover:text-fb-blue-dark mb-4 font-medium">
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Назад к проектам
            </Link>
            <div className="bg-white shadow-sm rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="w-10 h-10 bg-fb-blue rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-fb-text">Создать новый проект</h1>
          </div>
          
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-2 rounded mb-4 text-sm">
              <p className="font-medium">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">Название проекта</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                placeholder="Введите название проекта"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">Описание</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                rows={3}
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                placeholder="Описание проекта (опционально)"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">Пароль доступа</label>
              <input
                type="password"
                required
                value={formData.access_password}
                onChange={(e) => setFormData({...formData, access_password: e.target.value})}
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                placeholder="Пароль для доступа сотрудников"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">Токен Telegram бота</label>
              <input
                type="text"
                value={formData.bot_token}
                onChange={(e) => setFormData({...formData, bot_token: e.target.value})}
                placeholder="Опционально, можно добавить позже"
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">
                Шаблон промпта *
                <span className="ml-2 text-xs text-fb-text-secondary font-normal">
                  (Как бот должен отвечать на вопросы)
                </span>
              </label>
              <div className="mb-2 p-3 bg-fb-gray rounded-lg text-xs text-fb-text-secondary">
                <p className="font-semibold mb-1">Доступные плейсхолдеры:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li><code className="bg-white px-1 rounded">{"{chunks}"}</code> - контекст из документов</li>
                  <li><code className="bg-white px-1 rounded">{"{question}"}</code> - вопрос пользователя</li>
                  <li><code className="bg-white px-1 rounded">{"{max_length}"}</code> - максимальная длина ответа</li>
                </ul>
                <p className="mt-2 font-semibold">Важно:</p>
                <p>Бот отвечает ТОЛЬКО на основе предоставленных документов. Если информации нет, он должен честно сообщить об этом.</p>
              </div>
              <textarea
                required
                value={formData.prompt_template}
                onChange={(e) => setFormData({...formData, prompt_template: e.target.value})}
                rows={15}
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                placeholder="Введите шаблон промпта..."
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-fb-text mb-1.5">Максимальная длина ответа</label>
              <input
                type="number"
                required
                min={100}
                max={10000}
                value={formData.max_response_length}
                onChange={(e) => setFormData({...formData, max_response_length: parseInt(e.target.value) || 1000})}
                className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
              />
            </div>

            <div className="flex justify-end space-x-4 pt-4 border-t border-fb-gray-dark">
              <button
                type="button"
                onClick={() => router.back()}
                className="px-6 py-3 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-3 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold shadow-md transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Создание...' : 'Создать проект'}
              </button>
            </div>
            </form>
          </div>
          </div>
        </div>
      </div>
    </div>
  )
}

