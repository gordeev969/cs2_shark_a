import { defineConfig, devices } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const dataDir = mkdtempSync(join(tmpdir(), 'cs2-e2e-'))

export default defineConfig({
  testDir: './e2e',
  timeout: 90000,
  expect: { timeout: 20000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    timezoneId: 'Europe/Moscow',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command:
        '../.venv/bin/uvicorn backend.app.main:app --app-dir .. --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      env: {
        CS2_DATA_DIR: dataDir,
        CS2_REQUIRE_STEAM_LOGIN: 'false',
        STEAM_PUBLIC_URL: 'http://127.0.0.1:5173',
      },
    },
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: true },
  ],
})
