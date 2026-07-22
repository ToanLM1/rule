import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('decision studio preserves governance controls in dark mode', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await page.addInitScript(() => localStorage.setItem('brp.theme', 'dark'))
  await mockApi(page)
  await page.goto('/decisions?q=eligibility')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('heading', { name: 'Decisions' })).toBeVisible()
  await expect(page.getByLabel('Search decisions')).toHaveValue('eligibility')
  await expect(page.getByText('가입 자격 판정')).toBeVisible()
  await page.getByRole('button', { name: 'Open decision' }).click()
  await expect(page.getByRole('dialog', { name: 'Decision editor' })).toBeVisible()
  await expect(page.getByText('Optimistic concurrency: base r2')).toBeVisible()
  await expect(page.locator('.ag-root')).toBeVisible()
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
  expect(consoleErrors).toEqual([])
})
