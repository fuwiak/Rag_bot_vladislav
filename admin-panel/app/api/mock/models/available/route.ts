import { NextRequest, NextResponse } from 'next/server'
import { mockModels } from '../../data'

// GET /api/mock/models/available - получить доступные модели
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const search = searchParams.get('search') || ''

    let models = mockModels

    // Фильтрация по поисковому запросу
    if (search) {
      const searchLower = search.toLowerCase()
      models = models.filter(m =>
        m.name.toLowerCase().includes(searchLower) ||
        m.provider.toLowerCase().includes(searchLower) ||
        m.id.toLowerCase().includes(searchLower)
      )
    }

    return NextResponse.json(models, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки моделей' },
      { status: 500 }
    )
  }
}

