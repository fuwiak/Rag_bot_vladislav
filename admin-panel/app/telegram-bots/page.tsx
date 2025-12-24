'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../components/Sidebar'

interface BotInfo {
  project_id: string
  project_name: string
  bot_token: string | null
  bot_username: string | null
  bot_url: string | null
  bot_first_name: string | null
  is_active: boolean
  users_count: number
}

export default function TelegramBotsPage() {
  const router = useRouter()
  const [botsInfo, setBotsInfo] = useState<BotInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showTokenModal, setShowTokenModal] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [newBotToken, setNewBotToken] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchBotsInfo()
  }, [router])

  const fetchBotsInfo = async () => {
    try {
      setError('')
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch('/api/bots/info')

      if (response.ok) {
        const data = await response.json()
        setBotsInfo(data)
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка загрузки информации о ботах' }))
        throw new Error(errorData.detail || `Ошибка ${response.status}`)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка'
      if (errorMessage.includes('Failed to fetch')) {
        // Получаем реальный URL, который используется
        const { getBackendUrl } = await import('../lib/api-helpers')
        const backendUrl = await getBackendUrl()
        setError(`Ошибка подключения к серверу. Проверьте, что backend запущен и доступен по адресу: ${backendUrl}. Также убедитесь, что переменная NEXT_PUBLIC_BACKEND_URL установлена в Railway.`)
      } else {
        setError('Ошибка загрузки данных: ' + errorMessage)
      }
      console.error('Fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleAddBot = (projectId: string) => {
    setSelectedProjectId(projectId)
    setNewBotToken('')
    setShowTokenModal(true)
    setError('')
  }

  const handleVerifyToken = async () => {
    if (!newBotToken.trim()) {
      setError('Введите токен бота')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch(`/api/bots/${selectedProjectId}/verify`, {
        method: 'POST',
        body: JSON.stringify({ bot_token: newBotToken.trim() }),
      })

      if (response.ok) {
        setShowTokenModal(false)
        setNewBotToken('')
        await fetchBotsInfo()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Ошибка проверки токена')
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStartBot = async (projectId: string) => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch(`/api/bots/${projectId}/start`, {
        method: 'POST',
      })

      if (response.ok) {
        await fetchBotsInfo()
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка запуска бота')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }

  const handleStopBot = async (projectId: string) => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch(`/api/bots/${projectId}/stop`, {
        method: 'POST',
      })

      if (response.ok) {
        await fetchBotsInfo()
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка остановки бота')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fb-gray">
        <div className="text-fb-text-secondary text-lg">Загрузка...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-fb-gray">
      <Sidebar />
      
      {/* Navbar */}
      <nav className="bg-white shadow-sm border-b border-fb-gray-dark sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ml-64">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link href="/dashboard" className="flex items-center space-x-2">
                <div className="w-10 h-10 bg-fb-blue rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h1 className="text-2xl font-bold text-fb-blue hidden sm:block">RAG Bot Admin</h1>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <button
                
                className="text-fb-text-secondary hover:text-fb-text px-4 py-2 text-sm font-medium rounded-lg hover:bg-fb-gray-dark transition-colors flex items-center space-x-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>Выйти</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="ml-64">
        <main className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <div className="mb-4">
            <h2 className="text-2xl font-bold text-fb-text">Управление Telegram ботами</h2>
            <p className="text-fb-text-secondary mt-1 text-sm">
              Добавляйте и настраивайте Telegram ботов для каждого проекта
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-2 rounded mb-4 text-sm">
              <p className="font-medium">{error}</p>
            </div>
          )}

          {botsInfo.length === 0 ? (
            <div className="bg-white rounded-lg shadow-sm p-6 text-center">
              <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <p className="text-fb-text-secondary mb-4">Нет проектов. Сначала создайте проект в разделе "Проекты"</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-fb-gray-dark">
                <thead className="bg-fb-gray">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                      Проект
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                      Бот
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                      Пользователи
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                      Статус
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-fb-gray-dark">
                  {botsInfo.map((bot) => (
                    <tr key={bot.project_id} className="hover:bg-fb-gray transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Link
                          href={`/projects/${bot.project_id}`}
                          className="text-sm font-semibold text-fb-blue hover:text-fb-blue-dark"
                        >
                          {bot.project_name}
                        </Link>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {bot.bot_username ? (
                          <div>
                            <div className="text-sm font-semibold text-fb-text">
                              {bot.bot_first_name || bot.bot_username}
                            </div>
                            {bot.bot_url && (
                              <a
                                href={bot.bot_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-fb-blue hover:text-fb-blue-dark"
                              >
                                {bot.bot_url}
                              </a>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-fb-text-secondary">Бот не настроен</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-fb-text-secondary">
                        {bot.users_count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                          bot.is_active
                            ? 'bg-green-100 text-green-800'
                            : bot.bot_token
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {bot.is_active ? 'Активен' : bot.bot_token ? 'Остановлен' : 'Не настроен'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex items-center space-x-2">
                          {!bot.bot_token ? (
                            <button
                              onClick={() => handleAddBot(bot.project_id)}
                              className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors flex items-center space-x-2"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                              </svg>
                              <span>Добавить токен бота</span>
                            </button>
                          ) : (
                            <>
                              {!bot.is_active ? (
                                <button
                                  onClick={() => handleStartBot(bot.project_id)}
                                  className="px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors text-sm"
                                >
                                  Запустить
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleStopBot(bot.project_id)}
                                  className="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors text-sm"
                                >
                                  Остановить
                                </button>
                              )}
                              <button
                                onClick={() => handleAddBot(bot.project_id)}
                                className="px-3 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors text-sm"
                              >
                                Изменить токен
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          )}

          <div className="mt-8 bg-blue-50 border-l-4 border-blue-500 p-6 rounded-lg">
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-lg font-semibold text-blue-900">Как создать бота через @BotFather?</h3>
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors flex items-center space-x-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <span>Открыть @BotFather</span>
              </a>
            </div>
            <div className="space-y-4">
              <div className="bg-white p-4 rounded-lg">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold">
                    1
                  </div>
                  <div>
                    <h4 className="font-semibold text-blue-900 mb-1">Откройте @BotFather в Telegram</h4>
                    <p className="text-sm text-blue-800">
                      Найдите бота <strong>@BotFather</strong> в Telegram или нажмите кнопку выше
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-4 rounded-lg">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold">
                    2
                  </div>
                  <div>
                    <h4 className="font-semibold text-blue-900 mb-1">Создайте нового бота</h4>
                    <p className="text-sm text-blue-800 mb-2">
                      Отправьте команду <code className="bg-blue-100 px-2 py-1 rounded font-mono">/newbot</code>
                    </p>
                    <p className="text-sm text-blue-800">
                      Следуйте инструкциям: укажите имя бота и username (должен заканчиваться на <code className="bg-blue-100 px-1 rounded">bot</code>, например: <code className="bg-blue-100 px-1 rounded">my_bot</code> или <code className="bg-blue-100 px-1 rounded">mycompany_bot</code>)
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-4 rounded-lg">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold">
                    3
                  </div>
                  <div>
                    <h4 className="font-semibold text-blue-900 mb-1">Скопируйте токен</h4>
                    <p className="text-sm text-blue-800 mb-2">
                      После создания @BotFather отправит вам токен бота
                    </p>
                    <div className="bg-gray-100 p-3 rounded font-mono text-xs text-gray-800">
                      123456789:ABCdefGHIjklMNOpqrsTUVwxyz
                    </div>
                    <p className="text-sm text-blue-800 mt-2">
                      ⚠️ <strong>Важно:</strong> Сохраните токен в безопасном месте! Не публикуйте его публично.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-4 rounded-lg border-2 border-blue-500">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold">
                    4
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-blue-900 mb-2">Вставьте токен в форму</h4>
                    <p className="text-sm text-blue-800 mb-3">
                      В таблице выше найдите нужный проект и нажмите кнопку <strong className="bg-blue-100 px-2 py-1 rounded">"Добавить токен бота"</strong> (если бот не настроен) или <strong className="bg-blue-100 px-2 py-1 rounded">"Изменить токен"</strong> (если хотите изменить существующий токен).
                    </p>
                    <div className="bg-blue-100 p-3 rounded-lg">
                      <p className="text-sm font-semibold text-blue-900 mb-1">Откроется модальное окно с формой, где нужно:</p>
                      <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
                        <li>Вставить скопированный токен в текстовое поле</li>
                        <li>Нажать кнопку <strong>"Добавить и проверить"</strong></li>
                      </ol>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                <h4 className="font-semibold text-green-900 mb-2 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Готово!
                </h4>
                <p className="text-sm text-green-800">
                  После добавления токена вы получите ссылку на вашего бота. Нажмите <strong>"Запустить"</strong>, чтобы активировать бота для проекта.
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Modal для добавления токена бота */}
      {showTokenModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-fb-text">Добавить токен бота</h2>
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors flex items-center space-x-2 text-sm"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <span>Открыть @BotFather</span>
              </a>
            </div>
            
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded mb-4">
                <p className="font-medium">{error}</p>
              </div>
            )}

            <div className="space-y-4">
              {/* Инструкции */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="font-semibold text-blue-900 mb-2">Краткая инструкция:</h3>
                <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
                  <li>Нажмите кнопку <strong>"Открыть @BotFather"</strong> выше или найдите @BotFather в Telegram</li>
                  <li>Отправьте команду <code className="bg-blue-100 px-1 rounded">/newbot</code></li>
                  <li>Следуйте инструкциям для создания бота</li>
                  <li>Скопируйте токен, который отправит @BotFather</li>
                  <li>Вставьте токен в поле ниже</li>
                </ol>
              </div>

              {/* Поле для токена */}
              <div className="bg-fb-blue bg-opacity-5 border-2 border-fb-blue rounded-lg p-4">
                <label className="block text-sm font-bold text-fb-blue mb-3 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                  </svg>
                  ВСТАВЬТЕ ТОКЕН БОТА СЮДА:
                </label>
                <input
                  type="text"
                  required
                  value={newBotToken}
                  onChange={(e) => setNewBotToken(e.target.value)}
                  placeholder="Вставьте токен от @BotFather: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                  className="block w-full border-2 border-fb-blue rounded-lg px-4 py-4 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text font-mono text-sm bg-white"
                  autoFocus
                />
                <p className="text-xs text-fb-text-secondary mt-3 flex items-start">
                  <svg className="w-4 h-4 mr-1 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>Токен должен выглядеть как: <code className="bg-gray-100 px-1 rounded font-mono">123456789:ABCdefGHIjklMNOpqrsTUVwxyz</code> (две части, разделенные двоеточием)</span>
                </p>
              </div>

              {/* Пример токена */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-xs font-semibold text-gray-700 mb-2">Пример формата токена:</p>
                <div className="bg-white border border-gray-300 rounded px-3 py-2 font-mono text-xs text-gray-800">
                  1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  Токен состоит из двух частей, разделенных двоеточием (:)
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6 pt-4 border-t border-fb-gray-dark">
              <button
                type="button"
                onClick={() => {
                  setShowTokenModal(false)
                  setNewBotToken('')
                  setError('')
                }}
                disabled={submitting}
                className="px-4 py-2 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleVerifyToken}
                disabled={submitting || !newBotToken.trim()}
                className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {submitting ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Проверка...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Добавить и проверить</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

