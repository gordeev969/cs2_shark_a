/* global process, URL, document, innerWidth, console */
import { chromium, expect } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
const base = process.env.CS2_PAGES_URL
if (!base) throw new Error('Set CS2_PAGES_URL to the root of a built snapshot site.')
const snapshot = JSON.parse(
  readFileSync(new URL('../public/snapshot.json', import.meta.url), 'utf8'),
)
const match = Object.values(snapshot.matches)[0]
const artifacts = process.env.CS2_SCREENSHOTS_DIR ?? 'test-results/pages'
mkdirSync(artifacts, { recursive: true })
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  const errors = []
  const apiCalls = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiCalls.push(request.url())
  })
  async function checkOverflow() {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  async function navigate(path) {
    await page.goto(`${base}#${path}`)
  }
  for (const width of [320, 360, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 })
    await navigate('/')
    await expect(page.getByRole('heading', { name: 'Обзор игры', exact: true })).toBeVisible()
    await expect(page.locator('.stat-card')).toHaveCount(4)
    await checkOverflow()
    if (width === 1440 || width === 390)
      await page.screenshot({ path: `${artifacts}/dashboard-${width}.png`, fullPage: true })
    await page.getByRole('link', { name: 'Открыть отчёт матча', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Таблица участников/ })).toBeVisible()
    await expect(page.locator('.scoreboard tbody tr')).toHaveCount(match.players.length)
    await checkOverflow()
    if (width === 1440 || width === 390)
      await page.screenshot({ path: `${artifacts}/match-${width}.png`, fullPage: true })
    await page.reload()
    await expect(page.locator('.scoreboard tbody tr')).toHaveCount(match.players.length)
    await page.locator('.player-cell').first().click()
    await expect(page.getByRole('heading', { name: 'История игрока' })).toBeVisible()
    await checkOverflow()
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await navigate('/')
  const menu = page.getByRole('button', { name: 'Открыть меню', exact: true })
  await expect(page.locator('#main-sidebar')).toHaveAttribute('inert', '')
  await menu.click()
  await expect(page.locator('#main-sidebar')).not.toHaveAttribute('inert')
  await expect(page.getByRole('link', { name: 'Обзор', exact: true })).toBeVisible()
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
  await page.keyboard.press('Escape')
  await expect(menu).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('#main-sidebar')).toHaveAttribute('inert', '')
  await menu.click()
  await page.getByRole('link', { name: 'Игроки', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Знакомые по серверу' })).toBeVisible()
  await expect(menu).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden')
  await page.locator('.player-card').last().click()
  await expect(
    page.getByRole('heading', { name: snapshot.players.at(-1).latest_nickname, exact: true }),
  ).toBeVisible()
  const select = page.getByRole('button', { name: 'Выбрать игрока', exact: true })
  if (await select.count()) await select.click()
  await expect(page.getByRole('button', { name: 'Выбранный игрок', exact: true })).toBeDisabled()
  await navigate('/')
  await expect(page.locator('.profile-overview h2')).toHaveText(
    snapshot.players.at(-1).latest_nickname,
  )
  await navigate('/import')
  await expect(
    page.getByRole('heading', { name: 'Для своих матчей нужна полная версия' }),
  ).toBeVisible()
  await expect(page.locator('input[type=file]')).toHaveCount(0)
  await navigate('/connect')
  await expect(page.locator('input')).toHaveCount(0)
  expect(errors).toEqual([])
  expect(apiCalls).toEqual([])
  console.log(
    'Pages smoke passed: 7 widths, match/profile routes, reload, player selection, accessible menu and readonly actions. No API requests or JS errors.',
  )
} finally {
  await browser.close()
}
