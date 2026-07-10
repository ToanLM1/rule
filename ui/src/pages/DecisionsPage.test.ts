import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DecisionsPage from './DecisionsPage.vue'

const revision = {
  envelope: {
    decisionKey: 'enrollment_eligibility',
    revision: 2,
    lifecycleStatus: 'SUBMITTED',
    contentHash: 'a'.repeat(64),
    effectiveFrom: '2026-08-01T00:00:00Z',
    effectiveTo: null,
    createdBy: 'maker-a',
    submittedBy: 'maker-a',
    approvedBy: null,
  },
  content: {
    decisionName: '가입 자격 판정',
    rules: [{ ruleId: 'R001', when: { all: [] }, then: [], confidence: 0.95 }],
  },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    let body: unknown = revision
    if (url.endsWith('/decisions')) body = [{ decisionKey: 'enrollment_eligibility', name: '가입 자격 판정', latestRevision: 2, latestStatus: 'SUBMITTED' }]
    if (url.endsWith('/audit')) body = [{ id: 1, actor: 'maker-a', action: 'SUBMIT', fromStatus: 'DRAFT', toStatus: 'SUBMITTED', at: '2026-08-01T00:00:00Z' }]
    if (url.includes('/golden-suites/')) body = [{ revision: 1, status: 'APPROVED', contentHash: 'b'.repeat(64) }]
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
})

afterEach(() => vi.unstubAllGlobals())

describe('DecisionsPage', () => {
  it('separates governed envelope and canonical content', async () => {
    const wrapper = mount(DecisionsPage, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Decision governance')
    expect(wrapper.text()).toContain('가입 자격 판정')
    expect(wrapper.get('[aria-label="Revision envelope"]').text()).toContain('maker-a')
    expect(wrapper.text()).toContain('R001')
    expect(wrapper.get('[aria-label="Actor"]').element).toBeTruthy()
  })

  it('edits immutable content as a new revision and labels preview advisory', async () => {
    const wrapper = mount(DecisionsPage, { global: { plugins: [createPinia()] } })
    await flushPromises()
    await wrapper.get('button.button.ghost').trigger('click')
    expect(wrapper.get('[role="dialog"]').text()).toContain('Create new draft')
    await wrapper.get('[role="dialog"] button.button.ghost').trigger('click')
    const preview = wrapper.findAll('.tabs button').find((button) => button.text() === 'preview')
    await preview?.trigger('click')
    expect(wrapper.text()).toContain('ZEN is not the Mode-B production authority')
  })
})
