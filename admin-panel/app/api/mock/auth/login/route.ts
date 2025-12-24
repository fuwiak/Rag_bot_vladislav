import { NextRequest, NextResponse } from 'next/server'

// Mock авторизации - всегда успешная
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { username, password } = body

    // В режиме моков авторизация всегда успешна
    // Генерируем фиктивный токен
    const mockToken = `mock_token_${Date.now()}_${Math.random().toString(36).substring(7)}`

    return NextResponse.json({
      access_token: mockToken,
      token_type: 'bearer',
    }, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      { detail: 'Ошибка авторизации' },
      { status: 400 }
    )
  }
}

