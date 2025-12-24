import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../../data'

// PATCH /api/mock/users/[id]/status - изменить статус пользователя
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const { status: newStatus } = body

    if (!newStatus || !['active', 'blocked'].includes(newStatus)) {
      return NextResponse.json(
        { detail: 'Некорректный статус' },
        { status: 400 }
      )
    }

    // Ищем пользователя во всех проектах
    for (const projectId in mockDataStore.users) {
      const userIndex = mockDataStore.users[projectId].findIndex(u => u.id === params.id)
      if (userIndex !== -1) {
        mockDataStore.users[projectId][userIndex].status = newStatus
        return NextResponse.json(mockDataStore.users[projectId][userIndex], { status: 200 })
      }
    }

    return NextResponse.json(
      { detail: 'Пользователь не найден' },
      { status: 404 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка обновления статуса' },
      { status: 500 }
    )
  }
}


