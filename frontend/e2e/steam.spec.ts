import { test, expect } from '@playwright/test'

const steam = '76561198000000001'
const user = {
  steam_id64: steam,
  display_name: 'Тестовый аккаунт',
  avatar_url: null,
  profile_url: `https://steamcommunity.com/profiles/${steam}`,
}
const connection = {
  connected: false,
  status: 'disconnected',
  error: null,
  last_sync: null,
  initial_sharecode: null,
  latest_sharecode: null,
  discovered_count: 0,
  imported_count: 0,
  pending_count: 0,
  failed_count: 0,
  gc_configured: false,
  steam_api_configured: false,
}

test('protected routes show real Steam sign-in link before any private data', async ({ page }) => {
  await page.route('**/api/auth/session', (route) =>
    route.fulfill({ json: { authenticated: false, required: true, user: null, csrf_token: null } }),
  )
  await page.goto('/matches')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: /Ваш профиль/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Войти через Steam/ })).toHaveAttribute(
    'href',
    '/api/auth/steam/login',
  )
  await expect(page.getByText('Пароль вводится только на сайте Steam.')).toBeVisible()
})

test('CS2 connection, sync, immutable identity and logout send session CSRF', async ({ page }) => {
  let authenticated = true
  let connected = false
  let syncs = 0
  const mutations: string[] = []
  await page.route('**/api/auth/session', (route) =>
    route.fulfill({
      json: {
        authenticated,
        required: true,
        user: authenticated ? user : null,
        csrf_token: authenticated ? 'test-csrf' : null,
      },
    }),
  )
  await page.route('**/api/settings', (route) =>
    route.fulfill({ json: { steam_id64: steam, compact: false, ai_enabled: false } }),
  )
  await page.route('**/api/cs2/connection', async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') {
      expect(request.headers()['x-csrf-token']).toBe('test-csrf')
      mutations.push(request.method())
      if (request.method() === 'POST') {
        expect(request.postDataJSON()).toEqual({
          auth_code: 'ABCD-EFGHJ-KLMN',
          sharing_code: 'CSGO-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA',
        })
        connected = true
      }
      if (request.method() === 'DELETE') connected = false
    }
    await route.fulfill({
      json: { ...connection, connected, status: connected ? 'idle' : 'disconnected' },
    })
  })
  await page.route('**/api/cs2/sync', async (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('test-csrf')
    expect(route.request().method()).toBe('POST')
    syncs++
    await route.fulfill({ status: 202, json: { ...connection, connected: true, status: 'queued' } })
  })
  await page.route('**/api/auth/logout', async (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('test-csrf')
    authenticated = false
    await route.fulfill({ json: { authenticated: false } })
  })
  await page.goto('/connect')
  await page.getByLabel('Game Authentication Code').fill('ABCD-EFGHJ-KLMN')
  await page.getByLabel('Код недавнего матча').fill('CSGO-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA')
  await page.getByRole('button', { name: 'Подключить CS2' }).click()
  await expect(page.getByText('Код доступа сохранён')).toBeVisible()
  await expect(page.getByLabel('Game Authentication Code')).toHaveValue('')
  await expect(page.getByText('Автозагрузка пока не настроена')).toBeVisible()
  await page.getByRole('button', { name: 'Загрузить матчи' }).click()
  await expect.poll(() => syncs).toBe(1)
  await page.getByRole('button', { name: 'Отключить', exact: true }).click()
  await expect(page.getByText('Код доступа сохранён')).not.toBeVisible()
  expect(mutations).toEqual(['POST', 'DELETE'])
  await page.goto('/settings')
  await expect(page.getByLabel('Ваш SteamID64')).toHaveAttribute('readonly', '')
  await page.getByRole('button', { name: 'Выйти', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
})
