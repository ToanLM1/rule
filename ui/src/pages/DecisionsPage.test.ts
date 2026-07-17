import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppStore } from '../stores/app'
import DecisionsPage from './DecisionsPage.vue'

const summary = { decisionKey: 'enrollment_eligibility', name: 'Enrollment eligibility', latestRevision: 2, latestStatus: 'SUBMITTED', owner: 'maker-a', updatedAt: '2026-08-01T00:00:00Z' }
const revision = { envelope: { decisionKey: summary.decisionKey, revision: 2, lifecycleStatus: 'SUBMITTED', contentHash: 'a'.repeat(64), effectiveFrom: '2026-08-01T00:00:00Z', effectiveTo: null, createdBy: 'maker-a', submittedBy: 'maker-a', approvedBy: null }, content: { decisionName: summary.name, rules: [{ ruleId: 'R001', when: { all: [] }, then: [], confidence: 0.95 }] } }
let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia=createPinia();setActivePinia(pinia);useAppStore().siteId='site-1'
  vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{const url=String(input);const body=url.includes('/api/v1/decisions/enrollment_eligibility')?revision:{items:[summary],page:1,pageSize:25,total:1,pages:1};return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}})}))
})
afterEach(()=>vi.unstubAllGlobals())

describe('DecisionsPage',()=>{
  it('uses a server-paginated portfolio',async()=>{const wrapper=mount(DecisionsPage,{global:{plugins:[pinia],stubs:{RouterLink:true}}});await flushPromises();expect(wrapper.get('h1').text()).toBe('Decisions');expect(wrapper.text()).toContain('Enrollment eligibility');expect(wrapper.text()).toContain('1 decisions');expect(wrapper.get('[aria-label="Search decisions"]')).toBeTruthy()})
  it('opens the governed decision-table drawer',async()=>{const wrapper=mount(DecisionsPage,{global:{plugins:[pinia],stubs:{RouterLink:true}}});await flushPromises();await wrapper.get('[aria-label="Open decision"]').trigger('click');await flushPromises();expect(wrapper.get('[role="dialog"]').text()).toContain('Enrollment eligibility');expect(wrapper.text()).toContain('Immutable revision');expect(wrapper.text()).toContain('Advanced JSON')})
})
