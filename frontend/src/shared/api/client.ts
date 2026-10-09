import { useEffect, useState } from 'react'
import { isSnapshotMode } from '@/shared/config'
import { snapshotRequest } from './snapshot'

let currentCSRFToken: string | null = null
export function setCSRFToken(token: string | null) {
  currentCSRFToken = token
}
export function getCSRFToken() {
  return currentCSRFToken
}
export async function api<T>(url: string, options?: RequestInit): Promise<T> {
  if (isSnapshotMode) return snapshotRequest<T>(url, options)
  const headers = new Headers(options?.headers)
  if (currentCSRFToken && !['GET', 'HEAD'].includes(options?.method?.toUpperCase() ?? 'GET'))
    headers.set('X-CSRF-Token', currentCSRFToken)
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' })
  if (response.status === 401 && url !== '/api/auth/session')
    window.dispatchEvent(new Event('cs2-session-expired'))
  const body = await response.json().catch(() => null)
  if (!response.ok)
    throw new Error(
      typeof body?.detail === 'string'
        ? body.detail
        : `Ошибка запроса (${response.status}). Проверьте данные и подключение к локальному API.`,
    )
  return body as T
}

export function useData<T>(url: string | null, shouldPoll?: (data: T) => boolean) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({
    loading: true,
  })
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    setState((previous) => ({ data: url ? previous.data : undefined, loading: !!url }))
    async function load() {
      if (!url) return
      try {
        const data = await api<T>(url, { signal: controller.signal })
        if (!controller.signal.aborted) {
          setState({ data, loading: false })
          if (shouldPoll?.(data)) timer = setTimeout(load, 1500)
        }
      } catch (error) {
        if (!controller.signal.aborted)
          setState({
            error: error instanceof Error ? error.message : 'Ошибка подключения',
            loading: false,
          })
      }
    }
    void load()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [url, shouldPoll, revision])
  return { ...state, retry: () => setRevision((r) => r + 1) }
}
