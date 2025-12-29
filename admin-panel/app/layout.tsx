import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { I18nProvider } from './lib/i18n/context'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'RAG Bot Admin Panel',
  description: 'Admin panel for Telegram RAG Bot system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body className={`${inter.className} bg-fb-gray`}>
        <I18nProvider>
          {children}
        </I18nProvider>
      </body>
    </html>
  )
}

