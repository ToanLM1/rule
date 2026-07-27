import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import OverviewPage from './OverviewPage.vue'
import { useAppStore } from '../stores/app'

type Behaviour = 'ok' | 'error' | 'timeout' | 'empty' | 'partial'

const metrics = { decisions: 260, openReviews: 13, activeJobs: 0, failedJobs: 10 }
const job = {
  id: 'job-1',
  siteId: 'site-1',
  type: 'REPOSITORY_IMPORT',
  status: 'FAILED',
  progress: 100,
  attempts: 1,
  maxAttempts: 3,
  cancelRequested: false,
  correlationId: 'corr-1',
  createdBy: 'maker-a',
  createdAt: '2026-07-20T09:00:00Z',
}
const run = {
  id: 'run-1',
  siteId: 'site-1',
  jobId: 'job-1',
  adapter: 'code-java',
  sourceName: 'dummy-rules',
  sourceRevision: '2e73916',
  status: 'FAILED',
  progress: 100,
  createdBy: 'maker-a',
  createdAt: '2026-07-20T09:00:00Z',
}

let pinia: ReturnType<typeof createPinia>
let router: ReturnType<typeof createRouter>

function stubFetch(behaviour: Behaviour) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input)).pathname
      if (behaviour === 'timeout') throw new Error('Failed to fetch')
      if (behaviour === 'error') {
        return new Response(JSON.stringify({ detail: 'Database unreachable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (behaviour === 'partial' && path !== '/api/v1/overview') {
        return new Response(JSON.stringify({ detail: 'Database unreachable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      let body: unknown = []
      if (path === '/api/v1/overview') body = behaviour === 'empty' ? { decisions: 0, openReviews: 0, activeJobs: 0, failedJobs: 0 } : metrics
      else if (path === '/api/v1/jobs') body = behaviour === 'empty' ? [] : [job]
      else if (path === '/api/v1/import-runs') body = behaviour === 'empty' ? [] : [run]
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
      { path: '/overview', component: { template: '<div />' } },
      { path: '/imports', component: { template: '<div />' } },
      { path: '/reviews', component: { template: '<div />' } },
      { path: '/studio', component: { template: '<div />' } },
      { path: '/test-suites', component: { template: '<div />' } },
      { path: '/releases', component: { template: '<div />' } },
      { path: '/operations', component: { template: '<div />' } },
    ],
  })
  await router.push('/overview')
  await router.isReady()
})

afterEach(() => vi.unstubAllGlobals())

async function mountPage(behaviour: Behaviour) {
  stubFetch(behaviour)
  const wrapper = mount(OverviewPage, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

describe('OverviewPage truthful states', () => {
  it('renders populated counts from a successful response', async () => {
    const wrapper = await mountPage('ok')
    expect(wrapper.text()).toContain('260')
    expect(wrapper.text()).toContain('13')
    expect(wrapper.text()).toContain('10 failed job(s)')
    expect(wrapper.text()).not.toContain('No failed jobs')
  })

  it('never turns an offline request into zero or a clear-state claim', async () => {
    const wrapper = await mountPage('timeout')
    expect(wrapper.text()).toContain('Unavailable')
    expect(wrapper.text()).not.toContain('No imports yet')
    expect(wrapper.text()).not.toContain('No job activity')
    expect(wrapper.text()).not.toContain('No failed jobs')
    expect(wrapper.text()).toContain('Import history unavailable')
  })

  it('treats a 5xx the same way and consolidates duplicate errors into one alert', async () => {
    const wrapper = await mountPage('error')
    const alerts = wrapper.findAll('[role="alert"]')
    expect(alerts).toHaveLength(1)
    expect(alerts[0].text()).toContain('Database unreachable')
    expect(wrapper.text()).toContain('Unavailable')
  })

  it('keeps successful counts truthful when only some requests fail', async () => {
    const wrapper = await mountPage('partial')
    expect(wrapper.text()).toContain('260')
    expect(wrapper.text()).toContain('Job activity unavailable')
    expect(wrapper.text()).not.toContain('No imports yet')
  })

  it('shows real zeros and the health claim only after a successful empty response', async () => {
    const wrapper = await mountPage('empty')
    expect(wrapper.text()).toContain('No imports yet')
    expect(wrapper.text()).toContain('No job activity')
    expect(wrapper.text()).toContain('No failed jobs')
  })

  it('suppresses site counts when no workspace/site context exists', async () => {
    useAppStore().siteId = ''
    const wrapper = await mountPage('ok')
    expect(wrapper.text()).toContain('No workspace/site context is available')
    expect(wrapper.text()).not.toContain('No failed jobs')
  })
})
