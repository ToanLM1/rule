import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('functional overview, theme and command navigation work together', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await page.addInitScript(() => localStorage.setItem('brp.theme', 'light'))
  await mockApi(page)
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.locator('.metric-grid .metric-card')).toHaveCount(4)
  await expect(page.locator('.workflow-stages > a')).toHaveCount(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)

  await page.getByRole('button', { name: 'Theme: light' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.keyboard.press('Control+K')
  const palette = page.getByRole('dialog', { name: 'Go anywhere' })
  await expect(palette).toBeVisible()
  await palette.getByPlaceholder('Search decisions, jobs and workspaces').fill('eligibility')
  await palette.getByPlaceholder('Search decisions, jobs and workspaces').press('Enter')
  await expect(page).toHaveURL(/\/decisions\?q=eligibility$/)

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('reduced motion keeps overview content fully visible', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApi(page)
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.locator('.workflow-stages > a')).toHaveCount(4)
})

test('all eight workflow routes render their primary screen', async ({ page }) => {
  await mockApi(page)
  const routes = [
    ['/overview', 'Overview'],
    ['/decisions', 'Decisions'],
    ['/imports', 'Imports'],
    ['/reviews', 'Review queue'],
    ['/test-suites', 'Test suites'],
    ['/releases', 'Releases'],
    ['/sites', 'Sites'],
    ['/operations', 'Operations'],
  ] as const
  for (const [path, heading] of routes) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
  }
})
