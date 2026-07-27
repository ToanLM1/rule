import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

import { failedJob, fixtures, importRun, mockApi } from './mockApi'

function picker(page: Page, name: string) {
  return page.getByRole('combobox', { name })
}

test('the decision picker uniquely identifies same-named decisions and reaches the whole corpus', async ({ page }) => {
  await mockApi(page)
  await page.goto('/test-suites')
  await expect(page.getByRole('heading', { name: 'Test suites' })).toBeVisible()

  await picker(page, 'Governed decision').click()
  const options = page.getByRole('option')

  // Both same-named decisions are present and distinguishable by their stable key.
  await expect(options.filter({ has: page.getByText('enrollment_eligibility', { exact: true }) })).toHaveCount(1)
  await expect(options.filter({ has: page.getByText('enrollment_eligibility_kb', { exact: true }) })).toHaveCount(1)
  await expect(page.getByText(/Showing 1–10 of 24 decisions/)).toBeVisible()

  // The corpus beyond the first page is reachable.
  await page.getByRole('button', { name: /Next/ }).click()
  await expect(page.getByText(/Page 2 of 3/)).toBeVisible()

  // Server-side search, not a filter over one loaded page.
  await page.getByLabel('Search decisions by name or key').fill('renewal_rule_021')
  const match = options.filter({ has: page.getByText('renewal_rule_021', { exact: true }) })
  await expect(match).toHaveCount(1)
  await match.click()
  await expect(page).toHaveURL(/decision=renewal_rule_021/)

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

test('the governed change survives a deep link and the Next action', async ({ page }) => {
  await mockApi(page, { goldenSuites: [fixtures.approvedSuite], profiles: [fixtures.modeBProfile] })
  await page.goto('/test-suites?decision=enrollment_eligibility_kb')
  await expect(picker(page, 'Governed decision')).toContainText('enrollment_eligibility_kb')
  await page.getByRole('link', { name: /Next: Releases/ }).click()
  await expect(page).toHaveURL(/\/releases\?decision=enrollment_eligibility_kb/)
  await expect(picker(page, 'Governed change')).toContainText('enrollment_eligibility_kb')
})

test('release actions fail closed for a DRAFT decision and explain the missing gate', async ({ page }) => {
  await mockApi(page, { profiles: [fixtures.modeBProfile] })
  await page.goto('/releases?decision=enrollment_eligibility_kb')
  await expect(page.getByRole('heading', { name: 'Releases' })).toBeVisible()

  await expect(page.getByRole('button', { name: 'Create publication' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Start delivery' })).toBeDisabled()

  const modeA = page.getByRole('list', { name: 'Mode-A release readiness' })
  await expect(modeA.getByText('No golden suite revision has been captured for this decision.')).toBeVisible()
  await expect(modeA.getByText(/Owner: Checker/).first()).toBeVisible()
  await expect(modeA.getByRole('link', { name: 'Open Test suites' })).toBeVisible()

  // Accepted product scope stays visible and is not downgraded.
  await expect(page.getByText('Mode A', { exact: true })).toBeVisible()
  await expect(page.getByText('Mode B', { exact: true })).toBeVisible()
  await expect(page.getByText('GitHub', { exact: true })).toBeVisible()
  await expect(page.getByText('GitLab', { exact: true })).toBeVisible()

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

test('release actions open once every authoritative prerequisite is proven', async ({ page }) => {
  await mockApi(page, { goldenSuites: [fixtures.approvedSuite], profiles: [fixtures.modeBProfile] })
  await page.goto('/releases?decision=enrollment_eligibility')
  await expect(page.getByRole('button', { name: 'Create publication' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Start delivery' })).toBeEnabled()
})

test('a failed overview request never becomes an empty or zero claim', async ({ page }) => {
  await mockApi(page, { fail: ['/api/v1/overview', '/api/v1/jobs', '/api/v1/import-runs'] })
  await page.goto('/overview')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.getByText('Unavailable').first()).toBeVisible()
  await expect(page.getByText('No imports yet')).toHaveCount(0)
  await expect(page.getByText('No job activity')).toHaveCount(0)
  await expect(page.getByText('No failed jobs')).toHaveCount(0)
  await expect(page.getByRole('alert')).toHaveCount(1)
})

test('a failed review-queue request never claims the queue is clear', async ({ page }) => {
  await mockApi(page, { fail: ['/api/v1/review-items'] })
  await page.goto('/reviews')
  await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()
  await expect(page.getByText('Review queue is clear')).toHaveCount(0)
  await expect(page.getByText('the queue is not clear, its state is unknown')).toBeVisible()
})

test('a failed job exposes its stage, redacted reason and next action', async ({ page }) => {
  await mockApi(page, {
    jobs: [failedJob],
    importRuns: [importRun],
    overview: { decisions: 24, openReviews: 2, activeJobs: 0, failedJobs: 1 },
  })
  await page.goto('/operations')
  await expect(page.getByRole('heading', { name: 'Operations' })).toBeVisible()
  await page.getByRole('button', { name: /Open job detail/ }).click()

  const detail = page.getByRole('dialog', { name: 'Job detail' })
  await expect(detail).toBeVisible()
  await expect(detail.getByText(failedJob.id)).toBeVisible()
  await expect(detail.getByText(failedJob.correlationId)).toBeVisible()
  await expect(detail.getByText('PROVIDER_QUOTA')).toBeVisible()
  await expect(detail.getByText(/attempt\(s\) were used/)).toBeVisible()
  await expect(detail.getByText('novoda/dojos')).toBeVisible()
  // The redacted reason must not leak the raw token value.
  await expect(detail.getByText('token=abcdefgh')).toHaveCount(0)

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => item.impact === 'critical')).toEqual([])
})

for (const width of [390, 768, 1024, 1280, 1440]) {
  test(`releases readiness stays inside the viewport at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await mockApi(page, { profiles: [fixtures.modeBProfile] })
    await page.goto('/releases?decision=enrollment_eligibility')
    await expect(page.getByRole('heading', { name: 'Releases' })).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
  })
}
