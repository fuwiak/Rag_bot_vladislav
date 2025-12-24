import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../data'

// PATCH /api/mock/users/[id] - обновить пользователя
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()

    // Ищем пользователя во всех проектах
    for (const projectId in mockDataStore.users) {
      const userIndex = mockDataStore.users[projectId].findIndex(u => u.id === params.id)
      if (userIndex !== -1) {
        const updatedUser = {
          ...mockDataStore.users[projectId][userIndex],
          ...body,
        }
        mockDataStore.users[projectId][userIndex] = updatedUser
        return NextResponse.json(updatedUser, { status: 200 })
      }
    }

    return NextResponse.json(
      { detail: 'Пользователь не найден' },
      { status: 404 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка обновления пользователя' },
      { status: 500 }
    )
  }
}

// DELETE /api/mock/users/[id] - удалить пользователя
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Ищем пользователя во всех проектах
    for (const projectId in mockDataStore.users) {
      const userIndex = mockDataStore.users[projectId].findIndex(u => u.id === params.id)
      if (userIndex !== -1) {
        mockDataStore.users[projectId].splice(userIndex, 1)
        return NextResponse.json(null, { status: 204 })
      }
    }

    return NextResponse.json(
      { detail: 'Пользователь не найден' },
      { status: 404 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка удаления пользователя' },
      { status: 500 }
    )
  }
}


