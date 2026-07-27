import type { Page } from '@playwright/test'

export const siteId = '00000000-0000-0000-0000-000000000002'

/** Two records deliberately share a display name and revision, as the live corpus does. */
export const decisionCorpus = [
  {
    decisionKey: 'enrollment_eligibility',
    name: '가입 자격 판정',
    productKey: 'CANCER_BASIC',
    flowKey: 'ENROLLMENT',
    latestRevision: 2,
    latestStatus: 'APPROVED',
    owner: 'maker-a',
    updatedAt: '2026-07-16T00:00:00Z',
  },
  {
    decisionKey: 'enrollment_eligibility_kb',
    name: '가입 자격 판정',
    productKey: 'CANCER_PLUS',
    flowKey: 'ENROLLMENT',
    latestRevision: 2,
    latestStatus: 'DRAFT',
    owner: 'maker-b',
    updatedAt: '2026-07-17T00:00:00Z',
  },
  ...Array.from({ length: 22 }, (_, index) => ({
    decisionKey: `renewal_rule_${String(index).padStart(3, '0')}`,
    name: `Renewal rule ${index}`,
    productKey: 'RENEWAL',
    flowKey: 'RENEWAL',
    latestRevision: 1,
    latestStatus: 'APPROVED',
    owner: 'maker-a',
    updatedAt: '2026-07-18T00:00:00Z',
  })),
]

export const failedJob = {
  id: '9c2f0a1e-0000-4000-8000-000000000001',
  siteId,
  type: 'REPOSITORY_IMPORT',
  status: 'FAILED',
  progress: 45,
  attempts: 3,
  maxAttempts: 3,
  cancelRequested: false,
  errorCode: 'PROVIDER_ERROR',
  errorDetail: 'HTTP 429 rate limit from provider; token=abcdefgh was used',
  correlationId: '5f1d3b7a-0000-4000-8000-0000000000aa',
  createdBy: 'maker-a',
  createdAt: '2026-07-20T09:00:00Z',
  startedAt: '2026-07-20T09:00:05Z',
  finishedAt: '2026-07-20T09:00:40Z',
}

export const importRun = {
  id: '3a7c1b90-0000-4000-8000-000000000002',
  siteId,
  jobId: failedJob.id,
  adapter: 'code-java',
  sourceName: 'novoda/dojos',
  sourceRevision: '2e7391623b42617af1bbdad227e3e4701e89af2c',
  status: 'FAILED',
  progress: 45,
  candidateCount: 0,
  reviewCount: 2,
  createdBy: 'maker-a',
  createdAt: '2026-07-20T09:00:00Z',
}

const modeBProfile = {
  id: 'aa000000-0000-4000-8000-000000000003',
  siteId,
  revision: 2,
  contentHash: 'c'.repeat(64),
  document: {
    deliveryMode: 'B',
    target: {
      repository: 'targets/dummy-rules',
      baseBranch: 'main',
      buildCommand: './gradlew test',
      prProvider: 'github',
      providerRepository: 'owner/dummy-rules',
      tokenSecretRef: 'BRP_GITHUB_TOKEN',
    },
  },
  createdBy: 'admin',
  createdAt: '2026-07-03T00:00:00Z',
}

const approvedSuite = {
  id: 'bb000000-0000-4000-8000-000000000004',
  revision: 2,
  status: 'APPROVED',
  contentHash: 'b'.repeat(64),
  caseCount: 4,
  cases: [],
  createdBy: 'maker-a',
  createdAt: '2026-07-02T00:00:00Z',
}

const revision = {
  envelope: {
    decisionKey: 'enrollment_eligibility',
    revision: 2,
    lifecycleStatus: 'APPROVED',
    contentHash: '9f75f8e59bf2a7e6d4e1c9a401bc2b7c3d91cc87de23724d1b1fe0d08111a320',
    effectiveFrom: '2026-08-01T00:00:00Z',
    effectiveTo: null,
    createdBy: 'maker-a',
    submittedBy: 'maker-a',
    approvedBy: 'checker-b',
  },
  content: {
    decisionName: '가입 자격 판정',
    rules: [{ ruleId: 'R001', when: { all: [] }, then: [{ output: 'eligible', value: false }], confidence: 0.95 }],
  },
}

function decisionPage(url: URL) {
  const q = (url.searchParams.get('q') ?? '').toLowerCase()
  const page = Number(url.searchParams.get('page') ?? '1')
  const pageSize = Number(url.searchParams.get('page_size') ?? '25')
  const filtered = q
    ? decisionCorpus.filter((item) => item.decisionKey.toLowerCase().includes(q) || item.name.toLowerCase().includes(q))
    : decisionCorpus
  return {
    items: filtered.slice((page - 1) * pageSize, page * pageSize),
    page,
    pageSize,
    total: filtered.length,
    pages: Math.max(Math.ceil(filtered.length / pageSize), 1),
  }
}

export type MockOptions = {
  /** Paths (substring match) that should respond 503 instead of succeeding. */
  fail?: string[]
  jobs?: unknown[]
  importRuns?: unknown[]
  goldenSuites?: unknown[]
  profiles?: unknown[]
  overview?: Record<string, number>
}

export async function mockApi(page: Page, options: MockOptions = {}) {
  await page.route('http://localhost:8100/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (options.fail?.some((fragment) => path.includes(fragment))) {
      await route.fulfill({ status: 503, json: { detail: 'Database unreachable' } })
      return
    }
    let json: unknown = {}
    if (path === '/api/v1/context') {
      json = {
        workspaces: [{ id: '00000000-0000-0000-0000-000000000001', key: 'rules', name: 'Rules Operations' }],
        sites: [
          {
            id: siteId,
            workspaceId: '00000000-0000-0000-0000-000000000001',
            key: 'seoul',
            name: 'Seoul Underwriting',
            status: 'ACTIVE',
            defaultLocale: 'en',
            timezone: 'Asia/Seoul',
          },
        ],
        authentication: 'DEVELOPMENT_IDENTITY',
        productionBlocked: true,
      }
    } else if (path === '/api/v1/overview') {
      json = options.overview ?? { decisions: decisionCorpus.length, openReviews: 2, activeJobs: 0, failedJobs: 0 }
    } else if (path === '/api/v1/decisions') json = decisionPage(url)
    else if (path.includes('/revisions')) json = [revision]
    else if (path.startsWith('/api/v1/decisions/')) json = revision
    else if (path === '/api/v1/jobs') json = options.jobs ?? []
    else if (path === '/api/v1/import-runs') json = options.importRuns ?? []
    else if (path === '/api/v1/review-items') json = []
    else if (path.includes('/api/v1/golden-suites/')) json = options.goldenSuites ?? []
    else if (path.includes('/api/v1/releases/mode-a/')) json = []
    else if (path === '/api/v1/releases/mode-b') json = []
    else if (path.includes('/api/v1/sites/') && path.endsWith('/profiles')) json = options.profiles ?? []
    await route.fulfill({ json })
  })
}

export const fixtures = { modeBProfile, approvedSuite, revision }
