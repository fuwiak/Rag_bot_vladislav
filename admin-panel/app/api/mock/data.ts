// Mock данные для демонстрации UI без backend

export interface MockProject {
  id: string
  name: string
  description: string | null
  bot_token: string | null
  access_password: string
  prompt_template: string
  max_response_length: number
  created_at: string
  updated_at: string
}

export interface MockDocument {
  id: string
  project_id: string
  filename: string
  file_type: string
  created_at: string
}

export interface MockUser {
  id: string
  project_id: string
  phone: string
  username: string | null
  status: string
  first_login_at: string | null
  created_at: string
}

export interface MockBotInfo {
  project_id: string
  project_name: string
  bot_token: string | null
  bot_username: string | null
  bot_url: string | null
  bot_first_name: string | null
  is_active: boolean
  users_count: number
}

export interface MockModel {
  id: string
  name: string
  provider: string
  context_length?: number
  pricing?: any
  is_custom?: boolean
}

// Тестовые проекты
export const mockProjects: MockProject[] = [
  {
    id: '550e8400-e29b-41d4-a716-446655440000',
    name: 'Проект поддержки клиентов',
    description: 'Бот для ответов на вопросы клиентов о продуктах и услугах',
    bot_token: '123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
    access_password: 'demo123',
    prompt_template: 'Ты помощник службы поддержки. Отвечай на вопросы клиентов на основе предоставленных документов.\n\nКонтекст из документов:\n{chunks}\n\nВопрос клиента: {question}\n\nМаксимальная длина ответа: {max_length} символов.',
    max_response_length: 1000,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-20T14:45:00Z',
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440001',
    name: 'Внутренний справочник HR',
    description: 'Бот для сотрудников с информацией о политике компании',
    bot_token: null,
    access_password: 'hr2024',
    prompt_template: 'Ты помощник HR отдела. Отвечай на вопросы сотрудников на основе внутренних документов.\n\nКонтекст:\n{chunks}\n\nВопрос: {question}\n\nМаксимальная длина: {max_length} символов.',
    max_response_length: 2000,
    created_at: '2024-01-10T09:00:00Z',
    updated_at: '2024-01-18T16:20:00Z',
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440002',
    name: 'Техническая документация',
    description: 'Бот для разработчиков с технической документацией',
    bot_token: '987654321:XYZabcDEFghiJKLmnoPQRstuv',
    access_password: 'dev2024',
    prompt_template: 'Ты технический помощник. Отвечай на вопросы разработчиков на основе технической документации.\n\nДокументация:\n{chunks}\n\nВопрос: {question}\n\nМаксимальная длина ответа: {max_length} символов.',
    max_response_length: 1500,
    created_at: '2024-01-05T11:15:00Z',
    updated_at: '2024-01-22T10:30:00Z',
  },
]

// Тестовые документы
export const mockDocuments: Record<string, MockDocument[]> = {
  '550e8400-e29b-41d4-a716-446655440000': [
    {
      id: 'doc-001',
      project_id: '550e8400-e29b-41d4-a716-446655440000',
      filename: 'FAQ_Продукты.pdf',
      file_type: 'pdf',
      created_at: '2024-01-16T12:00:00Z',
    },
    {
      id: 'doc-002',
      project_id: '550e8400-e29b-41d4-a716-446655440000',
      filename: 'Политика_возврата.txt',
      file_type: 'txt',
      created_at: '2024-01-17T14:30:00Z',
    },
  ],
  '550e8400-e29b-41d4-a716-446655440001': [
    {
      id: 'doc-003',
      project_id: '550e8400-e29b-41d4-a716-446655440001',
      filename: 'Правила_трудового_распорядка.docx',
      file_type: 'docx',
      created_at: '2024-01-11T09:00:00Z',
    },
    {
      id: 'doc-004',
      project_id: '550e8400-e29b-41d4-a716-446655440001',
      filename: 'Политика_отпусков.pdf',
      file_type: 'pdf',
      created_at: '2024-01-12T10:15:00Z',
    },
  ],
  '550e8400-e29b-41d4-a716-446655440002': [
    {
      id: 'doc-005',
      project_id: '550e8400-e29b-41d4-a716-446655440002',
      filename: 'API_Документация.md',
      file_type: 'txt',
      created_at: '2024-01-06T13:00:00Z',
    },
  ],
}

// Тестовые пользователи
export const mockUsers: Record<string, MockUser[]> = {
  '550e8400-e29b-41d4-a716-446655440000': [
    {
      id: 'user-001',
      project_id: '550e8400-e29b-41d4-a716-446655440000',
      phone: '+79001234567',
      username: 'Иван Иванов',
      status: 'active',
      first_login_at: '2024-01-16T15:00:00Z',
      created_at: '2024-01-15T11:00:00Z',
    },
    {
      id: 'user-002',
      project_id: '550e8400-e29b-41d4-a716-446655440000',
      phone: '+79001234568',
      username: 'Мария Петрова',
      status: 'active',
      first_login_at: '2024-01-17T10:30:00Z',
      created_at: '2024-01-15T11:05:00Z',
    },
  ],
  '550e8400-e29b-41d4-a716-446655440001': [
    {
      id: 'user-003',
      project_id: '550e8400-e29b-41d4-a716-446655440001',
      phone: '+79001234569',
      username: 'Алексей Сидоров',
      status: 'active',
      first_login_at: '2024-01-11T09:30:00Z',
      created_at: '2024-01-10T09:30:00Z',
    },
  ],
  '550e8400-e29b-41d4-a716-446655440002': [
    {
      id: 'user-004',
      project_id: '550e8400-e29b-41d4-a716-446655440002',
      phone: '+79001234570',
      username: null,
      status: 'blocked',
      first_login_at: null,
      created_at: '2024-01-05T12:00:00Z',
    },
  ],
}

// Тестовые боты
export const mockBots: MockBotInfo[] = [
  {
    project_id: '550e8400-e29b-41d4-a716-446655440000',
    project_name: 'Проект поддержки клиентов',
    bot_token: '123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
    bot_username: 'support_bot',
    bot_url: 'https://t.me/support_bot',
    bot_first_name: 'Support Bot',
    is_active: true,
    users_count: 2,
  },
  {
    project_id: '550e8400-e29b-41d4-a716-446655440002',
    project_name: 'Техническая документация',
    bot_token: '987654321:XYZabcDEFghiJKLmnoPQRstuv',
    bot_username: 'tech_doc_bot',
    bot_url: 'https://t.me/tech_doc_bot',
    bot_first_name: 'Tech Doc Bot',
    is_active: true,
    users_count: 1,
  },
  {
    project_id: '550e8400-e29b-41d4-a716-446655440001',
    project_name: 'Внутренний справочник HR',
    bot_token: null,
    bot_username: null,
    bot_url: null,
    bot_first_name: null,
    is_active: false,
    users_count: 1,
  },
]

// Тестовые модели
export const mockModels: MockModel[] = [
  {
    id: 'x-ai/grok-4.1-fast',
    name: 'Grok 4.1 Fast',
    provider: 'x-ai',
    context_length: 128000,
    pricing: { prompt: '0.0001', completion: '0.0003' },
    is_custom: false,
  },
  {
    id: 'openai/gpt-oss-120b:free',
    name: 'GPT OSS 120B (Free)',
    provider: 'openai',
    context_length: 32768,
    pricing: { prompt: '0', completion: '0' },
    is_custom: false,
  },
  {
    id: 'anthropic/claude-3.5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'anthropic',
    context_length: 200000,
    pricing: { prompt: '0.003', completion: '0.015' },
    is_custom: false,
  },
]

// Хранилище для динамических данных (для POST/PUT/DELETE операций)
export const mockDataStore = {
  projects: [...mockProjects],
  documents: { ...mockDocuments },
  users: { ...mockUsers },
  bots: [...mockBots],
}

