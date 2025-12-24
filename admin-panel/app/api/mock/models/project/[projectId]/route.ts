import { NextRequest, NextResponse } from 'next/server'

// PATCH /api/mock/models/project/[projectId] - установить модель для проекта
export async function PATCH(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const searchParams = request.nextUrl.searchParams
    const modelId = searchParams.get('model_id')

    if (!modelId) {
      return NextResponse.json(
        { detail: 'model_id обязателен' },
        { status: 400 }
      )
    }

    // В моке просто возвращаем успех
    return NextResponse.json(
      { message: 'Модель успешно установлена для проекта', model_id: modelId },
      { status: 200 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка установки модели' },
      { status: 500 }
    )
  }
}

