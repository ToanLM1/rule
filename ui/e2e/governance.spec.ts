import { expect, test } from '@playwright/test'

const revision = {
  envelope: {
    decisionKey: 'enrollment_eligibility', revision: 2, lifecycleStatus: 'SUBMITTED',
    contentHash: '9f75f8e59bf2a7e6d4e1c9a401bc2b7c3d91cc87de23724d1b1fe0d08111a320',
    effectiveFrom: '2026-08-01T00:00:00Z', effectiveTo: null,
    createdBy: 'maker-a', submittedBy: 'maker-a', approvedBy: null,
  },
  content: {
    decisionName: '가입 자격 판정',
    rules: [
      { ruleId: 'R001', when: { all: [{ left: { kind: 'INPUT', name: 'age' }, operator: 'LT', right: { kind: 'LITERAL', value: 19 } }] }, then: [{ output: 'eligible', value: false }, { output: 'reasonCode', value: 'UNDER_AGE' }], confidence: .95 },
      { ruleId: 'R002', when: { all: [{ left: { kind: 'INPUT', name: 'age' }, operator: 'GT', right: { kind: 'LITERAL', value: 65 } }] }, then: [{ output: 'eligible', value: false }, { output: 'reasonCode', value: 'OVER_AGE_LIMIT' }], confidence: .93 },
      { ruleId: 'R003', when: { all: [{ left: { kind: 'LOOKUP_FIELD', lookup: 'regionEligibility' }, operator: 'NE', right: { kind: 'LITERAL', value: true } }] }, then: [{ output: 'eligible', value: false }, { output: 'reasonCode', value: 'REGION_NOT_COVERED' }], confidence: .86 },
    ],
  },
}

test('list, detail, and advisory preview render without console errors', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await page.route('http://localhost:8100/**', async (route) => {
    const url = route.request().url()
    let json: unknown = revision
    if (url.endsWith('/decisions')) json = [{ decisionKey: 'enrollment_eligibility', name: '가입 자격 판정', latestRevision: 2, latestStatus: 'SUBMITTED' }, { decisionKey: 'premium_adjustments', name: '보험료 할증', latestRevision: 1, latestStatus: 'APPROVED' }]
    else if (url.endsWith('/audit')) json = [{ id: 1, actor: 'maker-a', action: 'CREATE_REVISION', fromStatus: 'DRAFT', toStatus: 'DRAFT', at: '2026-08-01T00:00:00Z' }, { id: 2, actor: 'maker-a', action: 'SUBMIT', fromStatus: 'DRAFT', toStatus: 'SUBMITTED', at: '2026-08-02T00:00:00Z' }]
    else if (url.includes('/golden-suites/')) json = [{ revision: 1, status: 'APPROVED', contentHash: '81f0a314a61a39f4' }]
    else if (url.includes('/preview/')) json = { executor: 'ZEN', authority: 'ADVISORY', result: { eligible: false, reasonCode: 'UNDER_AGE' } }
    await route.fulfill({ json })
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: '가입 자격 판정' })).toBeVisible()
  await page.screenshot({ path: '../output/playwright/decision-list.png', fullPage: true })
  await expect(page.getByText('Revision 2')).toBeVisible()
  await page.screenshot({ path: '../output/playwright/decision-detail.png', fullPage: true })
  await page.getByRole('button', { name: 'preview' }).click()
  await page.getByRole('button', { name: 'Run Zen preview' }).click()
  await expect(page.getByTestId('preview-result')).toContainText('UNDER_AGE')
  await expect(page.getByTestId('preview-result')).toContainText('ADVISORY')
  await page.screenshot({ path: '../output/playwright/decision-preview.png', fullPage: true })
  expect(consoleErrors).toEqual([])
})
