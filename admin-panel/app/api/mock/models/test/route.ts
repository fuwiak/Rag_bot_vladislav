import { NextRequest, NextResponse } from 'next/server'

// POST /api/mock/models/test - протестировать модель
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { model_id, messages } = body

    if (!model_id) {
      return NextResponse.json(
        { detail: 'model_id обязателен' },
        { status: 400 }
      )
    }

    // В моке возвращаем фиктивный ответ
    const mockResponse = {
      model: model_id,
      choices: [
        {
          message: {
            role: 'assistant',
            content: 'Это тестовый ответ от Mock API. Модель работает корректно!',
          },
        },
      ],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 15,
        total_tokens: 25,
      },
    }

    return NextResponse.json(mockResponse, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка тестирования модели' },
      { status: 500 }
    )
  }
}


