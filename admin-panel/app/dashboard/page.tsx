'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../components/Sidebar'
import LanguageSwitcher from '../components/LanguageSwitcher'
import ResetPasswordModal from '../components/ResetPasswordModal'
import { cache, cacheKeys } from '../lib/cache'
import { useI18n } from '../lib/i18n/context'

interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showResetPassword, setShowResetPassword] = useState(false)
  const router = useRouter()
  const { t } = useI18n()

  useEffect(() => {
    fetchProjects()
  }, [router])

  const fetchProjects = async (useCache = true) => {
    // Показываем кэшированные данные сразу, если есть
    if (useCache) {
      const cachedProjects = cache.get<Project[]>(cacheKeys.projects)
      if (cachedProjects) {
        setProjects(cachedProjects)
        setLoading(false)
        // Обновляем данные в фоне
        fetchProjects(false)
        return
      }
    }

    try {
      const { apiFetch } = await import('../lib/api-helpers')
      // Не добавляем timestamp при использовании кэша
      const response = await apiFetch(`/api/projects`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setProjects(data)
        // Сохраняем в кэш на 2 минуты
        cache.set(cacheKeys.projects, data, 2 * 60 * 1000)
      } else if (response.status === 401 || response.status === 403) {
        console.error('Authentication error:', response.status)
        // Если нет токена, можно попробовать установить дефолтный токен
        if (typeof window !== 'undefined' && !localStorage.getItem('token')) {
          localStorage.setItem('token', 'dummy-token')
          // Повторяем запрос
          const retryResponse = await apiFetch(`/api/projects`, {
            cache: 'no-store',
            headers: {
              'Cache-Control': 'no-cache, no-store, must-revalidate',
              'Pragma': 'no-cache',
              'Expires': '0'
            }
          })
          if (retryResponse.ok) {
            const data = await retryResponse.json()
            setProjects(data)
            cache.set(cacheKeys.projects, data, 2 * 60 * 1000)
          }
        }
      } else {
        // При ошибке используем кэш, если есть
        const cachedProjects = cache.get<Project[]>(cacheKeys.projects)
        if (cachedProjects) {
          setProjects(cachedProjects)
        } else {
          setProjects([])
        }
      }
    } catch (err) {
      console.error('Error fetching projects:', err)
      // При ошибке используем кэш, если есть
      const cachedProjects = cache.get<Project[]>(cacheKeys.projects)
      if (cachedProjects) {
        setProjects(cachedProjects)
      } else {
        setProjects([])
      }
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    router.push('/login')
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
      
      {/* Navbar w stylu Facebook */}
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
          <h2 className="text-2xl font-bold text-fb-text">{t('dashboard.title')}</h2>
          <Link
            href="/projects/new"
            className="bg-fb-blue hover:bg-fb-blue-dark text-white px-6 py-3 rounded-lg font-semibold shadow-md transition-colors duration-200"
          >
            + {t('dashboard.createProject')}
          </Link>
        </div>

        {projects.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-6 text-center">
            <div className="max-w-md mx-auto">
              <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-xl font-semibold text-fb-text mb-2">{t('dashboard.noProjects')}</h3>
              <p className="text-fb-text-secondary mb-4">{t('dashboard.noProjectsDescription')}</p>
              <Link
                href="/projects/new"
                className="inline-block bg-fb-blue hover:bg-fb-blue-dark text-white px-6 py-3 rounded-lg font-semibold transition-colors duration-200"
              >
                {t('dashboard.createProject')}
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200 border border-fb-gray-dark hover:border-fb-blue overflow-hidden"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-lg font-semibold text-fb-text">{project.name}</h3>
                    <svg className="h-5 w-5 text-fb-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                  {project.description && (
                    <p className="text-sm text-fb-text-secondary mb-4 line-clamp-2">{project.description}</p>
                  )}
                  <div className="flex items-center text-xs text-fb-text-secondary">
                    <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(project.created_at).toLocaleDateString('ru-RU', { 
                      day: 'numeric', 
                      month: 'long', 
                      year: 'numeric' 
                    })}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
        </main>
      </div>
      
      <ResetPasswordModal
        isOpen={showResetPassword}
        onClose={() => setShowResetPassword(false)}
      />
    </div>
  )
}

