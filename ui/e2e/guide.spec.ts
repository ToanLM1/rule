import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test('business guide delivers editorial story, handbook and simulator', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await mockApi(page)
  await page.goto('/guide')

  const hero = page.locator('.guide-hero h1')
  await expect(hero).toBeVisible()
  const heroImage = page.locator('.guide-hero-art img')
  await expect(heroImage).toBeVisible()
  expect(await heroImage.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)

  const video = page.locator('.guide-video-frame video')
  await expect(video).toHaveAttribute('preload', 'metadata')
  await expect(video).not.toHaveAttribute('autoplay', '')
  await expect(video.locator('track')).toHaveCount(2)
  await video.evaluate(async (element: HTMLVideoElement) => {
    if (element.readyState >= 1) return
    await new Promise<void>((resolve, reject) => {
      element.addEventListener('loadedmetadata', () => resolve(), { once: true })
      element.addEventListener('error', () => reject(new Error('Guide video metadata failed to load')), { once: true })
    })
  })
  expect(await video.evaluate((element: HTMLVideoElement) => element.duration)).toBeGreaterThan(45)
  expect(await video.evaluate((element: HTMLVideoElement) => element.paused)).toBe(true)
  const heroLines = await hero.evaluate((element) => {
    const lineHeight = Number.parseFloat(getComputedStyle(element).lineHeight)
    return Math.round(element.getBoundingClientRect().height / lineHeight)
  })
  expect(heroLines).toBeLessThanOrEqual(3)
  await expect(page.locator('.guide-bento-card')).toHaveCount(5)
  expect(await page.locator('.guide-bento').evaluate((element) => getComputedStyle(element).gridAutoFlow)).toBe('dense')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)

  const riskGroup = page.getByRole('group', { name: 'Risk flag present' })
  await riskGroup.getByRole('button', { name: 'Yes', exact: true }).click()
  await expect(page.getByText('Manual review', { exact: true })).toBeVisible()
  await expect(page.getByText('ELG-RISK-03', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Next role' }).click()
  await expect(page.getByText('Checker', { exact: true })).toBeVisible()
  await expect(page.locator('.guide-role-portraits button')).toHaveCount(4)
  await expect(page.locator('.guide-role-visual img')).toHaveAttribute('src', '/guide/role-checker.webp')
  await page.getByLabel('Language').selectOption('ko')
  await expect(page.getByText('후보 규칙은 운영 로직이 아닙니다.', { exact: true })).toBeVisible()
  await expect(video).toHaveAttribute('aria-label', 'Rule Platform 소개 영상')
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => Array.from(element.textTracks).map((track) => `${track.language}:${track.mode}`).join(','))).toContain('ko:showing')

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('guide remains readable without the platform API', async ({ page }) => {
  await page.route('http://localhost:8100/**', (route) => route.abort())
  await page.goto('/guide')
  await expect(page.locator('.guide-hero h1')).toBeVisible()
  await expect(page.getByText('Connection problem')).toHaveCount(0)
  await expect(page.getByText('Illustrative sample — not production data')).toBeVisible()
})

test('guide is static and overflow-free on mobile reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApi(page)
  await page.goto('/guide')
  await expect(page.locator('.guide-hero h1')).toBeVisible()
  await expect(page.locator('.guide-trust-word').first()).toHaveCSS('opacity', '1')
  await expect(page.locator('.guide-video-frame video')).toBeVisible()
  expect(await page.locator('.guide-video-frame video').evaluate((element: HTMLVideoElement) => element.paused)).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByRole('link', { name: 'Guide', exact: true })).toBeVisible()
})
