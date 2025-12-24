import { NextRequest, NextResponse } from 'next/server'
import { mockDataStore } from '../../data'

// GET /api/mock/projects/[id] - получить проект по ID
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const project = mockDataStore.projects.find(p => p.id === params.id)

    if (!project) {
      return NextResponse.json(
        { detail: 'Проект не найден' },
        { status: 404 }
      )
    }

    return NextResponse.json(project, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка загрузки проекта' },
      { status: 500 }
    )
  }
}

// PUT /api/mock/projects/[id] - обновить проект
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const projectIndex = mockDataStore.projects.findIndex(p => p.id === params.id)

    if (projectIndex === -1) {
      return NextResponse.json(
        { detail: 'Проект не найден' },
        { status: 404 }
      )
    }

    const updatedProject = {
      ...mockDataStore.projects[projectIndex],
      ...body,
      updated_at: new Date().toISOString(),
    }

    mockDataStore.projects[projectIndex] = updatedProject

    return NextResponse.json(updatedProject, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка обновления проекта' },
      { status: 500 }
    )
  }
}

// DELETE /api/mock/projects/[id] - удалить проект
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const projectIndex = mockDataStore.projects.findIndex(p => p.id === params.id)

    if (projectIndex === -1) {
      return NextResponse.json(
        { detail: 'Проект не найден' },
        { status: 404 }
      )
    }

    mockDataStore.projects.splice(projectIndex, 1)
    delete mockDataStore.documents[params.id]
    delete mockDataStore.users[params.id]

    return NextResponse.json(null, { status: 204 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка удаления проекта' },
      { status: 500 }
    )
  }
}


