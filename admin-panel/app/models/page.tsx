'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '../components/Sidebar'

interface Model {
  id: string
  name: string
  description: string
  context_length?: number
  pricing?: any
  is_custom?: boolean
}

interface Project {
  id: string
  name: string
  llm_model: string | null
  bot_token: string | null
}

export default function ModelsPage() {
  const router = useRouter()
  const [models, setModels] = useState<Model[]>([])
  const [filteredModels, setFilteredModels] = useState<Model[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [assigning, setAssigning] = useState(false)
  const [globalSettings, setGlobalSettings] = useState<{primary_model_id: string | null, fallback_model_id: string | null} | null>(null)
  const [showAddCustomModal, setShowAddCustomModal] = useState(false)
  const [customModelId, setCustomModelId] = useState('')
  const [customModelName, setCustomModelName] = useState('')
  const [customModelDesc, setCustomModelDesc] = useState('')
  const [addingCustom, setAddingCustom] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [primarySearchQuery, setPrimarySearchQuery] = useState('')
  const [fallbackSearchQuery, setFallbackSearchQuery] = useState('')
  const [showPrimaryDropdown, setShowPrimaryDropdown] = useState(false)
  const [showFallbackDropdown, setShowFallbackDropdown] = useState(false)
  const [activeTab, setActiveTab] = useState<'models' | 'testing'>('models')
  
  // Состояния для тестирования моделей
  const [testModelId, setTestModelId] = useState<string>('')
  const [testMessages, setTestMessages] = useState<Array<{role: string, content: string}>>([])
  const [currentMessage, setCurrentMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [testModelSearchQuery, setTestModelSearchQuery] = useState('')
  const [showTestModelDropdown, setShowTestModelDropdown] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchData()
  }, [router])

  const fetchData = async () => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      // Загружаем модели, проекты и глобальные настройки параллельно
      const [modelsRes, projectsRes, settingsRes] = await Promise.all([
        apiFetch('/api/models/available'),
        apiFetch('/api/projects'),
        apiFetch('/api/models/global-settings'),
      ])

      let loadedModels: Model[] = []
      if (modelsRes.ok) {
        const modelsData = await modelsRes.json()
        loadedModels = modelsData.models || []
        setModels(loadedModels)
        setFilteredModels(loadedModels)
      }

      if (projectsRes.ok) {
        const projectsData = await projectsRes.json()
        setProjects(projectsData || [])
      }

      if (settingsRes.ok) {
        const settingsData = await settingsRes.json()
        setGlobalSettings(settingsData)
        
        // Устанавливаем модели по умолчанию, если их нет
        const defaultPrimary = 'x-ai/grok-4.1-fast'
        const defaultFallback = 'openai/gpt-oss-120b:free'
        
        if (!settingsData.primary_model_id && !settingsData.fallback_model_id) {
          // Если настроек нет, устанавливаем дефолтные
          const { apiFetch } = await import('../lib/api-helpers')
          
          apiFetch('/api/models/global-settings', {
            method: 'PATCH',
            body: JSON.stringify({
              primary_model_id: defaultPrimary,
              fallback_model_id: defaultFallback,
            }),
          }).then(res => res.json()).then(data => {
            setGlobalSettings(data)
            // Инициализируем поисковые запросы (используем loadedModels z closure)
            const primaryModel = loadedModels.find(m => m.id === defaultPrimary)
            const fallbackModel = loadedModels.find(m => m.id === defaultFallback)
            if (primaryModel) setPrimarySearchQuery(primaryModel.name)
            if (fallbackModel) setFallbackSearchQuery(fallbackModel.name)
          }).catch(err => console.error('Ошибка установки дефолтных моделей:', err))
        } else {
          // Инициализируем поисковые запросы названиями моделей (используем уже загруженные модели)
          if (settingsData.primary_model_id) {
            const primaryModel = loadedModels.find(m => m.id === settingsData.primary_model_id)
            if (primaryModel) {
              setPrimarySearchQuery(primaryModel.name)
            } else {
              // Если модель не найдена в списке, показываем ID
              setPrimarySearchQuery(settingsData.primary_model_id)
            }
          }
          if (settingsData.fallback_model_id) {
            const fallbackModel = loadedModels.find(m => m.id === settingsData.fallback_model_id)
            if (fallbackModel) {
              setFallbackSearchQuery(fallbackModel.name)
            } else {
              // Если модель не найдена в списке, показываем ID
              setFallbackSearchQuery(settingsData.fallback_model_id)
            }
          }
        }
      }
    } catch (err) {
      console.error('Ошибка загрузки данных:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleAssignModel = async () => {
    if (!selectedProject || !selectedModel) {
      alert('Выберите проект и модель')
      return
    }

    setAssigning(true)
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch(`/api/models/project/${selectedProject}?model_id=${encodeURIComponent(selectedModel)}`, {
        method: 'PATCH',
      })

      if (response.ok) {
        const data = await response.json()
        alert('Модель успешно присвоена проекту')
        fetchData() // Обновляем список проектов
        setSelectedProject(null)
        setSelectedModel('')
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка присвоения модели')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    } finally {
      setAssigning(false)
    }
  }

  const handleSearchModels = async (query: string, type?: 'primary' | 'fallback') => {
    if (!query || query.length < 2) {
      setFilteredModels(models)
      return
    }

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      
      const response = await apiFetch(`/api/models/available?search=${encodeURIComponent(query)}`)

      if (response.ok) {
        const data = await response.json()
        const filtered = data.models || []
        setFilteredModels(filtered)
        
        if (type === 'primary') {
          setShowPrimaryDropdown(true)
        } else if (type === 'fallback') {
          setShowFallbackDropdown(true)
        }
      }
    } catch (err) {
      console.error('Ошибка поиска моделей:', err)
      // Fallback: фильтруем локально
      const filtered = models.filter(m => 
        m.name.toLowerCase().includes(query.toLowerCase()) || 
        m.id.toLowerCase().includes(query.toLowerCase())
      )
      setFilteredModels(filtered)
    }
  }

  const handleUpdateGlobalSettings = async (type: 'primary' | 'fallback', modelId: string) => {
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const updateData: any = {}
      if (type === 'primary') {
        updateData.primary_model_id = modelId || null
      } else {
        updateData.fallback_model_id = modelId || null
      }

      const response = await apiFetch('/api/models/global-settings', {
        method: 'PATCH',
        body: JSON.stringify(updateData),
      })

      if (response.ok) {
        const data = await response.json()
        setGlobalSettings(data)
        alert('Глобальные настройки обновлены')
        fetchData()
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка обновления настроек')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }

  const handleAddCustomModel = async () => {
    if (!customModelId || !customModelName) {
      alert('Заполните ID и название модели')
      return
    }

    setAddingCustom(true)
    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const response = await apiFetch('/api/models/custom', {
        method: 'POST',
        body: JSON.stringify({
          model_id: customModelId,
          name: customModelName,
          description: customModelDesc || null,
        }),
      })

      if (response.ok) {
        setShowAddCustomModal(false)
        setCustomModelId('')
        setCustomModelName('')
        setCustomModelDesc('')
        fetchData()
        alert('Кастомная модель добавлена')
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка добавления модели')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    } finally {
      setAddingCustom(false)
    }
  }


  const handleSendTestMessage = async () => {
    if (!testModelId || !currentMessage.trim()) {
      alert('Выберите модель и введите сообщение')
      return
    }

    const userMessage = currentMessage.trim()
    setCurrentMessage('')
    setIsSending(true)

    // Добавляем сообщение пользователя в историю
    const newMessages = [...testMessages, { role: 'user', content: userMessage }]
    setTestMessages(newMessages)

    try {
      const { apiFetch } = await import('../lib/api-helpers')

      const requestData = {
        model_id: testModelId,
        messages: newMessages,
        temperature: 0.7,
      }
      
      console.log('Sending test request:', JSON.stringify(requestData, null, 2))

      const response = await apiFetch('/api/models/test', {
        method: 'POST',
        body: JSON.stringify(requestData),
      })

      if (response.ok) {
        const data = await response.json()
        // Добавляем ответ модели в историю
        setTestMessages([...newMessages, { role: 'assistant', content: data.response }])
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Не удалось получить детали ошибки' }))
        const errorMessage = errorData.detail || errorData.message || `Ошибка при отправке сообщения (статус: ${response.status})`
        console.error('Error testing model - Full response:', {
          status: response.status,
          statusText: response.statusText,
          errorData: errorData,
          headers: Object.fromEntries(response.headers.entries())
        })
        // Показываем детальную ошибку
        alert(`Ошибка тестирования модели:\n\n${errorMessage}\n\nПроверьте консоль (F12) для деталей.`)
        // Удаляем последнее сообщение пользователя при ошибке
        setTestMessages(testMessages)
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
      setTestMessages(testMessages)
    } finally {
      setIsSending(false)
    }
  }

  const handleClearChat = () => {
    setTestMessages([])
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendTestMessage()
    }
  }

  // Автоматическая прокрутка к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [testMessages, isSending])

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
      <div className="ml-64">
        {/* Navbar */}
        <nav className="bg-white shadow-sm border-b border-fb-gray-dark sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <h1 className="text-2xl font-bold text-fb-text">Управление моделями LLM</h1>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          {/* Вкладки */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark mb-4">
            <div className="flex border-b border-fb-gray-dark">
              <button
                onClick={() => setActiveTab('models')}
                className={`px-6 py-4 font-semibold transition-colors ${
                  activeTab === 'models'
                    ? 'text-fb-blue border-b-2 border-fb-blue'
                    : 'text-fb-text-secondary hover:text-fb-text'
                }`}
              >
                Доступные модели
              </button>
              <button
                onClick={() => setActiveTab('testing')}
                className={`px-6 py-4 font-semibold transition-colors ${
                  activeTab === 'testing'
                    ? 'text-fb-blue border-b-2 border-fb-blue'
                    : 'text-fb-text-secondary hover:text-fb-text'
                }`}
              >
                Тестирование моделей
              </button>
            </div>
          </div>

          {activeTab === 'models' ? (
            <>
          {/* Глобальные настройки моделей */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6 mb-4">
            <h2 className="text-xl font-bold text-fb-text mb-4">Глобальные настройки моделей</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Primary модель */}
              <div className="relative">
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Primary модель (основная)
                </label>
                <input
                  type="text"
                  value={primarySearchQuery}
                  onChange={(e) => {
                    const query = e.target.value
                    setPrimarySearchQuery(query)
                    if (query.length >= 2) {
                      handleSearchModels(query, 'primary')
                    } else {
                      setFilteredModels(models)
                    }
                  }}
                  onFocus={() => {
                    setShowPrimaryDropdown(true)
                    setFilteredModels(models)
                  }}
                  onBlur={() => setTimeout(() => setShowPrimaryDropdown(false), 200)}
                  placeholder="Начните вводить название модели..."
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                />
                {showPrimaryDropdown && filteredModels.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-fb-gray-dark rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {filteredModels.slice(0, 20).map((model) => (
                      <div
                        key={model.id}
                        onClick={() => {
                          handleUpdateGlobalSettings('primary', model.id)
                          setPrimarySearchQuery(model.name)
                          setShowPrimaryDropdown(false)
                        }}
                        className="px-4 py-2 hover:bg-fb-gray cursor-pointer"
                      >
                        <div className="font-semibold text-fb-text">{model.name}</div>
                        <div className="text-xs text-fb-text-secondary">{model.id}</div>
                        {model.description && (
                          <div className="text-xs text-fb-text-secondary mt-1">{model.description}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <button
                  onClick={() => {
                    handleUpdateGlobalSettings('primary', '')
                    setPrimarySearchQuery('')
                  }}
                  className="mt-2 text-sm text-red-600 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!globalSettings?.primary_model_id}
                >
                  Очистить
                </button>
              </div>

              {/* Fallback модель */}
              <div className="relative">
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Fallback модель (резервная)
                </label>
                <input
                  type="text"
                  value={fallbackSearchQuery}
                  onChange={(e) => {
                    const query = e.target.value
                    setFallbackSearchQuery(query)
                    if (query.length >= 2) {
                      handleSearchModels(query, 'fallback')
                    } else {
                      setFilteredModels(models)
                    }
                  }}
                  onFocus={() => {
                    setShowFallbackDropdown(true)
                    setFilteredModels(models)
                  }}
                  onBlur={() => setTimeout(() => setShowFallbackDropdown(false), 200)}
                  placeholder="Начните вводить название модели..."
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                />
                {showFallbackDropdown && filteredModels.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-fb-gray-dark rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {filteredModels.slice(0, 20).map((model) => (
                      <div
                        key={model.id}
                        onClick={() => {
                          handleUpdateGlobalSettings('fallback', model.id)
                          setFallbackSearchQuery(model.name)
                          setShowFallbackDropdown(false)
                        }}
                        className="px-4 py-2 hover:bg-fb-gray cursor-pointer"
                      >
                        <div className="font-semibold text-fb-text">{model.name}</div>
                        <div className="text-xs text-fb-text-secondary">{model.id}</div>
                        {model.description && (
                          <div className="text-xs text-fb-text-secondary mt-1">{model.description}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <button
                  onClick={() => {
                    handleUpdateGlobalSettings('fallback', '')
                    setFallbackSearchQuery('')
                  }}
                  className="mt-2 text-sm text-red-600 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!globalSettings?.fallback_model_id}
                >
                  Очистить
                </button>
              </div>
            </div>
          </div>

          {/* Добавление кастомной модели */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6 mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-fb-text">Кастомные модели</h2>
              <button
                onClick={() => setShowAddCustomModal(true)}
                className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors"
              >
                + Добавить кастомную модель
              </button>
            </div>
          </div>

          {/* Присвоение модели проекту */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6 mb-8">
            <h2 className="text-xl font-bold text-fb-text mb-4">Присвоить модель проекту</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Выберите проект
                </label>
                <select
                  value={selectedProject || ''}
                  onChange={(e) => {
                    setSelectedProject(e.target.value)
                    const project = projects.find(p => p.id === e.target.value)
                    setSelectedModel(project?.llm_model || '')
                  }}
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                >
                  <option value="">-- Выберите проект --</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name} {project.bot_token ? '🤖' : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Выберите модель LLM
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={selectedModel ? (models.find(m => m.id === selectedModel)?.name || selectedModel) : ''}
                    onChange={(e) => {
                      const query = e.target.value
                      setSearchQuery(query)
                      handleSearchModels(query)
                    }}
                    onFocus={() => {
                      setFilteredModels(models)
                    }}
                    placeholder="Начните вводить название модели..."
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  />
                  {filteredModels.length > 0 && searchQuery && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-fb-gray-dark rounded-lg shadow-lg max-h-60 overflow-y-auto">
                      {filteredModels.slice(0, 20).map((model) => (
                        <div
                          key={model.id}
                          onClick={() => {
                            setSelectedModel(model.id)
                            setSearchQuery('')
                          }}
                          className="px-4 py-2 hover:bg-fb-gray cursor-pointer"
                        >
                          <div className="font-semibold text-fb-text">{model.name}</div>
                          <div className="text-xs text-fb-text-secondary">{model.id}</div>
                          {model.description && (
                            <div className="text-xs text-fb-text-secondary mt-1">{model.description}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedModel && (
                    <button
                      onClick={() => {
                        setSelectedModel('')
                        setSearchQuery('')
                      }}
                      className="mt-2 text-sm text-red-600 hover:text-red-700"
                    >
                      Очистить
                    </button>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-4">
              <button
                onClick={handleAssignModel}
                disabled={!selectedProject || assigning}
                className="px-6 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {assigning ? 'Присвоение...' : 'Присвоить модель'}
              </button>
            </div>
          </div>

          {/* Список проектов с их моделями */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6">
            <h2 className="text-xl font-bold text-fb-text mb-4">Проекты и их модели</h2>
            <div className="space-y-3">
              {projects.map((project) => {
                const currentModel = models.find(m => m.id === project.llm_model)
                return (
                  <div key={project.id} className="flex items-center justify-between p-4 border border-fb-gray-dark rounded-lg hover:bg-fb-gray transition-colors">
                    <div className="flex items-center space-x-4">
                      <div>
                        <p className="font-semibold text-fb-text">{project.name}</p>
                        <p className="text-sm text-fb-text-secondary">
                          Модель: {currentModel ? currentModel.name : 'Глобальная (по умолчанию)'}
                          {project.bot_token && ' • 🤖 Бот настроен'}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedProject(project.id)
                        setSelectedModel(project.llm_model || '')
                      }}
                      className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors text-sm"
                    >
                      Изменить модель
                    </button>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Список доступных моделей */}
          <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6 mt-8">
            <h2 className="text-xl font-bold text-fb-text mb-4">Доступные модели</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {models.map((model) => (
                <div key={model.id} className="p-4 border border-fb-gray-dark rounded-lg hover:bg-fb-gray transition-colors">
                  <h3 className="font-semibold text-fb-text mb-2">{model.name}</h3>
                  <p className="text-sm text-fb-text-secondary mb-2">{model.description}</p>
                  <p className="text-xs text-fb-text-secondary">
                    ID: {model.id}
                    {model.context_length && ` • Context: ${model.context_length.toLocaleString()}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
            </>
          ) : (
            /* Вкладка тестирования моделей */
            <div className="bg-white rounded-lg shadow-sm border border-fb-gray-dark p-6">
              <h2 className="text-xl font-bold text-fb-text mb-4">Тестирование моделей</h2>
              
              {/* Выбор модели */}
              <div className="mb-4">
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Выберите модель для тестирования
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={testModelSearchQuery}
                    onChange={(e) => {
                      const query = e.target.value
                      setTestModelSearchQuery(query)
                      if (query.length >= 2) {
                        handleSearchModels(query)
                      } else {
                        setFilteredModels(models)
                      }
                    }}
                    onFocus={() => {
                      setShowTestModelDropdown(true)
                      setFilteredModels(models)
                    }}
                    onBlur={() => setTimeout(() => setShowTestModelDropdown(false), 200)}
                    placeholder="Начните вводить название модели..."
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  />
                  {showTestModelDropdown && filteredModels.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-fb-gray-dark rounded-lg shadow-lg max-h-60 overflow-y-auto">
                      {filteredModels.slice(0, 20).map((model) => (
                        <div
                          key={model.id}
                          onClick={() => {
                            setTestModelId(model.id)
                            setTestModelSearchQuery(model.name)
                            setShowTestModelDropdown(false)
                          }}
                          className="px-4 py-2 hover:bg-fb-gray cursor-pointer"
                        >
                          <div className="font-semibold text-fb-text">{model.name}</div>
                          <div className="text-xs text-fb-text-secondary">{model.id}</div>
                          {model.description && (
                            <div className="text-xs text-fb-text-secondary mt-1">{model.description}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {testModelId && (
                  <div className="mt-2 text-sm text-fb-text-secondary">
                    Выбрана модель: <span className="font-semibold">{models.find(m => m.id === testModelId)?.name || testModelId}</span>
                    <button
                      onClick={() => {
                        setTestModelId('')
                        setTestModelSearchQuery('')
                      }}
                      className="ml-2 text-red-600 hover:text-red-700"
                    >
                      Очистить
                    </button>
                  </div>
                )}
              </div>

              {/* Чат интерфейс */}
              <div className="border border-fb-gray-dark rounded-lg flex flex-col" style={{ height: '600px' }}>
                {/* История сообщений */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {testMessages.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-fb-text-secondary">
                      Выберите модель и начните диалог
                    </div>
                  ) : (
                    testMessages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-3xl rounded-lg px-4 py-2 ${
                            msg.role === 'user'
                              ? 'bg-fb-blue text-white'
                              : 'bg-fb-gray text-fb-text'
                          }`}
                        >
                          <div className="text-sm font-semibold mb-1">
                            {msg.role === 'user' ? 'Вы' : 'Модель'}
                          </div>
                          <div className="whitespace-pre-wrap">{msg.content}</div>
                        </div>
                      </div>
                    ))
                  )}
                  {isSending && (
                    <div className="flex justify-start">
                      <div className="bg-fb-gray text-fb-text rounded-lg px-4 py-2">
                        <div className="flex items-center space-x-2">
                          <div className="w-2 h-2 bg-fb-text-secondary rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-fb-text-secondary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                          <div className="w-2 h-2 bg-fb-text-secondary rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Поле ввода */}
                <div className="border-t border-fb-gray-dark p-4">
                  <div className="flex space-x-2">
                    <textarea
                      value={currentMessage}
                      onChange={(e) => setCurrentMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Введите сообщение..."
                      className="flex-1 border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text resize-none"
                      rows={3}
                      disabled={isSending || !testModelId}
                    />
                    <div className="flex flex-col space-y-2">
                      <button
                        onClick={handleSendTestMessage}
                        disabled={isSending || !testModelId || !currentMessage.trim()}
                        className="px-6 py-3 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSending ? 'Отправка...' : 'Отправить'}
                      </button>
                      <button
                        onClick={handleClearChat}
                        disabled={testMessages.length === 0 || isSending}
                        className="px-6 py-3 border border-fb-gray-dark hover:bg-fb-gray text-fb-text rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Очистить
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Modal для добавления кастомной модели */}
      {showAddCustomModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold text-fb-text mb-4">Добавить кастомную модель</h2>
            
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  ID модели *
                </label>
                <input
                  type="text"
                  required
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  placeholder="например: custom/my-model"
                />
                <p className="text-xs text-fb-text-secondary mt-1">
                  ID модели из OpenRouter или ваш кастомный ID
                </p>
              </div>
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Название *
                </label>
                <input
                  type="text"
                  required
                  value={customModelName}
                  onChange={(e) => setCustomModelName(e.target.value)}
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  placeholder="Моя модель"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-1.5">
                  Описание (опционально)
                </label>
                <textarea
                  value={customModelDesc}
                  onChange={(e) => setCustomModelDesc(e.target.value)}
                  className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  rows={3}
                  placeholder="Описание модели"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6 pt-4 border-t border-fb-gray-dark">
              <button
                type="button"
                onClick={() => {
                  setShowAddCustomModal(false)
                  setCustomModelId('')
                  setCustomModelName('')
                  setCustomModelDesc('')
                }}
                disabled={addingCustom}
                className="px-4 py-2 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleAddCustomModel}
                disabled={addingCustom || !customModelId || !customModelName}
                className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addingCustom ? 'Добавление...' : 'Добавить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

