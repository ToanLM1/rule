import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('enterprise decision portfolio and editor have no critical accessibility violations', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await mockApi(page)
  await page.goto('/decisions')
  await expect(page.getByRole('heading', { name: 'Decisions' })).toBeVisible()
  await expect(page.getByText('가입 자격 판정')).toBeVisible()
  await page.getByRole('button', { name: 'Open decision' }).click()
  await expect(page.getByRole('dialog', { name: 'Decision editor' })).toBeVisible()
  await expect(page.getByText('Optimistic concurrency: base r2')).toBeVisible()
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
  expect(consoleErrors).toEqual([])
})
