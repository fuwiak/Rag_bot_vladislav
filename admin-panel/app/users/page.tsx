'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../components/Sidebar'
import LanguageSwitcher from '../components/LanguageSwitcher'
import ResetPasswordModal from '../components/ResetPasswordModal'
import { useI18n } from '../lib/i18n/context'

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
  const { t, language } = useI18n()
  const [users, setUsers] = useState<User[]>([])
  const [projects, setProjects] = useState<Record<string, Project>>({})
  const [projectsList, setProjectsList] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showResetPassword, setShowResetPassword] = useState(false)
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

  const fetchData = async (useCache = true) => {
    try {
      setError('')
      
      // Проверяем кэш сначала
      if (useCache) {
        const { cache, cacheKeys } = await import('../lib/cache')
        const cachedUsers = cache.get<User[]>(cacheKeys.allUsers)
        const cachedProjects = cache.get<Project[]>(cacheKeys.projects)
        
        if (cachedUsers && cachedProjects) {
          // Показываем кэшированные данные сразу
          const projectsMap: Record<string, Project> = {}
          cachedProjects.forEach((project: Project) => {
            projectsMap[project.id] = project
          })
          setProjects(projectsMap)
          setProjectsList(cachedProjects)
          setUsers(cachedUsers)
          setLoading(false)
          // Обновляем данные в фоне
          fetchData(false)
          return
        }
      }

      const { apiFetch } = await import('../lib/api-helpers')
      const { cache, cacheKeys } = await import('../lib/cache')

      // Загружаем все проекты
      const projectsRes = await apiFetch('/api/projects')

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

      // Сохраняем проекты в кэш
      cache.set(cacheKeys.projects, projectsData, 2 * 60 * 1000)

      // ✅ РАВНОПАРАЛЛЕЛЬНЫЕ запросы вместо последовательных
      const userPromises = projectsData.map((project: Project) =>
        apiFetch(`/api/users/project/${project.id}`)
          .then(res => res.ok ? res.json() : [])
          .catch((err) => {
          console.error(`Ошибка загрузки пользователей проекта ${project.id}:`, err)
            return []
          })
      )
      
      // Выполняем все запросы параллельно
      const usersResults = await Promise.all(userPromises)
      const allUsers = usersResults.flat()
      
      setUsers(allUsers)
      
      // Сохраняем в кэш на 2 минуты
      cache.set(cacheKeys.allUsers, allUsers, 2 * 60 * 1000)
    } catch (err) {
      setError('Ошибка загрузки данных: ' + (err instanceof Error ? err.message : 'Неизвестная ошибка'))
      console.error('Fetch error:', err)
      
      // При ошибке используем кэш, если есть
      try {
        const { cache, cacheKeys } = await import('../lib/cache')
        const cachedUsers = cache.get<User[]>(cacheKeys.allUsers)
        const cachedProjects = cache.get<Project[]>(cacheKeys.projects)
        if (cachedUsers && cachedProjects) {
          const projectsMap: Record<string, Project> = {}
          cachedProjects.forEach((project: Project) => {
            projectsMap[project.id] = project
          })
          setProjects(projectsMap)
          setProjectsList(cachedProjects)
          setUsers(cachedUsers)
        }
      } catch (cacheErr) {
        console.error('Cache error:', cacheErr)
      }
    } finally {
      setLoading(false)
    }
  }


  const handleDelete = async (userId: string) => {
    if (!confirm(t('users.deleteConfirm'))) {
      return
    }

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      
      const response = await apiFetch(`/api/users/${userId}`, {
        method: 'DELETE',
      })
      if (response.ok) {
        // Очищаем кэш перед обновлением
        const { cache, cacheKeys } = await import('../lib/cache')
        cache.delete(cacheKeys.allUsers)
        fetchData(false) // false = без кэша, wymusza odświeżenie
      } else {
        alert(t('users.deleteError'))
      }
    } catch (err) {
      alert(t('users.addUserModal.connectionError'))
    }
  }

  const handleStatusChange = async (userId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'blocked' : 'active'
    try {
      const { apiFetch } = await import('../lib/api-helpers')
      
      const response = await apiFetch(`/api/users/${userId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      })
      if (response.ok) {
        // Очищаем кэш перед обновлением
        const { cache, cacheKeys } = await import('../lib/cache')
        cache.delete(cacheKeys.allUsers)
        fetchData(false) // false = без кэша, wymusza odświeżenie
      } else {
        alert(t('users.statusUpdateError'))
      }
    } catch (err) {
      alert(t('users.addUserModal.connectionError'))
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    router.push('/login')
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
      const { apiFetch } = await import('../lib/api-helpers')
      
      const updateData: any = {}
      if (editUserPhone !== editingUser.phone) updateData.phone = editUserPhone
      if (editUserUsername !== (editingUser.username || '')) updateData.username = editUserUsername || null
      if (editUserProjectId !== editingUser.project_id) updateData.project_id = editUserProjectId
      if (editUserStatus !== editingUser.status) updateData.status = editUserStatus

      const response = await apiFetch(`/api/users/${editingUser.id}`, {
        method: 'PATCH',
        body: JSON.stringify(updateData),
      })

      if (response.ok) {
        setEditingUser(null)
        setEditUserPhone('')
        setEditUserUsername('')
        setEditUserProjectId('')
        setEditUserStatus('active')
        // Очищаем кэш перед обновлением
        const { cache, cacheKeys } = await import('../lib/cache')
        cache.delete(cacheKeys.allUsers)
        fetchData(false) // false = без кэша, wymusza odświeżenie
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
        <div className="text-fb-text-secondary text-lg">{t('common.loading')}</div>
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
                <h1 className="text-2xl font-bold text-fb-blue hidden sm:block">{t('dashboard.appName')}</h1>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <LanguageSwitcher />
              <button
                onClick={() => setShowResetPassword(true)}
                className="text-fb-text-secondary hover:text-fb-text px-4 py-2 text-sm font-medium rounded-lg hover:bg-fb-gray-dark transition-colors flex items-center space-x-2"
                title="Сброс пароля"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                <span className="hidden sm:inline">Сброс пароля</span>
              </button>
              <button
                onClick={handleLogout}
                className="text-fb-text-secondary hover:text-fb-text px-4 py-2 text-sm font-medium rounded-lg hover:bg-fb-gray-dark transition-colors flex items-center space-x-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>{t('common.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="ml-64">
        <main className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <div className="mb-4 flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-fb-text">{t('users.title')}</h2>
              <p className="text-fb-text-secondary mt-1 text-sm">{t('users.subtitle')}</p>
            </div>
            <button
              onClick={() => setShowAddUserModal(true)}
              className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors flex items-center space-x-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>{t('users.addUser')}</span>
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
              <p className="text-fb-text-secondary">{t('users.noUsers')}</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-fb-gray-dark">
                  <thead className="bg-fb-gray">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        {t('users.user')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        {t('users.project')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        {t('users.status')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        {t('users.createdAt')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-fb-text-secondary uppercase tracking-wider">
                        {t('users.actions')}
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
                            {projects[user.project_id]?.name || t('users.unknownProject')}
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
                            {user.status === 'active' ? t('common.active') : t('common.blocked')}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-fb-text-secondary">
                          {new Date(user.created_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm space-x-3">
                          <button
                            onClick={() => handleEditUser(user)}
                            className="text-fb-blue hover:text-fb-blue-dark font-medium"
                          >
                            {t('common.edit')}
                          </button>
                          <button
                            onClick={() => handleDelete(user.id)}
                            className="text-red-600 hover:text-red-700 font-medium"
                          >
                            {t('common.delete')}
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
            <h2 className="text-xl font-bold text-fb-text mb-4">{t('users.addUserModal.title')}</h2>
            
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
                setError(t('users.addUserModal.selectProjectError'))
                setAddingUser(false)
                return
              }

              try {
                const { apiFetch } = await import('../lib/api-helpers')
                
                const response = await apiFetch(`/api/users/project/${newUserProjectId}`, {
                  method: 'POST',
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
                  // Очищаем кэш перед обновлением
                  const { cache, cacheKeys } = await import('../lib/cache')
                  cache.delete(cacheKeys.allUsers)
                  fetchData(false) // false = без кэша, wymusza odświeżenie
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
                    {t('users.addUserModal.project')} *
                  </label>
                  <select
                    required
                    value={newUserProjectId}
                    onChange={(e) => setNewUserProjectId(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                  >
                    <option value="">{t('users.addUserModal.selectProject')}</option>
                    {projectsList.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    {t('users.addUserModal.phone')} *
                  </label>
                  <input
                    type="text"
                    required
                    value={newUserPhone}
                    onChange={(e) => setNewUserPhone(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder={t('users.addUserModal.phonePlaceholder')}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-fb-text mb-1.5">
                    {t('users.addUserModal.username')}
                  </label>
                  <input
                    type="text"
                    value={newUserUsername}
                    onChange={(e) => setNewUserUsername(e.target.value)}
                    className="block w-full border border-fb-gray-dark rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-fb-blue focus:border-transparent text-fb-text"
                    placeholder={t('users.addUserModal.usernamePlaceholder')}
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
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={addingUser}
                  className="px-4 py-2 bg-fb-blue hover:bg-fb-blue-dark text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {addingUser ? t('users.addUserModal.adding') : t('common.add')}
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
      
      <ResetPasswordModal
        isOpen={showResetPassword}
        onClose={() => setShowResetPassword(false)}
      />
    </div>
  )
}

