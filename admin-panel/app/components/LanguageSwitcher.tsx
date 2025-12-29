'use client'

import { useI18n } from '../lib/i18n/context'

export default function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()

  return (
    <div className="relative">
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as 'ru' | 'en')}
        className="px-3 py-2 border border-fb-gray-dark rounded-lg text-sm font-medium text-fb-text bg-white hover:bg-fb-gray-dark transition-colors focus:outline-none focus:ring-2 focus:ring-fb-blue cursor-pointer"
      >
        <option value="ru">🇷🇺 Русский</option>
        <option value="en">🇬🇧 English</option>
      </select>
    </div>
  )
}

