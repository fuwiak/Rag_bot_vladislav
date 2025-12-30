import { NextRequest, NextResponse } from 'next/server'

export async function POST(
  request: NextRequest,
  { params }: { params: { action: string } }
) {
  try {
    const body = await request.json()
    const { project_id } = body
    const { action } = params

    if (!project_id) {
      return NextResponse.json(
        { detail: 'Missing required field: project_id' },
        { status: 400 }
      )
    }

    if (action !== 'create' && action !== 'delete') {
      return NextResponse.json(
        { detail: 'Invalid action. Use "create" or "delete"' },
        { status: 400 }
      )
    }

    // Forward to backend API
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const response = await fetch(`${backendUrl}/api/rag/collections/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': request.headers.get('Authorization') || '',
      },
      body: JSON.stringify({
        project_id,
        action: action,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(error, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error('Error in RAG collection management API:', error)
    return NextResponse.json(
      { detail: error.message || 'Internal server error' },
      { status: 500 }
    )
  }
}

