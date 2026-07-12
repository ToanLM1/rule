import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import OrchestrationPage from './OrchestrationPage.vue'

const candidate = {
  decisionId: 'eligibility', decisionName: '가입 자격', profile: 'RULE_IR_V1', schemaVersion: 1,
  programContexts: [{ programId: 'LOCAL', kind: 'SERVICE', entryPoint: 'local://test' }],
  hitPolicy: 'FIRST', inputs: [{ name: 'age', type: 'integer', required: true }],
  outputs: [{ name: 'result', type: 'string' }], defaultOutput: { result: '가입 가능' },
  rules: [{ ruleId: 'R001', when: { all: [{ left: { kind: 'INPUT', name: 'age' }, operator: 'LT', right: { kind: 'LITERAL', value: 18 } }] }, then: [{ output: 'result', value: '미성년' }], origin: 'EXTRACTED', sourceReferences: [], confidence: 1 }],
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    let body: unknown = {}
    if (url.endsWith('/orchestration/catalog')) body = {
      evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE', persistent: false,
      adapters: ['db-postgres-stored-object', 'ui-html-validation', 'engine-native', 'engine-dmn'],
      generators: ['dmn-export', 'csharp-source'],
      hostInventory: { java: true, dotnet: false, joern: true, zen: true, postgres: true, sqlite: true },
      boundaries: ['Inputs are isolated', 'Scripts are never executed'],
    }
    if (url.endsWith('/orchestration/extract')) body = {
      evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE', persistent: false,
      batch: { adapter: 'db-postgres-stored-object', decisions: [{ decisionKey: 'eligibility', content: candidate }], unmappable: [], diagnostics: [], sourceSnapshot: { contentHash: 'a'.repeat(64), revision: 'v1' } },
    }
    if (url.endsWith('/orchestration/generate')) body = {
      generator: 'dmn-export', evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE',
      persistent: false, authoritative: false, path: 'preview/eligibility.dmn',
      content: '<decisionTable hitPolicy="FIRST"/>', contentHash: 'b'.repeat(64),
    }
    if (url.endsWith('/orchestration/preflight')) body = {
      schemaVersion: 1, reports: [{ site: 'local-workbench', ready: true }], matrixHash: 'c'.repeat(64),
    }
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
})

afterEach(() => vi.unstubAllGlobals())

describe('OrchestrationPage', () => {
  it('extracts a local candidate and generates a non-authoritative target preview', async () => {
    const wrapper = mount(OrchestrationPage, { global: { plugins: [createPinia()], stubs: ['RouterLink'] } })
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Phase 3 workbench')
    expect(wrapper.text()).toContain('LOCAL_PREVIEW_NON_AUTHORITATIVE')
    await wrapper.get('.run-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="candidate-output"]').text()).toContain('미성년')
    await wrapper.findAll('button').find((item) => item.text().includes('Continue to target'))?.trigger('click')
    await wrapper.findAll('button').find((item) => item.text() === 'Generate preview')?.trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="generated-output"]').text()).toContain('decisionTable')
    expect(wrapper.text()).toContain('not persisted')
  })

  it('runs the fail-closed capability preflight', async () => {
    const wrapper = mount(OrchestrationPage, { global: { plugins: [createPinia()], stubs: ['RouterLink'] } })
    await flushPromises()
    await wrapper.findAll('.workbench-nav button')[2].trigger('click')
    await wrapper.findAll('button').find((item) => item.text() === 'Run capability preflight')?.trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="preflight-output"]').text()).toContain('local-workbench')
    expect(wrapper.get('[data-testid="preflight-output"]').text()).toContain('ready')
  })
})
