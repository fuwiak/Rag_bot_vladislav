import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../../data'

// POST /api/mock/bots/[projectId]/verify - проверить токен бота
export async function POST(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const body = await request.json()
    const { bot_token } = body

    if (!bot_token) {
      return NextResponse.json(
        { detail: 'Токен бота не предоставлен' },
        { status: 400 }
      )
    }

    // В моке всегда успешная проверка
    // Обновляем информацию о боте
    const botIndex = mockDataStore.bots.findIndex(b => b.project_id === params.projectId)
    if (botIndex !== -1) {
      mockDataStore.bots[botIndex].bot_token = bot_token
      mockDataStore.bots[botIndex].bot_username = 'mock_bot_' + Math.random().toString(36).substring(7)
      mockDataStore.bots[botIndex].bot_url = `https://t.me/${mockDataStore.bots[botIndex].bot_username}`
      mockDataStore.bots[botIndex].bot_first_name = 'Mock Bot'
      mockDataStore.bots[botIndex].is_active = true
    } else {
      // Создаем нового бота, если не существует
      const project = mockDataStore.projects.find(p => p.id === params.projectId)
      mockDataStore.bots.push({
        project_id: params.projectId,
        project_name: project?.name || 'Неизвестный проект',
        bot_token,
        bot_username: 'mock_bot_' + Math.random().toString(36).substring(7),
        bot_url: `https://t.me/mock_bot_${Math.random().toString(36).substring(7)}`,
        bot_first_name: 'Mock Bot',
        is_active: true,
        users_count: 0,
      })
    }

    return NextResponse.json(
      { message: 'Токен успешно проверен и сохранен' },
      { status: 200 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка проверки токена' },
      { status: 500 }
    )
  }
}


