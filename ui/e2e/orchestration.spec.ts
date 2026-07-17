import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('responsive shell exposes complete workflow and Korean locale', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
  await page.getByLabel('Language').selectOption('ko')
  await expect(page.getByRole('link', { name: /결정/ })).toBeVisible()
  await page.getByRole('link', { name: /가져오기/ }).click()
  await expect(page).toHaveURL(/\/imports$/)
  await expect(page.getByRole('heading', { name: 'Imports' })).toBeVisible()
})
