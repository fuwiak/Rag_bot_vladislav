'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '../components/Sidebar'

interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    fetchProjects()
  }, [router])

  const fetchProjects = async () => {
    try {
      const { getApiUrl } = await import('../lib/api-helpers')
      const response = await fetch(getApiUrl('/api/projects'), {
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const data = await response.json()
        setProjects(data)
      }
    } catch (err) {
      console.error('Error fetching projects:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    // В режиме без логина просто обновляем страницу
    window.location.reload()
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
          <h2 className="text-2xl font-bold text-fb-text">Проекты</h2>
          <Link
            href="/projects/new"
            className="bg-fb-blue hover:bg-fb-blue-dark text-white px-6 py-3 rounded-lg font-semibold shadow-md transition-colors duration-200"
          >
            + Создать проект
          </Link>
        </div>

        {projects.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-6 text-center">
            <div className="max-w-md mx-auto">
              <svg className="mx-auto h-12 w-12 text-fb-text-secondary mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-xl font-semibold text-fb-text mb-2">Нет проектов</h3>
              <p className="text-fb-text-secondary mb-4">Создайте первый проект для начала работы</p>
              <Link
                href="/projects/new"
                className="inline-block bg-fb-blue hover:bg-fb-blue-dark text-white px-6 py-3 rounded-lg font-semibold transition-colors duration-200"
              >
                Создать проект
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
    </div>
  )
}

