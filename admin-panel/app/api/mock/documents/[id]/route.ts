import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../data'

// DELETE /api/mock/documents/[id] - удалить документ
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Ищем документ во всех проектах
    for (const projectId in mockDataStore.documents) {
      const docIndex = mockDataStore.documents[projectId].findIndex(d => d.id === params.id)
      if (docIndex !== -1) {
        mockDataStore.documents[projectId].splice(docIndex, 1)
        return NextResponse.json(null, { status: 204 })
      }
    }

    return NextResponse.json(
      { detail: 'Документ не найден' },
      { status: 404 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка удаления документа' },
      { status: 500 }
    )
  }
}

