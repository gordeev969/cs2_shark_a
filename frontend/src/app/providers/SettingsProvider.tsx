import type { ReactNode } from 'react'
import { SettingsContext } from '@/entities/settings'
import { useData } from '@/shared/api'
import type { Settings } from '@/shared/api/contracts'
import { Gate } from '@/shared/ui'

export function SettingsProvider({ children }: { children: ReactNode }) {
  const result = useData<Settings>('/api/settings')
  return (
    <SettingsContext.Provider value={{ settings: result.data, refresh: result.retry }}>
      <Gate loading={result.loading && !result.data} error={result.error} retry={result.retry}>
        {children}
      </Gate>
    </SettingsContext.Provider>
  )
}
