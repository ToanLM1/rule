import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

async function mockApi(page: Page) {
  const handler = async (route: Parameters<Parameters<Page['route']>[1]>[0]) => {
    const body = route.request().url().endsWith('/api/v1/auth/me')
      ? {
          username: 'maker',
          roles: ['maker'],
          csrfToken: 'guide-playwright-csrf',
        }
      : route.request().url().endsWith('/api/v1/context')
      ? {
          workspaces: [{ id: 'workspace-test', key: 'test', name: 'Test workspace' }],
          sites: [
            {
              id: 'site-test',
              workspaceId: 'workspace-test',
              key: 'test',
              name: 'Test site',
              status: 'ACTIVE',
              defaultLocale: 'en',
              timezone: 'UTC',
            },
          ],
          authentication: 'test',
          productionBlocked: true,
        }
      : []

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  }

  await page.route('http://localhost:8100/**', handler)
  await page.route('http://127.0.0.1:8100/**', handler)
}

test('guide presents explanatory slides, architecture, and working navigation', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await mockApi(page)
  await page.goto('/guide')

  await expect(page.locator('.doc-header h1')).toHaveText('Rule Platform documentation')

  const images = page.locator('.doc-header img, .doc-visual img')
  await expect(images).toHaveCount(4)
  for (let index = 0; index < 4; index += 1) {
    const image = images.nth(index)
    await image.scrollIntoViewIfNeeded()
    await expect.poll(async () => image.evaluate((element) => (element as HTMLImageElement).complete)).toBe(true)
  }

  const visualState = await images.evaluateAll((images) =>
    images.map((image) => {
      const element = image as HTMLImageElement
      return {
        alt: element.alt,
        src: element.getAttribute('src'),
        naturalWidth: element.naturalWidth,
        naturalHeight: element.naturalHeight,
      }
    }),
  )

  expect(visualState).toHaveLength(4)
  for (const visual of visualState) {
    expect(visual.alt.length).toBeGreaterThan(0)
    expect(visual.naturalWidth).toBeGreaterThan(0)
    expect(visual.naturalHeight).toBeGreaterThan(0)
  }
  expect(visualState.map((visual) => visual.src)).toEqual([
    '/guide/slides/governed-decision-hero.webp',
    '/guide/slides/rule-platform-architecture.svg',
    '/guide/slides/maker-checker-review.webp',
    '/guide/slides/golden-test-delivery.webp',
  ])

  await expect(page.locator('.doc-toc a.active')).toHaveCount(1)
  const authorLink = page.locator('.doc-toc a[href="#author"]')
  await authorLink.click()
  await expect(page.locator('#author')).toBeInViewport()

  await expect(page.locator('.doc-links a[href="/studio"]')).toBeVisible()

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(horizontalOverflow).toBeLessThanOrEqual(0)

  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations.filter((violation) => violation.impact === 'critical')).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('an unavailable authentication API fails closed at login', async ({ page }) => {
  await page.route('http://localhost:8100/**', (route) => route.abort())
  await page.route('http://127.0.0.1:8100/**', (route) => route.abort())

  await page.goto('/guide')

  await expect(page).toHaveURL(/\/login\?redirect=\/guide/)
  await expect(page.getByRole('heading', { name: 'Sign in to continue' })).toBeVisible()
})

test('guide localizes visuals and stays contained on mobile with reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApi(page)
  await page.goto('/guide')

  await page.getByRole('combobox', { name: 'Language' }).selectOption('ko')

  await expect(page.locator('.doc-header h1')).toHaveText('Rule Platform 문서')
  await expect(page.locator('.doc-hero-visual img')).toHaveAttribute('alt', /5단계/)
  await expect(page.locator('.doc-hero-visual img')).toBeVisible()

  const heroNaturalWidth = await page.locator('.doc-hero-visual img').evaluate(
    (image) => (image as HTMLImageElement).naturalWidth,
  )
  expect(heroNaturalWidth).toBeGreaterThan(0)

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(horizontalOverflow).toBeLessThanOrEqual(0)
})
