import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../../data'

// POST /api/mock/bots/[projectId]/stop - остановить бота
export async function POST(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const botIndex = mockDataStore.bots.findIndex(b => b.project_id === params.projectId)
    
    if (botIndex !== -1) {
      mockDataStore.bots[botIndex].is_active = false
    }

    return NextResponse.json(
      { message: 'Бот успешно остановлен' },
      { status: 200 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка остановки бота' },
      { status: 500 }
    )
  }
}


