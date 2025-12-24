import { NextRequest, NextResponse } from 'next/server'

// POST /api/mock/models/custom - добавить кастомную модель
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { model_id, name } = body

    if (!model_id || !name) {
      return NextResponse.json(
        { detail: 'model_id и name обязательны' },
        { status: 400 }
      )
    }

    // В моке просто возвращаем успех
    return NextResponse.json(
      { 
        message: 'Кастомная модель успешно добавлена',
        model_id,
        name,
      },
      { status: 201 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка добавления модели' },
      { status: 500 }
    )
  }
}


