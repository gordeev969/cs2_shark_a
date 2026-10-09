import { expect, test } from '@playwright/test'

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
