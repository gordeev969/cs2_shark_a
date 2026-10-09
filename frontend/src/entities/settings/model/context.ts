import { createContext, useContext } from 'react'
import type { Settings } from '@/shared/api/contracts'
export const SettingsContext = createContext<{ settings?: Settings; refresh: () => void }>({
  refresh: () => {},
})
export const useSettings = () => useContext(SettingsContext)
