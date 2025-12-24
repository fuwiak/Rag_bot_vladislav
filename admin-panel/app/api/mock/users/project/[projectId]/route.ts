import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../../data'

// GET /api/mock/users/project/[projectId] - получить пользователей проекта
export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const users = mockDataStore.users[params.projectId] || []

    return NextResponse.json(users, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки пользователей' },
      { status: 500 }
    )
  }
}

// POST /api/mock/users/project/[projectId] - создать пользователя
export async function POST(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const body = await request.json()
    const { phone, username } = body

    if (!phone) {
      return NextResponse.json(
        { detail: 'Номер телефона обязателен' },
        { status: 400 }
      )
    }

    if (!mockDataStore.users[params.projectId]) {
      mockDataStore.users[params.projectId] = []
    }

    const newUser = {
      id: `user-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      project_id: params.projectId,
      phone,
      username: username || null,
      status: 'active',
      first_login_at: null,
      created_at: new Date().toISOString(),
    }

    mockDataStore.users[params.projectId].push(newUser)

    return NextResponse.json(newUser, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка создания пользователя' },
      { status: 500 }
    )
  }
}


