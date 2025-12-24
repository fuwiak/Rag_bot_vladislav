import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../data'

// GET /api/mock/projects - получить список проектов
export async function GET(request: NextRequest) {
  try {
    // Возвращаем упрощенный список проектов для dashboard
    const projects = mockDataStore.projects.map(p => ({
      id: p.id,
      name: p.name,
      description: p.description,
      created_at: p.created_at,
    }))

    return NextResponse.json(projects, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки проектов' },
      { status: 500 }
    )
  }
}

// POST /api/mock/projects - создать новый проект
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { name, description, access_password, prompt_template, max_response_length, bot_token } = body

    const newProject = {
      id: `550e8400-e29b-41d4-a716-44665544${Math.random().toString(36).substring(2, 10)}`,
      name: name || 'Новый проект',
      description: description || null,
      bot_token: bot_token || null,
      access_password: access_password || 'demo123',
      prompt_template: prompt_template || 'Контекст: {chunks}\nВопрос: {question}\nМаксимальная длина: {max_length}',
      max_response_length: max_response_length || 1000,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    mockDataStore.projects.push(newProject)
    mockDataStore.documents[newProject.id] = []
    mockDataStore.users[newProject.id] = []

    return NextResponse.json(newProject, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка создания проекта' },
      { status: 500 }
    )
  }
}


