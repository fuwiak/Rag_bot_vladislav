import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../data'

// GET /api/mock/bots/info - получить информацию о ботах
export async function GET(request: NextRequest) {
  try {
    return NextResponse.json(mockDataStore.bots, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки информации о ботах' },
      { status: 500 }
    )
  }
}


