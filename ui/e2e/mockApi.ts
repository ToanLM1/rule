import type { Page } from '@playwright/test'

export const siteId = '00000000-0000-0000-0000-000000000002'

export async function mockApi(page: Page) {
  await page.route('http://localhost:8100/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    let json: unknown = {}
    if (path === '/api/v1/context') json = { workspaces: [{ id: '00000000-0000-0000-0000-000000000001', key: 'rules', name: 'Rules Operations' }], sites: [{ id: siteId, workspaceId: '00000000-0000-0000-0000-000000000001', key: 'seoul', name: 'Seoul Underwriting', status: 'ACTIVE', defaultLocale: 'en', timezone: 'Asia/Seoul' }], authentication: 'DEVELOPMENT_IDENTITY', productionBlocked: true }
    else if (path === '/api/v1/overview') json = { decisions: 1, openReviews: 2, activeJobs: 0, failedJobs: 0 }
    else if (path === '/api/v1/decisions') json = { items: [{ decisionKey: 'enrollment_eligibility', name: '가입 자격 판정', productKey: 'CANCER_BASIC', flowKey: 'ENROLLMENT', latestRevision: 2, latestStatus: 'APPROVED', owner: 'maker-a', updatedAt: '2026-07-16T00:00:00Z' }], page: 1, pageSize: 25, total: 1, pages: 1 }
    else if (path === '/api/v1/decisions/enrollment_eligibility') json = revision
    else if (path === '/api/v1/jobs') json = []
    else if (path === '/api/v1/import-runs') json = []
    else if (path === '/api/v1/review-items') json = []
    else if (path.includes('/api/v1/golden-suites/')) json = []
    else if (path.includes('/api/v1/releases/mode-a/')) json = []
    else if (path === '/api/v1/releases/mode-b') json = []
    else if (path.includes('/api/v1/sites/') && path.endsWith('/profiles')) json = []
    await route.fulfill({ json })
  })
}

const revision = {
  envelope: { decisionKey: 'enrollment_eligibility', revision: 2, lifecycleStatus: 'APPROVED', contentHash: '9f75f8e59bf2a7e6d4e1c9a401bc2b7c3d91cc87de23724d1b1fe0d08111a320', effectiveFrom: '2026-08-01T00:00:00Z', effectiveTo: null, createdBy: 'maker-a', submittedBy: 'maker-a', approvedBy: 'checker-b' },
  content: { decisionName: '가입 자격 판정', rules: [{ ruleId: 'R001', when: { all: [] }, then: [{ output: 'eligible', value: false }], confidence: 0.95 }] },
}
