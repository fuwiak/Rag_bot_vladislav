import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../data'

// GET /api/mock/documents/[projectId] - получить документы проекта
export async function GET(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    const documents = mockDataStore.documents[params.projectId] || []

    return NextResponse.json(documents, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки документов' },
      { status: 500 }
    )
  }
}

// POST /api/mock/documents/[projectId]/upload - загрузить документы
export async function POST(
  request: NextRequest,
  { params }: { params: { projectId: string } }
) {
  try {
    // В моке просто возвращаем успех
    // В реальном приложении здесь была бы загрузка файлов
    const formData = await request.formData()
    const files = formData.getAll('files') as File[]

    if (!files || files.length === 0) {
      return NextResponse.json(
        { detail: 'Файлы не предоставлены' },
        { status: 400 }
      )
    }

    // Добавляем фиктивные документы
    if (!mockDataStore.documents[params.projectId]) {
      mockDataStore.documents[params.projectId] = []
    }

    files.forEach((file, index) => {
      const newDoc = {
        id: `doc-${Date.now()}-${index}`,
        project_id: params.projectId,
        filename: file.name,
        file_type: file.name.split('.').pop() || 'txt',
        created_at: new Date().toISOString(),
      }
      mockDataStore.documents[params.projectId].push(newDoc)
    })

    return NextResponse.json(
      { message: 'Документы успешно загружены', count: files.length },
      { status: 200 }
    )
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки документов' },
      { status: 500 }
    )
  }
}

