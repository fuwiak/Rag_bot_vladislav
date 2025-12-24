import { NextRequest, NextResponse } from 'next/server'
import { mockModels } from '../../data'

// GET /api/mock/models/global-settings - получить глобальные настройки моделей
export async function GET(request: NextRequest) {
  try {
    return NextResponse.json({
      primary_model_id: mockModels[0]?.id || null,
      fallback_model_id: mockModels[1]?.id || null,
    }, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки настроек' },
      { status: 500 }
    )
  }
}

// PATCH /api/mock/models/global-settings - обновить глобальные настройки
export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    
    // В моке просто возвращаем обновленные настройки
    return NextResponse.json({
      primary_model_id: body.primary_model_id || null,
      fallback_model_id: body.fallback_model_id || null,
    }, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка обновления настроек' },
      { status: 500 }
    )
  }
}


