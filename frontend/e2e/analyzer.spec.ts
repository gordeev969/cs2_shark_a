import { expect, test } from '@playwright/test'

test('queued import shows its position and allows the next upload', async ({ page }) => {
  let uploads = 0
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('**/api/matches/import', async (route) => {
    uploads++
    await route.fulfill({
      status: 202,
      json: { id: 990 + uploads, status: 'queued', queue_position: uploads + 1, duplicate: false },
    })
  })
  await page.route(/\/api\/matches\/99[12]$/, async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').at(-1))
    await route.fulfill({
      json: {
        id,
        status: 'queued',
        queue_position: id - 989,
        error: null,
        imported_at: '2026-01-01T00:00:00Z',
        played_at: null,
        map_name: null,
        players: [],
        rounds: [],
        diagnostics: [],
        team_scores: null,
      },
    })
  })
  await page.goto('/import')
  const input = page.getByLabel('Выбрать демку')
  const button = page.getByRole('button', { name: 'Загрузить и разобрать' })
  for (const number of [1, 2]) {
    await input.setInputFiles({
      name: `queued-${number}.dem`,
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('Browser-only mocked upload'),
    })
    await expect(button).toBeEnabled()
    await button.click()
    await expect(page.getByText(`В очереди · №${number + 1}`, { exact: true })).toBeVisible()
    await expect(input).toBeEnabled()
    await expect(button).toBeDisabled()
    await expect(page.getByText(/Можно загрузить следующую демку/)).toBeVisible()
  }
  expect(uploads).toBe(2)
  await page.goto('/matches/992')
  await expect(page.getByText('В очереди · №3', { exact: true })).toBeVisible()
  await expect(page.getByText(/Записи всех пользователей разбираются по одной/)).toBeVisible()
  expect(errors).toEqual([])
})

test('dashboard loading, failure and retry remain accessible on mobile', async ({ page }) => {
  let fail = true
  let release!: () => void
  const pending = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/dashboard?**', async (route) => {
    await pending
    if (fail) await route.fulfill({ status: 503, json: { detail: 'Данные временно недоступны' } })
    else await route.continue()
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  try {
    await expect(page.getByRole('status', { name: 'Загружаем локальные данные' })).toBeVisible()
    await expect(page.locator('.stat-card')).toHaveCount(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
  } finally {
    release()
  }
  await expect(page.getByRole('alert')).toContainText('Данные временно недоступны')
  await expect(page.getByRole('status', { name: 'Загружаем локальные данные' })).toHaveCount(0)
  fail = false
  await page.getByRole('button', { name: 'Повторить', exact: true }).click()
  await expect(page.locator('.profile-overview')).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('Russian dashboard, empty state and mobile navigation', async ({ page, request }) => {
  const d = await (await request.get('/api/dashboard')).json()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Обзор игры' })).toBeVisible()
  if (!d.match_count)
    await expect(page.getByRole('heading', { name: 'Здесь будут ваши матчи' })).toBeVisible()
  await expect(page.getByText('API подключён', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Открыть меню' }).click()
  await page.getByRole('navigation').getByRole('link', { name: 'Настройки' }).click()
  await expect(page.getByRole('heading', { name: 'Под вашу игру' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Открыть меню' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})

test('real demo upload, all participants, own profile, deduplication and local-only requests', async ({
  page,
  request,
}) => {
  test.skip(!process.env.CS2_TEST_DEMO, 'Set CS2_TEST_DEMO to a legally obtained CS2 replay')
  const external: string[] = []
  page.on('request', (r) => {
    if (!['127.0.0.1', 'localhost'].includes(new URL(r.url()).hostname)) external.push(r.url())
  })
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const prior = await (await request.get('/api/matches')).json()
  await page.goto('/import')
  await page.getByLabel('Выбрать демку').setInputFiles(process.env.CS2_TEST_DEMO!)
  await page.getByRole('button', { name: 'Загрузить и разобрать' }).click()
  await expect(page.getByRole('link', { name: 'Открыть отчёт' })).toBeVisible({ timeout: 60000 })
  await page.getByRole('link', { name: 'Открыть отчёт' }).click()
  const matchId = page.url().split('/').at(-1)
  const match = await (await request.get(`/api/matches/${matchId}`)).json()
  await expect(page.locator('.scoreboard tbody tr')).toHaveCount(match.players.length)
  if (process.env.CS2_UPSTREAM_FIXTURE === '1') {
    expect(match.players.length).toBe(10)
    expect(match.team_scores).toEqual({ A: 8, B: 2 })
    expect(match.rounds.length).toBe(9)
    expect(match.players.reduce((sum: number, p: { kills: number }) => sum + p.kills, 0)).toBe(64)
    expect(match.players.reduce((sum: number, p: { deaths: number }) => sum + p.deaths, 0)).toBe(64)
    expect(match.players.every((p: { adr: number | null }) => p.adr !== null)).toBe(true)
  }
  const own = match.players[0]
  await page.locator('.scoreboard tbody tr').first().getByRole('link').click()
  await expect(page.getByRole('heading', { name: own.nickname, exact: true })).toBeVisible()
  const select = page.getByRole('button', { name: 'Это я', exact: true })
  if (await select.count()) await select.click()
  await expect(page.getByRole('button', { name: 'Ваш профиль', exact: true })).toBeDisabled()
  await expect(page.getByText(/Недостаточно данных для оценки аномальности/)).toBeVisible()
  await page.goto('/players')
  await page.getByRole('textbox', { name: 'Никнейм или SteamID64' }).fill(own.steam_id64)
  await expect(page.locator('.player-card')).toHaveCount(1)
  await page.goto('/settings')
  await page.getByRole('checkbox', { name: /Компактные таблицы/ }).check()
  await page.getByRole('button', { name: 'Сохранить настройки' }).click()
  await expect(page.getByText('Настройки сохранены локально')).toBeVisible()
  await page.goto(`/matches/${matchId}`)
  await expect(page.locator('tr.own-player')).toHaveCount(1)
  await page.getByTitle(/Раунд 2, победа/).click()
  await expect(page.locator('.round-players')).toBeVisible()
  await page.goto('/import')
  await page.getByLabel('Выбрать демку').setInputFiles(process.env.CS2_TEST_DEMO!)
  await page.getByRole('button', { name: 'Загрузить и разобрать' }).click()
  await expect(
    page.getByText('Эта демка уже есть в базе. Повторная статистика не создана.'),
  ).toBeVisible()
  const after = await (await request.get('/api/matches')).json()
  expect(after.length).toBe(
    prior.some((m: { id: number }) => m.id === Number(matchId)) ? prior.length : prior.length + 1,
  )
  expect(external).toEqual([])
  expect(errors).toEqual([])
  await page.goto(`/matches/${matchId}`)
  await expect(page.locator('.scoreboard')).toBeVisible()
  await page.screenshot({ path: '/tmp/cs2-match-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '')
  await expect(page.getByRole('button', { name: 'Открыть меню' })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  await page.screenshot({ path: '/tmp/cs2-match-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})

test('invalid file is explained without fake statistics', async ({ page }) => {
  await page.goto('/import')
  await page.getByLabel('Выбрать демку').setInputFiles({
    name: 'bad.dem',
    mimeType: 'application/octet-stream',
    buffer: Buffer.from('invalid cs2 data'),
  })
  await page.getByRole('button', { name: 'Загрузить и разобрать' }).click()
  await expect(page.getByRole('alert')).toContainText('не является бинарной CS2-демкой')
  await expect(page.locator('.scoreboard')).toHaveCount(0)
})
