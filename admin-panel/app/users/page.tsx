'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../components/Sidebar'

interface User {
  id: string
  project_id: string
  phone: string
  username: string | null
  status: string
  first_login_at: string | null
  created_at: string
}

interface Project {
  id: string
  name: string
}

export default function UsersPage() {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [projects, setProjects] = useState<Record<string, Project>>({})
  const [projectsList, setProjectsList] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAddUserModal, setShowAddUserModal] = useState(false)
  const [newUserPhone, setNewUserPhone] = useState('')
  const [newUserUsername, setNewUserUsername] = useState('')
  const [newUserProjectId, setNewUserProjectId] = useState('')
  const [addingUser, setAddingUser] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editUserPhone, setEditUserPhone] = useState('')
  const [editUserUsername, setEditUserUsername] = useState('')
  const [editUserProjectId, setEditUserProjectId] = useState('')
  const [editUserStatus, setEditUserStatus] = useState('active')
  const [updatingUser, setUpdatingUser] = useState(false)

  useEffect(() => {
    // Автоматически устанавливаем токен, если его нет
    if (typeof window !== 'undefined' && !localStorage.getItem('token')) {
      localStorage.setItem('token', 'auto-login-token')
    }
    fetchData()
  }, [router])

  const fetchData = async () => {
    try {
      setError('')
      const { getApiUrl } = await import('../lib/api-helpers')

      // Загружаем все проекты
      const projectsRes = await fetch(getApiUrl('/api/projects'), {
        headers: { 'Content-Type': 'application/json' },
      })

      if (!projectsRes.ok) {
        throw new Error(`Ошибка загрузки проектов: ${projectsRes.status}`)
      }

      const projectsData = await projectsRes.json()
      const projectsMap: Record<string, Project> = {}
      projectsData.forEach((project: Project) => {
        projectsMap[project.id] = project
      })
      setProjects(projectsMap)
      setProjectsList(projectsData)

      // Загружаем всех пользователей из всех проектов
      const allUsers: User[] = []
      for (const project of projectsData) {
        try {
          const usersRes = await fetch(getApiUrl(`/api/users/project/${project.id}`), {
            headers: { 'Content-Type': 'application/json' },
          })
          if (usersRes.ok) {
            const usersData = await usersRes.json()
            allUsers.push(...usersData)
          }
        } catch (err) {
          console.error(`Ошибка загрузки пользователей проекта ${project.id}:`, err)
        }
      }
      setUsers(allUsers)
    } catch (err) {
      setError('Ошибка загрузки данных: ' + (err instanceof Error ? err.message : 'Неизвестная ошибка'))
      console.error('Fetch error:', err)
    } finally {
      setLoading(false)
    }
  }


  const handleDelete = async (userId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этого пользователя?')) {
      return
    }

    try {
      const { getApiUrl } = await import('../lib/api-helpers')
      
      const response = await fetch(getApiUrl(`/api/users/${userId}`), {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      })
      if (response.ok) {
        fetchData()
      } else {
        alert('Ошибка удаления пользователя')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }

  const handleStatusChange = async (userId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'blocked' : 'active'
    try {
      const { getApiUrl } = await import('../lib/api-helpers')
      
      const response = await fetch(getApiUrl(`/api/users/${userId}/status`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      })
      if (response.ok) {
        fetchData()
      } else {
        alert('Ошибка обновления статуса пользователя')
      }
    } catch (err) {
      alert('Ошибка подключения к серверу')
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    // В режиме без логина просто обновляем страницу
    window.location.reload()
  }

  const handleEditUser = (user: User) => {
    setEditingUser(user)
    setEditUserPhone(user.phone)
    setEditUserUsername(user.username || '')
    setEditUserProjectId(user.project_id)
    setEditUserStatus(user.status)
    setError('')
  }

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    setUpdatingUser(true)
    setError('')

    try {
      const { getApiUrl } = await import('../lib/api-helpers')
      
      const updateData: any = {}
      if (editUserPhone !== editingUser.phone) updateData.phone = editUserPhone
      if (editUserUsername !== (editingUser.username || '')) updateData.username = editUserUsername || null
      if (editUserProjectId !== editingUser.project_id) updateData.project_id = editUserProjectId
      if (editUserStatus !== editingUser.status) updateData.status = editUserStatus

      const response = await fetch(getApiUrl(`/api/users/${editingUser.id}`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      })

      if (response.ok) {
        setEditingUser(null)
        setEditUserPhone('')
        setEditUserUsername('')
        setEditUserProjectId('')
        setEditUserStatus('active')
        fetchData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Ошибка обновления пользователя')
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setUpdatingUser(false)
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
                onClick={handleLogout}
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
          <div className="mb-4 flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-fb-text">Все пользователи</h2>
              <p className="text-fb-text-secondary mt-1 text-sm">Управление всеми пользователями системы</p>
            </div>
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

          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded mb-4">
              <p className="font-medium">{error}</p>
            </div>
          )}

          {users.length === 0 ? (
            <div className="bg-white rounded-lg shadow-sm p-6 text-center">
              <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              <p className="text-fb-text-secondary">Нет пользователей</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-fb-gray-dark">
                  <thead className="bg-fb-gray">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        Пользователь
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        Проект
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        Статус
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        Дата создания
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        Действия
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-fb-gray-dark">
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-fb-gray transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="w-8 h-8 bg-fb-blue rounded-full flex items-center justify-center text-white font-semibold text-sm mr-2">
                              {user.phone.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-fb-text">
                                {user.username || user.phone}
                              </div>
                              <div className="text-sm text-fb-text-secondary">{user.phone}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <Link
                            href={`/projects/${user.project_id}`}
                            className="text-sm text-fb-blue hover:text-fb-blue-dark font-medium"
                          >
                            {projects[user.project_id]?.name || 'Неизвестный проект'}
                          </Link>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <button
                            onClick={() => handleStatusChange(user.id, user.status)}
                            className={`px-3 py-1 rounded-full text-sm font-semibold cursor-pointer transition-colors ${
                              user.status === 'active'
                                ? 'bg-green-100 text-green-800 hover:bg-green-200'
                                : 'bg-red-100 text-red-800 hover:bg-red-200'
                            }`}
                          >
                            {user.status === 'active' ? 'Активен' : 'Заблокирован'}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-fb-text-secondary">
                          {new Date(user.created_at).toLocaleDateString('ru-RU')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm space-x-3">
                          <button
                            onClick={() => handleEditUser(user)}
                            className="text-fb-blue hover:text-fb-blue-dark font-medium"
                          >
                            Редактировать
                          </button>
                          <button
                            onClick={() => handleDelete(user.id)}
                            className="text-red-600 hover:text-red-700 font-medium"
                          >
                            Удалить
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Modal добавления пользователя */}
      {showAddUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold text-fb-text mb-4">Добавить пользователя</h2>
            
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-2 rounded mb-3 text-sm">
                <p className="font-medium">{error}</p>
              </div>
            )}

            <form onSubmit={async (e) => {
              e.preventDefault()
              setError('')
              setAddingUser(true)

              if (!newUserProjectId) {
                setError('Выберите проект')
                setAddingUser(false)
                return
              }

              try {
                const { getApiUrl } = await import('../lib/api-helpers')
                
                const response = await fetch(getApiUrl(`/api/users/project/${newUserProjectId}`), {
                  method: 'POST',
                  headers: {
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
                  setNewUserProjectId('')
                  fetchData()
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
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    Проект *
                  </label>
                  <select
                    required
                    value={newUserProjectId}
                    onChange={(e) => setNewUserProjectId(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  >
                    <option value="">Выберите проект</option>
                    {projectsList.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
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
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
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
                    setNewUserProjectId('')
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

      {/* Modal редактирования пользователя */}
      {editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold text-fb-text mb-6">Редактировать пользователя</h2>
            
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded mb-4">
                <p className="font-medium">{error}</p>
              </div>
            )}

            <form onSubmit={handleUpdateUser}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    Проект *
                  </label>
                  <select
                    required
                    value={editUserProjectId}
                    onChange={(e) => setEditUserProjectId(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  >
                    <option value="">Выберите проект</option>
                    {projectsList.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    Номер телефона *
                  </label>
                  <input
                    type="text"
                    required
                    value={editUserPhone}
                    onChange={(e) => setEditUserPhone(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder="+1234567890"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    Username (опционально)
                  </label>
                  <input
                    type="text"
                    value={editUserUsername}
                    onChange={(e) => setEditUserUsername(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder="username"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    Статус *
                  </label>
                  <select
                    required
                    value={editUserStatus}
                    onChange={(e) => setEditUserStatus(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  >
                    <option value="active">Активен</option>
                    <option value="blocked">Заблокирован</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-4 pt-4 border-t border-fb-gray-dark">
                <button
                  type="button"
                  onClick={() => {
                    setEditingUser(null)
                    setEditUserPhone('')
                    setEditUserUsername('')
                    setEditUserProjectId('')
                    setEditUserStatus('active')
                    setError('')
                  }}
                  disabled={updatingUser}
                  className="px-4 py-2 border border-fb-gray-dark rounded-lg text-fb-text font-semibold hover:bg-fb-gray-dark transition-colors disabled:opacity-50"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={updatingUser}
                  className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {updatingUser ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

