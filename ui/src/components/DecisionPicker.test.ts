import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DecisionPicker from './DecisionPicker.vue'
import { useAppStore } from '../stores/app'

const TOTAL = 260

/** Two records that share a display name and revision but differ by decision key. */
function corpus(page: number, pageSize: number, q?: string) {
  const all = Array.from({ length: TOTAL }, (_, index) => ({
    decisionKey: `decision_${String(index).padStart(3, '0')}`,
    name: index < 2 ? '가입 자격 판정' : `Decision ${index}`,
    productKey: 'CANCER_BASIC',
    flowKey: 'ENROLLMENT',
    latestRevision: 2,
    latestStatus: index === 0 ? 'DRAFT' : 'APPROVED',
  }))
  const filtered = q ? all.filter((item) => item.decisionKey.includes(q) || item.name.includes(q)) : all
  const items = filtered.slice((page - 1) * pageSize, page * pageSize)
  return { items, page, pageSize, total: filtered.length, pages: Math.ceil(filtered.length / pageSize) }
}

let pinia: ReturnType<typeof createPinia>
let requested: string[]

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  useAppStore().siteId = 'site-1'
  requested = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input))
      requested.push(url.search)
      const page = Number(url.searchParams.get('page') ?? '1')
      const pageSize = Number(url.searchParams.get('page_size') ?? '10')
      const q = url.searchParams.get('q') ?? undefined
      return new Response(JSON.stringify(corpus(page, pageSize, q)), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

function mountPicker(modelValue = '') {
  return mount(DecisionPicker, { props: { modelValue }, global: { plugins: [pinia] } })
}

describe('DecisionPicker', () => {
  it('states the real result scope instead of silently truncating the corpus', async () => {
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.get('[role="combobox"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(`of ${TOTAL} decisions`)
    expect(wrapper.findAll('[role="option"]')).toHaveLength(10)
  })

  it('identifies every option by its stable decision key, not name plus revision', async () => {
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.get('[role="combobox"]').trigger('click')
    await flushPromises()
    const options = wrapper.findAll('[role="option"]')
    const first = options[0].text()
    const second = options[1].text()
    expect(first).toContain('가입 자격 판정')
    expect(second).toContain('가입 자격 판정')
    expect(first).toContain('decision_000')
    expect(second).toContain('decision_001')
    expect(first).not.toBe(second)
    expect(options[0].attributes('id')).not.toBe(options[1].attributes('id'))
  })

  it('reaches decisions beyond the first page', async () => {
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.get('[role="combobox"]').trigger('click')
    await flushPromises()
    const next = wrapper.findAll('button').find((button) => button.text().includes('Next'))!
    await next.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('decision_010')
    expect(wrapper.text()).toContain('Page 2 of 26')
  })

  it('searches the server corpus rather than filtering one loaded page', async () => {
    vi.useFakeTimers()
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.get('[role="combobox"]').trigger('click')
    await flushPromises()
    await wrapper.get('input[type="search"]').setValue('decision_25')
    vi.advanceTimersByTime(300)
    vi.useRealTimers()
    await flushPromises()
    expect(requested.some((search) => search.includes('q=decision_25'))).toBe(true)
    expect(wrapper.text()).toContain('matching “decision_25”')
  })

  it('emits the stable key for keyboard selection', async () => {
    const wrapper = mountPicker()
    await flushPromises()
    const trigger = wrapper.get('[role="combobox"]')
    await trigger.trigger('click')
    await flushPromises()
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['decision_001'])
  })

  it('resolves a selected key that is not on the current page', async () => {
    const wrapper = mountPicker('decision_200')
    await flushPromises()
    expect(wrapper.text()).toContain('decision_200')
    expect(wrapper.text()).toContain('APPROVED')
  })

  it('never reports an empty corpus when the search request failed', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"Failed to fetch"}', { status: 503 })))
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.get('[role="combobox"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Result scope unknown')
    expect(wrapper.text()).not.toContain('No governed decisions in this site yet')
  })
})
