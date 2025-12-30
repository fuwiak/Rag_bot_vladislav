'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '../components/Sidebar'

interface RAGDiagnosticsData {
  question: string
  project_id: string
  user_id: string
  steps: Array<{
    step: string
    status: 'pending' | 'running' | 'success' | 'error'
    data?: any
    error?: string
    timestamp: string
  }>
  final_answer?: string
  execution_time?: number
}

export default function RAGDiagnosticsPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [selectedProject, setSelectedProject] = useState<string>('')
  const [selectedUser, setSelectedUser] = useState<string>('')
  const [question, setQuestion] = useState<string>('')
  const [diagnostics, setDiagnostics] = useState<RAGDiagnosticsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingProjects, setLoadingProjects] = useState(true)

  useEffect(() => {
    fetchProjects()
  }, [])

  useEffect(() => {
    if (selectedProject) {
      fetchUsers(selectedProject)
    } else {
      setUsers([])
      setSelectedUser('')
    }
  }, [selectedProject])

  const fetchProjects = async () => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')
      const response = await apiFetch('/api/projects')
      if (response.ok) {
        const data = await response.json()
        setProjects(data)
      } else {
        console.error('Error fetching projects:', response.status)
      }
    } catch (error) {
      console.error('Error fetching projects:', error)
    } finally {
      setLoadingProjects(false)
    }
  }

  const fetchUsers = async (projectId: string) => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')
      const response = await apiFetch(`/api/users/project/${projectId}`)
      if (response.ok) {
        const data = await response.json()
        setUsers(data)
      } else {
        console.error('Error fetching users:', response.status)
      }
    } catch (error) {
      console.error('Error fetching users:', error)
    }
  }

  const manageCollection = async (action: 'create' | 'delete') => {
    if (!selectedProject) {
      alert('Выберите проект')
      return
    }

    const confirmMessage = action === 'delete' 
      ? 'Вы уверены, что хотите удалить коллекцию Qdrant? Все векторы будут удалены!'
      : 'Создать новую коллекцию Qdrant для этого проекта?'
    
    if (!confirm(confirmMessage)) {
      return
    }

    setLoading(true)

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      const response = await apiFetch(`/api/rag/collections/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: selectedProject,
          action: action,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        alert(`✅ ${data.message || (action === 'create' ? 'Коллекция создана' : 'Коллекция удалена')}`)
      } else {
        const error = await response.json()
        alert(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`)
      }
    } catch (error) {
      console.error(`Error ${action}ing collection:`, error)
      alert('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  const reprocessDocuments = async () => {
    if (!selectedProject) {
      alert('Выберите проект')
      return
    }

    if (!confirm('Переобработать все документы проекта и записать их в Qdrant? Это может занять некоторое время.')) {
      return
    }

    setLoading(true)

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      const response = await apiFetch('/api/rag/reprocess-documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: selectedProject,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        alert(`✅ ${data.message}\nОбработано: ${data.processed}/${data.total}${data.errors ? `\nОшибки: ${data.errors.length}` : ''}`)
      } else {
        const error = await response.json()
        alert(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`)
      }
    } catch (error) {
      console.error('Error reprocessing documents:', error)
      alert('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  const runDiagnostics = async () => {
    if (!selectedProject || !selectedUser || !question.trim()) {
      alert('Выберите проект, пользователя и введите вопрос')
      return
    }

    setLoading(true)
    setDiagnostics(null)

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      const response = await apiFetch('/api/rag/diagnostics', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: selectedProject,
          user_id: selectedUser,
          question: question.trim(),
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setDiagnostics(data)
      } else {
        const error = await response.json()
        alert(`Ошибка: ${error.detail || 'Неизвестная ошибка'}`)
      }
    } catch (error) {
      console.error('Error running diagnostics:', error)
      alert('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-green-600 bg-green-50'
      case 'error':
        return 'text-red-600 bg-red-50'
      case 'running':
        return 'text-blue-600 bg-blue-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return '✓'
      case 'error':
        return '✗'
      case 'running':
        return '⟳'
      default:
        return '○'
    }
  }

  if (loadingProjects) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fb-gray">
        <div className="text-fb-text-secondary text-lg">Загрузка...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-fb-gray">
      <Sidebar />
      <div className="ml-64">
        {/* Navbar */}
        <nav className="bg-white shadow-sm border-b border-fb-gray-dark sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <h1 className="text-2xl font-bold text-fb-text">Диагностика RAG</h1>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          {/* Configuration Panel */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark mb-4 p-6">
            <h2 className="text-xl font-semibold text-fb-text mb-4">Настройка диагностики</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-fb-text mb-2">
                  Проект
                </label>
                <select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  className="w-full px-3 py-2 border border-fb-gray-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-fb-blue"
                >
                  <option value="">Выберите проект</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-fb-text mb-2">
                  Пользователь
                </label>
                <select
                  value={selectedUser}
                  onChange={(e) => setSelectedUser(e.target.value)}
                  disabled={!selectedProject}
                  className="w-full px-3 py-2 border border-fb-gray-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-fb-blue disabled:bg-gray-100"
                >
                  <option value="">Выберите пользователя</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.phone || user.username || user.id}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-fb-text mb-2">
                  Вопрос для диагностики
                </label>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Введите вопрос для тестирования RAG..."
                  className="w-full px-3 py-2 border border-fb-gray-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-fb-blue h-24"
                />
              </div>

              <div className="flex space-x-2">
                <button
                  onClick={runDiagnostics}
                  disabled={loading || !selectedProject || !selectedUser || !question.trim()}
                  className="flex-1 bg-fb-blue text-white px-4 py-2 rounded-lg hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Запуск диагностики...' : 'Запустить диагностику'}
                </button>
              </div>

              {selectedProject && (
                <div className="mt-4 pt-4 border-t border-fb-gray-dark">
                  <h3 className="text-sm font-semibold text-fb-text mb-2">Управление коллекцией Qdrant</h3>
                  <div className="flex space-x-2 mb-2">
                    <button
                      onClick={() => manageCollection('delete')}
                      disabled={loading}
                      className="flex-1 bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
                    >
                      Удалить коллекцию
                    </button>
                    <button
                      onClick={() => manageCollection('create')}
                      disabled={loading}
                      className="flex-1 bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
                    >
                      Создать коллекцию
                    </button>
                  </div>
                  <button
                    onClick={reprocessDocuments}
                    disabled={loading}
                    className="w-full bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
                  >
                    {loading ? 'Обработка...' : 'Переобработать все документы в коллекцию'}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Diagnostics Results */}
          {diagnostics && (
            <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6">
              <h2 className="text-xl font-semibold text-fb-text mb-4">Результаты диагностики</h2>
              
              {diagnostics.execution_time && (
                <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                  <span className="text-sm font-medium text-blue-800">
                    Время выполнения: {diagnostics.execution_time.toFixed(2)} сек
                  </span>
                </div>
              )}

              {/* Steps Timeline */}
              <div className="space-y-4 mb-6">
                <h3 className="text-lg font-semibold text-fb-text">Этапы обработки:</h3>
                {diagnostics.steps.map((step, index) => (
                  <div
                    key={index}
                    className={`p-4 rounded-lg border ${getStatusColor(step.status)}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        <span className="text-2xl font-bold">{getStatusIcon(step.status)}</span>
                        <div className="flex-1">
                          <h4 className="font-semibold text-sm mb-1">{step.step}</h4>
                          <p className="text-xs text-gray-500">{step.timestamp}</p>
                          {step.error && (
                            <p className="text-sm text-red-600 mt-2">{step.error}</p>
                          )}
                          {step.data && (
                            <details className="mt-2">
                              <summary className="text-sm cursor-pointer text-blue-600 hover:text-blue-800">
                                Показать данные
                              </summary>
                              <pre className="mt-2 p-3 bg-gray-100 rounded text-xs overflow-auto max-h-64">
                                {JSON.stringify(step.data, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Final Answer */}
              {diagnostics.final_answer && (
                <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
                  <h3 className="text-lg font-semibold text-green-800 mb-2">Финальный ответ:</h3>
                  <p className="text-green-900 whitespace-pre-wrap">{diagnostics.final_answer}</p>
                </div>
              )}
            </div>
          )}

          {/* Info Panel */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6 mt-4">
            <h2 className="text-xl font-semibold text-fb-text mb-4">О диагностике RAG</h2>
            <div className="text-sm text-fb-text-secondary space-y-2">
              <p>
                Этот инструмент позволяет отслеживать весь процесс обработки вопроса через RAG систему.
              </p>
              <p>
                Вы можете видеть каждый этап: проверку документов, создание embeddings, поиск в Qdrant,
                генерацию summary (если нужно), и финальный ответ.
              </p>
              <p className="font-semibold text-fb-text mt-4">
                Используйте это для отладки и оптимизации работы RAG системы.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

