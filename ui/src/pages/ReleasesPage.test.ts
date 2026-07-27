import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ReleasesPage from './ReleasesPage.vue'
import { useAppStore } from '../stores/app'

const decisionKey = 'enrollment_eligibility_v2'

const draftSummary = {
  decisionKey,
  name: '가입 자격 판정',
  productKey: 'CANCER_BASIC',
  flowKey: 'ENROLLMENT',
  latestRevision: 3,
  latestStatus: 'DRAFT',
}
const approvedSummary = { ...draftSummary, latestStatus: 'APPROVED' }

const draftRevision = {
  envelope: {
    decisionKey,
    revision: 3,
    lifecycleStatus: 'DRAFT',
    contentHash: 'a'.repeat(64),
    effectiveFrom: '2026-07-01T00:00:00Z',
    effectiveTo: null,
    createdBy: 'maker-a',
    submittedBy: null,
    approvedBy: null,
  },
  content: { decisionName: draftSummary.name, rules: [] },
}
const approvedRevision = {
  ...draftRevision,
  envelope: { ...draftRevision.envelope, lifecycleStatus: 'APPROVED', approvedBy: 'checker-b' },
}
const approvedSuite = {
  id: 'suite-1',
  revision: 2,
  status: 'APPROVED',
  contentHash: 'b'.repeat(64),
  caseCount: 4,
  cases: [],
  createdBy: 'maker-a',
  createdAt: '2026-07-02T00:00:00Z',
}
const modeBProfile = {
  id: 'profile-1',
  siteId: 'site-1',
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

type Scenario = {
  summary?: unknown
  revisions?: unknown
  suites?: unknown
  profiles?: unknown
  failSuites?: boolean
}

let pinia: ReturnType<typeof createPinia>
let router: ReturnType<typeof createRouter>
let posted: string[]

function stubFetch(scenario: Scenario) {
  posted = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input))
      const path = url.pathname
      if (init?.method === 'POST') {
        posted.push(path)
        return new Response(JSON.stringify({ id: 'job-1' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      let body: unknown = []
      if (path === '/api/v1/decisions') {
        body = { items: [scenario.summary ?? approvedSummary], page: 1, pageSize: 10, total: 1, pages: 1 }
      } else if (path.endsWith('/profiles')) body = scenario.profiles ?? [modeBProfile]
      else if (path === '/api/v1/releases/mode-b') body = []
      else if (path.startsWith('/api/v1/releases/mode-a/')) body = []
      else if (path.startsWith('/api/v1/golden-suites/')) {
        if (scenario.failSuites) {
          return new Response(JSON.stringify({ detail: 'Failed to fetch' }), { status: 503, headers: { 'Content-Type': 'application/json' } })
        }
        body = scenario.suites ?? [approvedSuite]
      } else if (path.includes('/revisions')) body = scenario.revisions ?? [approvedRevision]
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

beforeEach(async () => {
  pinia = createPinia()
  setActivePinia(pinia)
  useAppStore().siteId = 'site-1'
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/releases', component: { template: '<div />' } },
      { path: '/decisions', component: { template: '<div />' } },
      { path: '/studio', component: { template: '<div />' } },
      { path: '/test-suites', component: { template: '<div />' } },
      { path: '/sites', component: { template: '<div />' } },
      { path: '/operations', component: { template: '<div />' } },
    ],
  })
})

afterEach(() => vi.unstubAllGlobals())

async function mountPage(scenario: Scenario = {}, query = '') {
  stubFetch(scenario)
  await router.push(`/releases${query}`)
  await router.isReady()
  const wrapper = mount(ReleasesPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function primaryButtons(wrapper: Awaited<ReturnType<typeof mountPage>>) {
  const buttons = wrapper.findAll('button')
  return {
    publish: buttons.find((button) => button.text().includes('Create publication'))!,
    deliver: buttons.find((button) => button.text().includes('Start delivery'))!,
  }
}

describe('ReleasesPage fail-closed gates', () => {
  it('enables both accepted targets when every prerequisite is proven', async () => {
    const wrapper = await mountPage({}, `?decision=${decisionKey}`)
    const { publish, deliver } = primaryButtons(wrapper)
    expect(publish.attributes('disabled')).toBeUndefined()
    expect(deliver.attributes('disabled')).toBeUndefined()
    // Accepted scope stays visible.
    expect(wrapper.text()).toContain('Mode A')
    expect(wrapper.text()).toContain('Mode B')
    expect(wrapper.text()).toContain('GitHub')
    expect(wrapper.text()).toContain('GitLab')
  })

  it('disables both actions for a DRAFT decision with no approved revision', async () => {
    const wrapper = await mountPage(
      { summary: draftSummary, revisions: [draftRevision] },
      `?decision=${decisionKey}`,
    )
    const { publish, deliver } = primaryButtons(wrapper)
    expect(publish.attributes('disabled')).toBeDefined()
    expect(deliver.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('A separate checker must approve it')
    expect(wrapper.text()).toContain('Owner: Checker')
  })

  it('disables the action when golden evidence is missing and names the remediation', async () => {
    const wrapper = await mountPage({ suites: [] }, `?decision=${decisionKey}`)
    expect(primaryButtons(wrapper).publish.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('No golden suite revision has been captured')
    expect(wrapper.find('a[href="/test-suites"]').exists()).toBe(true)
  })

  it('disables Mode-B delivery without a Mode-B site profile but keeps Mode A available', async () => {
    const wrapper = await mountPage({ profiles: [] }, `?decision=${decisionKey}`)
    const { publish, deliver } = primaryButtons(wrapper)
    expect(deliver.attributes('disabled')).toBeDefined()
    expect(publish.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('Mode A stays available')
  })

  it('disables Mode-B delivery when the credential reference is unresolved', async () => {
    const profile = {
      ...modeBProfile,
      document: { deliveryMode: 'B', target: { ...modeBProfile.document.target, tokenSecretRef: '' } },
    }
    const wrapper = await mountPage({ profiles: [profile] }, `?decision=${decisionKey}`)
    expect(primaryButtons(wrapper).deliver.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('tokenSecretRef')
  })

  it('fails closed and reports the failure when release evidence cannot be loaded', async () => {
    const wrapper = await mountPage({ failSuites: true }, `?decision=${decisionKey}`)
    const { publish, deliver } = primaryButtons(wrapper)
    expect(publish.attributes('disabled')).toBeDefined()
    expect(deliver.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Golden evidence unavailable')
    expect(wrapper.text()).toContain('cannot be proven')
  })

  it('submits nothing while a gate is unsatisfied, leaving backend enforcement untouched', async () => {
    const wrapper = await mountPage({ summary: draftSummary, revisions: [draftRevision] }, `?decision=${decisionKey}`)
    const component = wrapper.vm as unknown as { publish: () => Promise<void>; deliver: () => Promise<void> }
    await component.publish?.()
    await component.deliver?.()
    await flushPromises()
    expect(posted).toEqual([])
  })

  it('carries the governed change from the deep link into the picker', async () => {
    const wrapper = await mountPage({}, `?decision=${decisionKey}`)
    expect(wrapper.get('[role="combobox"]').text()).toContain(decisionKey)
    expect(useAppStore().decisionKey).toBe(decisionKey)
  })
})
