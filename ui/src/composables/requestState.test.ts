import { describe, expect, it } from 'vitest'

import { consolidateErrors, showsEmptyState, truthfulCount, useRequestState } from './requestState'

describe('useRequestState', () => {
  it('starts idle and never claims emptiness before a response', async () => {
    const state = useRequestState<number[]>([])
    expect(state.phase.value).toBe('idle')
    expect(showsEmptyState(state.phase.value)).toBe(false)
    expect(state.trusted.value).toBe(false)
  })

  it('reports empty only after a successful empty response', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => [])
    expect(state.phase.value).toBe('empty')
    expect(state.trusted.value).toBe(true)
    expect(showsEmptyState(state.phase.value)).toBe(true)
  })

  it('reports ready for a populated response', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => [1, 2])
    expect(state.phase.value).toBe('ready')
    expect(state.data.value).toEqual([1, 2])
    expect(state.loadedAt.value).not.toBe('')
  })

  it('turns a first failure into error, not empty', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => {
      throw new Error('Failed to fetch')
    })
    expect(state.phase.value).toBe('error')
    expect(state.error.value).toBe('Failed to fetch')
    expect(showsEmptyState(state.phase.value)).toBe(false)
    expect(state.trusted.value).toBe(false)
    expect(state.failed.value).toBe(true)
  })

  it('keeps previously loaded data as stale when a refresh fails', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => [7])
    await state.run(async () => {
      throw new Error('timeout')
    })
    expect(state.phase.value).toBe('stale')
    expect(state.data.value).toEqual([7])
    expect(state.trusted.value).toBe(false)
    expect(state.failed.value).toBe(true)
  })

  it('resets back to idle', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => [1])
    state.reset()
    expect(state.phase.value).toBe('idle')
    expect(state.loadedAt.value).toBe('')
  })

  it('treats a 5xx problem detail as an error phase', async () => {
    const state = useRequestState<number[]>([])
    await state.run(async () => {
      throw new Error('Request failed: 503')
    })
    expect(state.phase.value).toBe('error')
    expect(state.error.value).toBe('Request failed: 503')
  })
})

describe('truthfulCount', () => {
  it('never renders zero for a failed or unloaded request', () => {
    expect(truthfulCount('error', 0)).toBe('Unavailable')
    expect(truthfulCount('stale', 0)).toBe('Unavailable')
    expect(truthfulCount('loading', 0)).toBe('—')
    expect(truthfulCount('idle', 12)).toBe('—')
  })

  it('renders a real zero from a successful response', () => {
    expect(truthfulCount('ready', 0)).toBe('0')
    expect(truthfulCount('empty', 0)).toBe('0')
    expect(truthfulCount('ready', 1234)).toBe((1234).toLocaleString())
  })

  it('renders unavailable when a successful response omitted the value', () => {
    expect(truthfulCount('ready', undefined)).toBe('Unavailable')
    expect(truthfulCount('ready', null)).toBe('Unavailable')
  })
})

describe('consolidateErrors', () => {
  it('returns nothing when every request succeeded', () => {
    expect(consolidateErrors([{ label: 'Jobs', message: '' }])).toBe('')
  })

  it('merges duplicate messages into one scoped alert', () => {
    const message = consolidateErrors([
      { label: 'Jobs', message: 'Failed to fetch' },
      { label: 'Imports', message: 'Failed to fetch' },
      { label: 'Metrics', message: '' },
    ])
    expect(message).toBe('Jobs, Imports unavailable: Failed to fetch')
  })

  it('keeps distinct failures distinguishable', () => {
    const message = consolidateErrors([
      { label: 'Jobs', message: 'timeout' },
      { label: 'Imports', message: '503' },
    ])
    expect(message).toBe('Jobs unavailable: timeout · Imports unavailable: 503')
  })
})
