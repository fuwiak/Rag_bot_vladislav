'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../../components/Sidebar'

interface Project {
  id: string
  name: string
  description: string | null
  bot_token: string | null
  access_password: string
  prompt_template: string
  max_response_length: number
  created_at: string
  updated_at: string
}

interface Document {
  id: string
  project_id: string
  filename: string
  file_type: string
  created_at: string
}

interface User {
  id: string
  project_id: string
  phone: string
  username: string | null
  status: string
  first_login_at: string | null
  created_at: string
}

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string

  const [project, setProject] = useState<Project | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'info' | 'documents' | 'users'>('info')
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState({
    name: '',
    description: '',
    access_password: '',
    prompt_template: '',
    max_response_length: 1000,
    bot_token: '',
  })
  const [saving, setSaving] = useState(false)
  const [showAddUserModal, setShowAddUserModal] = useState(false)
  const [newUserPhone, setNewUserPhone] = useState('')
  const [newUserUsername, setNewUserUsername] = useState('')
  const [addingUser, setAddingUser] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])

  useEffect(() => {
    // Lazy loading: загружаем только основные данные проекта при монтировании
    fetchProjectBasicData()
  }, [projectId, router])

  // Загружаем документы и пользователей только при переключении на соответствующие вкладки
  useEffect(() => {
    if (activeTab === 'documents' && documents.length === 0 && !loading) {
      fetchDocuments()
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab === 'users' && users.length === 0 && !loading) {
      fetchUsers()
    }
  }, [activeTab])

  // Загружаем только основные данные проекта
  const fetchProjectBasicData = async () => {
    setLoading(true)
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      

      const projectRes = await fetch(`${backendUrl}/api/projects/${projectId}`, {
        headers: { 'Content-Type': 'application/json' },
      })

      if (projectRes.ok) {
        const projectData = await projectRes.json()
        setProject(projectData)
        // Заполняем форму редактирования
        setEditData({
          name: projectData.name,
          description: projectData.description || '',
          access_password: projectData.access_password,
          prompt_template: projectData.prompt_template,
          max_response_length: projectData.max_response_length,
          bot_token: projectData.bot_token || '',
        })
      } else if (projectRes.status === 401) {
        
        return
      } else if (projectRes.status === 404) {
        setError('Проект не найден')
      }
    } catch (err) {
      setError('Ошибка загрузки данных')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  // Lazy loading документов
  const fetchDocuments = async () => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      

      const documentsRes = await fetch(`${backendUrl}/api/documents/${projectId}`, {
        headers: { 'Content-Type': 'application/json' },
      })

      if (documentsRes.ok) {
        const documentsData = await documentsRes.json()
        setDocuments(documentsData)
      }
    } catch (err) {
      console.error('Ошибка загрузки документов:', err)
    }
  }

  // Lazy loading пользователей
  const fetchUsers = async () => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      

      const usersRes = await fetch(`${backendUrl}/api/users/project/${projectId}`, {
        headers: { 'Content-Type': 'application/json' },
      })

      if (usersRes.ok) {
        const usersData = await usersRes.json()
        setUsers(usersData)
      }
    } catch (err) {
      console.error('Ошибка загрузки пользователей:', err)
    }
  }

  // Полная загрузка всех данных (используется при необходимости)
  const fetchProjectData = async () => {
    await Promise.all([
      fetchProjectBasicData(),
      fetchDocuments(),
      fetchUsers()
    ])
  }

  const handleDelete = async () => {
    if (!confirm('Вы уверены, что хотите удалить этот проект? Это действие необратимо.')) {
      return
    }

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      

      const response = await fetch(`${backendUrl}/api/projects/${projectId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        router.push('/dashboard')
      } else {
        const errorData = await response.json()
        alert(errorData.detail || 'Ошибка удаления проекта')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    // Восстанавливаем исходные данные
    if (project) {
      setEditData({
        name: project.name,
        description: project.description || '',
        access_password: project.access_password,
        prompt_template: project.prompt_template,
        max_response_length: project.max_response_length,
        bot_token: project.bot_token || '',
      })
    }
    setError('')
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      

      const response = await fetch(`${backendUrl}/api/projects/${projectId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editData),
      })

      if (response.ok) {
        const updatedProject = await response.json()
        setProject(updatedProject)
        setIsEditing(false)
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Ошибка сохранения проекта')
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setSaving(false)
    }
  }


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fb-gray">
        <div className="text-fb-text-secondary text-lg">Загрузка...</div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-fb-gray py-4">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link href="/dashboard" className="inline-flex items-center text-fb-blue hover:text-fb-blue-dark mb-4 font-medium">
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Назад к проектам
          </Link>
          <div className="bg-white rounded-lg shadow-sm p-6 text-center">
            <p className="text-red-600 text-lg">{error || 'Проект не найден'}</p>
          </div>
        </div>
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
              <Link
                href="/dashboard"
                className="text-fb-text-secondary hover:text-fb-text px-4 py-2 text-sm font-medium rounded-lg hover:bg-fb-gray-dark transition-colors"
              >
                Все проекты
              </Link>
              <button
        <div className="mb-4">
          <Link href="/dashboard" className="inline-flex items-center text-fb-blue hover:text-fb-blue-dark mb-4 font-medium">
            <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Назад к проектам
          </Link>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-fb-text mb-2">
                {isEditing ? editData.name : project.name}
              </h1>
              {(isEditing ? editData.description : project.description) && (
                <p className="text-fb-text-secondary text-lg">
                  {isEditing ? editData.description : project.description}
                </p>
              )}
            </div>
            <div className="flex space-x-3">
              {!isEditing ? (
                <>
                  <button
                    onClick={handleEdit}
                    className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors flex items-center space-x-2"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    <span>Редактировать</span>
                  </button>
                  <button
                    onClick={handleDelete}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors"
                  >
                    Удалить проект
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>{saving ? 'Сохранение...' : 'Сохранить'}</span>
                  </button>
                  <button
                    onClick={handleCancelEdit}
                    disabled={saving}
                    className="px-4 py-2 bg-fb-gray-dark hover:bg-gray-400 text-fb-text rounded-lg font-semibold transition-colors disabled:opacity-50"
                  >
                    Отмена
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow-sm mb-4">
          <div className="border-b border-fb-gray-dark">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('info')}
                className={`px-6 py-4 font-semibold text-sm border-b-2 transition-colors ${
                  activeTab === 'info'
                    ? 'border-fb-blue text-fb-blue'
                    : 'border-transparent text-fb-text-secondary hover:text-fb-text hover:border-fb-gray-dark'
                }`}
              >
                Информация
              </button>
              <button
                onClick={() => setActiveTab('documents')}
                className={`px-6 py-4 font-semibold text-sm border-b-2 transition-colors ${
                  activeTab === 'documents'
                    ? 'border-fb-blue text-fb-blue'
                    : 'border-transparent text-fb-text-secondary hover:text-fb-text hover:border-fb-gray-dark'
                }`}
              >
                Документы ({documents.length})
              </button>
              <button
                onClick={() => setActiveTab('users')}
                className={`px-6 py-4 font-semibold text-sm border-b-2 transition-colors ${
                  activeTab === 'users'
                    ? 'border-fb-blue text-fb-blue'
                    : 'border-transparent text-fb-text-secondary hover:text-fb-text hover:border-fb-gray-dark'
                }`}
              >
                Пользователи ({users.length})
              </button>
            </nav>
          </div>
        </div>

        {/* Content */}
          <div className="bg-white rounded-lg shadow-sm p-6">
          {activeTab === 'info' && (
            <div className="space-y-4">
              {error && (
                <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded">
                  <p className="font-medium">{error}</p>
                </div>
              )}

              {!isEditing ? (
                <>
                  <div>
                    <h2 className="text-2xl font-bold text-fb-text mb-4">Основная информация</h2>
                    <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">ID проекта</dt>
                        <dd className="mt-1 text-sm text-fb-text font-mono">{project.id}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Название</dt>
                        <dd className="mt-1 text-sm text-fb-text">{project.name}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Описание</dt>
                        <dd className="mt-1 text-sm text-fb-text">{project.description || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Пароль доступа</dt>
                        <dd className="mt-1 text-sm text-fb-text font-mono">{project.access_password}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Токен бота</dt>
                        <dd className="mt-1 text-sm text-fb-text font-mono">
                          {project.bot_token ? (project.bot_token.substring(0, 20) + '...') : 'Не установлен'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Макс. длина ответа</dt>
                        <dd className="mt-1 text-sm text-fb-text">{project.max_response_length} символов</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Создан</dt>
                        <dd className="mt-1 text-sm text-fb-text">
                          {new Date(project.created_at).toLocaleString('ru-RU')}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-semibold text-fb-text-secondary">Обновлен</dt>
                        <dd className="mt-1 text-sm text-fb-text">
                          {new Date(project.updated_at).toLocaleString('ru-RU')}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div>
                    <h3 className="text-xl font-bold text-fb-text mb-3">Шаблон промпта</h3>
                    <div className="bg-fb-gray rounded-lg p-4">
                      <pre className="text-sm text-fb-text whitespace-pre-wrap font-mono">
                        {project.prompt_template}
                      </pre>
                    </div>
                  </div>
                </>
              ) : (
                <form onSubmit={handleSave} className="space-y-4">
                  <div>
                    <h2 className="text-2xl font-bold text-fb-text mb-4">Редактирование проекта</h2>
                    
                    <div className="mb-4 p-4 bg-fb-gray rounded-lg">
                      <p className="text-sm text-fb-text-secondary">
                        <strong>ID проекта:</strong> <span className="font-mono">{project.id}</span>
                      </p>
                      <p className="text-sm text-fb-text-secondary mt-2">
                        <strong>Создан:</strong> {new Date(project.created_at).toLocaleString('ru-RU')}
                      </p>
                      <p className="text-sm text-fb-text-secondary">
                        <strong>Обновлен:</strong> {new Date(project.updated_at).toLocaleString('ru-RU')}
                      </p>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
                          Название проекта *
                        </label>
                        <input
                          type="text"
                          required
                          value={editData.name}
                          onChange={(e) => setEditData({...editData, name: e.target.value})}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                          placeholder="Введите название проекта"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
                          Описание
                        </label>
                        <textarea
                          value={editData.description}
                          onChange={(e) => setEditData({...editData, description: e.target.value})}
                          rows={3}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                          placeholder="Описание проекта (опционально)"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
                          Пароль доступа *
                        </label>
                        <input
                          type="password"
                          required
                          value={editData.access_password}
                          onChange={(e) => setEditData({...editData, access_password: e.target.value})}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                          placeholder="Пароль для доступа сотрудников"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
                          Токен Telegram бота
                        </label>
                        <input
                          type="text"
                          value={editData.bot_token}
                          onChange={(e) => setEditData({...editData, bot_token: e.target.value})}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                          placeholder="Опционально, можно оставить пустым"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
                          Максимальная длина ответа *
                        </label>
                        <input
                          type="number"
                          required
                          min={100}
                          max={10000}
                          value={editData.max_response_length}
                          onChange={(e) => setEditData({...editData, max_response_length: parseInt(e.target.value)})}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-fb-text mb-2">
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
                          value={editData.prompt_template}
                          onChange={(e) => setEditData({...editData, prompt_template: e.target.value})}
                          rows={15}
                          className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                          placeholder="Введите шаблон промпта..."
                        />
                      </div>
                    </div>
                  </div>
                </form>
              )}
            </div>
          )}

          {activeTab === 'documents' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-fb-text">Документы</h2>
                <button 
                  onClick={() => setShowUploadModal(true)}
                  className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors"
                >
                  Загрузить документы
                </button>
              </div>
              {documents.length === 0 ? (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-fb-text-secondary mb-4">Нет загруженных документов</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {documents.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-4 border border-fb-gray-dark rounded-lg hover:bg-fb-gray transition-colors">
                      <div className="flex items-center space-x-4">
                        <svg className="w-8 h-8 text-fb-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <div>
                          <p className="font-semibold text-fb-text">{doc.filename}</p>
                          <p className="text-sm text-fb-text-secondary">
                            {doc.file_type.toUpperCase()} • {new Date(doc.created_at).toLocaleDateString('ru-RU')}
                          </p>
                        </div>
                      </div>
                      <button 
                        onClick={async () => {
                          if (!confirm(`Вы уверены, что хотите удалить документ "${doc.filename}"?`)) {
                            return
                          }
                          try {
                            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
                            
                            const response = await fetch(`${backendUrl}/api/documents/${doc.id}`, {
                              method: 'DELETE',
                              headers: { 'Content-Type': 'application/json' },
                            })
                            if (response.ok || response.status === 204) {
                              fetchDocuments()
                            } else {
                              const errorData = await response.json().catch(() => ({ detail: 'Ошибка удаления документа' }))
                              alert(errorData.detail || 'Ошибка удаления документа')
                            }
                          } catch (err) {
                            alert('Ошибка подключения к серверу')
                          }
                        }}
                        className="text-red-600 hover:text-red-700 px-4 py-2 rounded-lg hover:bg-red-50 transition-colors"
                      >
                        Удалить
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'users' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-fb-text">Пользователи</h2>
                <button
                  onClick={() => setShowAddUserModal(true)}
                  className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors flex items-center space-x-2"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Добавить пользователя</span>
                </button>
              </div>
              {users.length === 0 ? (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                  <p className="text-fb-text-secondary mb-4">Нет пользователей</p>
                  <button
                    onClick={() => setShowAddUserModal(true)}
                    className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors"
                  >
                    Добавить первого пользователя
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-4 border border-fb-gray-dark rounded-lg hover:bg-fb-gray transition-colors">
                      <div className="flex items-center space-x-4">
                        <div className="w-10 h-10 bg-fb-blue rounded-full flex items-center justify-center text-white font-semibold">
                          {user.phone.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-fb-text">{user.username || user.phone}</p>
                          <p className="text-sm text-fb-text-secondary">
                            {user.phone} • {user.first_login_at ? new Date(user.first_login_at).toLocaleDateString('ru-RU') : 'Не входил'} • {new Date(user.created_at).toLocaleDateString('ru-RU')}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-3">
                        <button
                          onClick={async () => {
                            const newStatus = user.status === 'active' ? 'blocked' : 'active'
                            try {
                              const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
                              
                              const response = await fetch(`${backendUrl}/api/users/${user.id}/status`, {
                                method: 'PATCH',
                                headers: {
                                  'Content-Type': 'application/json',
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ status: newStatus }),
                              })
                              if (response.ok) {
                                fetchUsers()
                              } else {
                                alert('Ошибка обновления статуса пользователя')
                              }
                            } catch (err) {
                              alert('Ошибка подключения к серверу')
                            }
                          }}
                          className={`px-3 py-1 rounded-full text-sm font-semibold cursor-pointer transition-colors ${
                            user.status === 'active'
                              ? 'bg-green-100 text-green-800 hover:bg-green-200'
                              : 'bg-red-100 text-red-800 hover:bg-red-200'
                          }`}
                        >
                          {user.status === 'active' ? 'Активен' : 'Заблокирован'}
                        </button>
                        <button
                          onClick={async () => {
                            if (confirm(`Удалить пользователя ${user.username || user.phone}?`)) {
                              try {
                                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
                                
                                const response = await fetch(`${backendUrl}/api/users/${user.id}`, {
                                  method: 'DELETE',
                                  headers: { 'Content-Type': 'application/json' },
                                })
                                if (response.ok) {
                                  fetchUsers()
                                } else {
                                  alert('Ошибка удаления пользователя')
                                }
                              } catch (err) {
                                alert('Ошибка подключения к серверу')
                              }
                            }
                          }}
                          className="text-red-600 hover:text-red-700 px-3 py-1 rounded-lg hover:bg-red-50 transition-colors"
                        >
                          Удалить
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      </div>

      {/* Modal добавления пользователя */}
      {/* Modal для загрузки документов */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold text-fb-text mb-4">Загрузить документы</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-fb-text mb-2">
                  Выберите файлы (TXT, DOCX, PDF)
                </label>
                <input
                  type="file"
                  multiple
                  accept=".txt,.docx,.pdf"
                  onChange={(e) => {
                    const files = Array.from(e.target.files || [])
                    setUploadFiles(files)
                  }}
                  className="block w-full text-sm text-fb-text-secondary
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-lg file:border-0
                    file:text-sm file:font-semibold
                    file:bg-fb-blue file:text-white
                    hover:file:bg-fb-blue-dark
                    file:cursor-pointer"
                />
                <p className="text-xs text-fb-text-secondary mt-2">
                  Можно загрузить несколько файлов одновременно
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-4 pt-4 border-t border-fb-gray-dark">
              <button
                type="button"
                onClick={() => {
                  setShowUploadModal(false)
                  setUploadFiles([])
                }}
                disabled={uploading}
                className="px-4 py-2 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (uploadFiles.length === 0) {
                    alert('Выберите хотя бы один файл')
                    return
                  }
                  
                  setUploading(true)
                  try {
                    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
                    
                    
                    const formData = new FormData()
                    uploadFiles.forEach(file => {
                      formData.append('files', file)
                    })
                    
                    const response = await fetch(`${backendUrl}/api/documents/${projectId}/upload`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                      },
                      body: formData,
                    })
                    
                    if (response.ok) {
                      setShowUploadModal(false)
                      setUploadFiles([])
                      fetchDocuments()
                    } else {
                      const errorData = await response.json().catch(() => ({ detail: 'Ошибка загрузки документов' }))
                      alert(errorData.detail || 'Ошибка загрузки документов')
                    }
                  } catch (err) {
                    alert('Ошибка подключения к серверу')
                  } finally {
                    setUploading(false)
                  }
                }}
                disabled={uploading || uploadFiles.length === 0}
                className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? 'Загрузка...' : 'Загрузить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAddUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold text-fb-text mb-4">Добавить пользователя</h2>
            
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded mb-4">
                <p className="font-medium">{error}</p>
              </div>
            )}

            <form onSubmit={async (e) => {
              e.preventDefault()
              setError('')
              setAddingUser(true)

              try {
                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
                
                const response = await fetch(`${backendUrl}/api/users/project/${projectId}`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    phone: newUserPhone,
                    username: newUserUsername || null,
                  }),
                })

                if (response.ok) {
                  setShowAddUserModal(false)
                  setNewUserPhone('')
                  setNewUserUsername('')
                  fetchUsers()
                } else {
                  const errorData = await response.json()
                  setError(errorData.detail || 'Ошибка создания пользователя')
                }
              } catch (err) {
                setError('Ошибка подключения к серверу')
              } finally {
                setAddingUser(false)
              }
            }}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-2">
                    Номер телефона *
                  </label>
                  <input
                    type="text"
                    required
                    value={newUserPhone}
                    onChange={(e) => setNewUserPhone(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder="+1234567890"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-2">
                    Username (опционально)
                  </label>
                  <input
                    type="text"
                    value={newUserUsername}
                    onChange={(e) => setNewUserUsername(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder="username"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-4 pt-4 border-t border-fb-gray-dark">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddUserModal(false)
                    setNewUserPhone('')
                    setNewUserUsername('')
                    setError('')
                  }}
                  disabled={addingUser}
                  className="px-4 py-2 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={addingUser}
                  className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {addingUser ? 'Добавление...' : 'Добавить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

