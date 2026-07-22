import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('responsive shell exposes the full workflow in Korean without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
  await page.getByLabel('Language').selectOption('ko')
  await expect(page.getByRole('link', { name: '결정' })).toBeVisible()
  await page.getByRole('link', { name: '가져오기', exact: true }).click()
  await expect(page).toHaveURL(/\/imports$/)
  await expect(page.getByRole('heading', { name: 'Imports' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
