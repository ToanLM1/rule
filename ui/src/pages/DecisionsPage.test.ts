import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppStore } from '../stores/app'
import DecisionsPage from './DecisionsPage.vue'

const summary = { decisionKey: 'enrollment_eligibility', name: 'Enrollment eligibility', latestRevision: 2, latestStatus: 'SUBMITTED', owner: 'maker-a', updatedAt: '2026-08-01T00:00:00Z' }
const revision = { envelope: { decisionKey: summary.decisionKey, revision: 2, lifecycleStatus: 'SUBMITTED', contentHash: 'a'.repeat(64), effectiveFrom: '2026-08-01T00:00:00Z', effectiveTo: null, createdBy: 'maker-a', submittedBy: 'maker-a', approvedBy: null }, content: { decisionName: summary.name, inputs: [{ name: 'age', type: 'integer', sourcePath: 'customer.age' }], outputs: [{ name: 'eligible', type: 'boolean' }, { name: 'reason', type: 'string' }], rules: [{ ruleId: 'R001', when: { all: [{ left: { kind: 'INPUT', name: 'age' }, operator: 'LT', right: { kind: 'LITERAL', value: 18 } }] }, then: [{ output: 'eligible', value: false }, { output: 'reason', value: 'UNDER_AGE' }], sourceReferences: [{ type: 'JAVA_SOURCE' }], confidence: 0.95 }] } }
let pinia: ReturnType<typeof createPinia>
let router: ReturnType<typeof createRouter>

beforeEach(async () => {
  pinia = createPinia()
  setActivePinia(pinia)
  useAppStore().siteId = 'site-1'
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/decisions', component: { template: '<div />' } },
      { path: '/imports', component: { template: '<div />' } },
    ],
  })
  await router.push('/decisions')
  await router.isReady()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const body = url.includes('/api/v1/decisions/enrollment_eligibility') ? revision : { items: [summary], page: 1, pageSize: 25, total: 1, pages: 1 }
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
})

afterEach(() => vi.unstubAllGlobals())

function mountPage() {
  return mount(DecisionsPage, { global: { plugins: [pinia, router] } })
}

describe('DecisionsPage', () => {
  it('uses a server-paginated portfolio', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Decisions')
    expect(wrapper.text()).toContain('Enrollment eligibility')
    expect(wrapper.text()).toContain('1 decisions')
    expect(wrapper.get('[aria-label="Search decisions"]')).toBeTruthy()
  })

  it('opens the governed decision-table drawer', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[aria-label="Open decision"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="dialog"]').text()).toContain('Enrollment eligibility')
    expect(wrapper.text()).toContain('Immutable revision')
    expect(wrapper.text()).toContain('Business inputs')
    expect(wrapper.text()).toContain('customer.age')
    expect(wrapper.text()).toContain('Business outcomes')
    expect(wrapper.text()).toContain('Advanced JSON')
  })

  it('accepts a command-palette query handoff', async () => {
    await router.replace('/decisions?q=eligibility')
    const wrapper = mountPage()
    await flushPromises()
    expect((wrapper.get('[aria-label="Search decisions"]').element as HTMLInputElement).value).toBe('eligibility')
  })
})
