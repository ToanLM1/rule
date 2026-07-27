import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/**
 * Live audit against the running cloud-local stack (API 8100 + UI 5173, no mocks).
 *
 * Opt-in only: it is skipped unless BRP_LIVE_AUDIT=1, so the default suite stays
 * deterministic and offline. It performs no writes — it selects, reads and screenshots.
 */
const LIVE = process.env.BRP_LIVE_AUDIT === '1'
const UI = process.env.BRP_LIVE_UI ?? 'http://127.0.0.1:5173'
const API = process.env.BRP_LIVE_API ?? 'http://127.0.0.1:8100'
const SHOTS = '../output/product-audit-2026-07-26-live-b008'

test.skip(!LIVE, 'Set BRP_LIVE_AUDIT=1 with the cloud-local stack running.')
test.use({ baseURL: UI })

async function siteId(page: Page) {
  const context = await page.request.get(`${API}/api/v1/context`)
  return (await context.json()).sites[0].id as string
}

async function decisionAt(page: Page, offset: number, status?: string) {
  const site = await siteId(page)
  const query = new URLSearchParams({ site_id: site, page: String(offset), page_size: '1' })
  if (status) query.set('status', status)
  const response = await page.request.get(`${API}/api/v1/decisions?${query}`)
  const body = await response.json()
  return { item: body.items[0], total: body.total as number }
}

test('the picker exposes the whole 260-decision corpus with unique identity', async ({ page }) => {
  const { total } = await decisionAt(page, 1)
  expect(total).toBeGreaterThan(100)

  await page.goto('/test-suites')
  // The page auto-selects a governed change and rewrites the URL; wait for that to
  // settle so the picker interaction is not racing a router replace.
  await expect(page).toHaveURL(/decision=/)
  await page.getByRole('combobox', { name: 'Governed decision' }).click()
  await expect(page.getByText(new RegExp(`of ${total} decisions in this site`))).toBeVisible()

  // Scope to the picker's listbox: the topbar's native selects also expose options.
  const listbox = page.getByRole('listbox')
  const options = listbox.getByRole('option')

  // Every visible option is uniquely identified by its stable key even though the
  // live corpus repeats the same Korean display name across records.
  const keys = await options.evaluateAll((nodes) =>
    nodes.map((node) => node.querySelector('code')?.textContent ?? ''),
  )
  expect(keys.length).toBeGreaterThan(0)
  expect(new Set(keys).size).toBe(keys.length)
  const names = await options.evaluateAll((nodes) =>
    nodes.map((node) => node.querySelector('strong')?.textContent ?? ''),
  )
  expect(new Set(names).size).toBeLessThan(names.length) // duplicates really exist
  await page.screenshot({ path: `${SHOTS}/01-picker-260-unique-keys.png`, fullPage: false })

  // A decision past the old 100-item ceiling is reachable by search.
  const deep = await decisionAt(page, 201)
  await page.getByLabel('Search decisions by name or key').fill(deep.item.decisionKey)
  const option = options.filter({ hasText: deep.item.decisionKey })
  await expect(option).toHaveCount(1)
  await page.screenshot({ path: `${SHOTS}/02-picker-reaches-decision-201.png` })
  await option.click()
  await expect(page).toHaveURL(new RegExp(`decision=${deep.item.decisionKey}`))

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

test('the governed change survives the Next action into Releases', async ({ page }) => {
  const deep = await decisionAt(page, 201)
  await page.goto(`/test-suites?decision=${deep.item.decisionKey}`)
  await expect(page.getByRole('combobox', { name: 'Governed decision' })).toContainText(deep.item.decisionKey)
  await page.getByRole('link', { name: /Next: Releases/ }).click()
  await expect(page).toHaveURL(new RegExp(`/releases\\?decision=${deep.item.decisionKey}`))
  await expect(page.getByRole('combobox', { name: 'Governed change' })).toContainText(deep.item.decisionKey)
})

test('release actions fail closed on a real DRAFT decision', async ({ page }) => {
  const draft = await decisionAt(page, 1, 'DRAFT')
  test.skip(!draft.item, 'No DRAFT decision in the live corpus.')
  await page.goto(`/releases?decision=${draft.item.decisionKey}`)
  await expect(page.getByRole('heading', { name: 'Releases' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create publication' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Start delivery' })).toBeDisabled()
  await expect(page.getByText(/Blocked:/).first()).toBeVisible()
  // Accepted scope stays present.
  await expect(page.getByText('GitHub', { exact: true })).toBeVisible()
  await expect(page.getByText('GitLab', { exact: true })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/03-releases-fail-closed-draft.png`, fullPage: true })

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

test('failed jobs expose a diagnostic record', async ({ page }) => {
  await page.goto('/operations?status=FAILED')
  await expect(page.getByRole('heading', { name: 'Operations' })).toBeVisible()
  // Wait for the jobs request to resolve; counting immediately races the skeleton.
  await expect(page.locator('.skeleton-list')).toHaveCount(0)
  const detailButtons = page.getByRole('button', { name: /Open job detail/ })
  test.skip((await detailButtons.count()) === 0, 'No failed jobs in the live corpus.')
  await detailButtons.first().click()
  const detail = page.getByRole('dialog', { name: 'Job detail' })
  await expect(detail).toBeVisible()
  await expect(detail.getByText('Job ID')).toBeVisible()
  await expect(detail.getByText('Correlation ID')).toBeVisible()
  await expect(detail.getByText('Failure class')).toBeVisible()
  await expect(detail.getByText('Stage timeline')).toBeVisible()
  await expect(detail.getByText('Retry classification')).toBeVisible()
  // The real corpus fails on candidate compilation and provider exhaustion, so the
  // record must name one of those rather than a generic "attempts used up".
  await expect(detail.getByText(/UNSUPPORTED_SEMANTICS|INVALID_INPUT|PROVIDER_UNAVAILABLE|PROVIDER_QUOTA/)).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/04-operations-job-detail.png`, fullPage: true })

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

test('overview reports live counts without false zeros', async ({ page }) => {
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.getByText('Unavailable')).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/05-overview-live.png`, fullPage: true })
})

for (const width of [390, 768, 1024, 1280, 1440]) {
  test(`live releases layout is contained at ${width}px`, async ({ page }) => {
    const draft = await decisionAt(page, 1, 'DRAFT')
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`/releases?decision=${draft.item?.decisionKey ?? ''}`)
    await expect(page.getByRole('heading', { name: 'Releases' })).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
    if (width === 390) await page.screenshot({ path: `${SHOTS}/06-releases-mobile-390.png`, fullPage: true })
  })
}
