import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppStore } from './app'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
  setActivePinia(createPinia())
})

describe('appearance preferences', () => {
  it('resolves the system theme and applies it to the document', () => {
    const store = useAppStore()
    store.hydrateAppearance()
    expect(store.theme).toBe('system')
    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('persists explicit theme and sidebar state', () => {
    const store = useAppStore()
    store.setTheme('light')
    store.setSidebarCollapsed(true)
    expect(localStorage.getItem('brp.theme')).toBe('light')
    expect(localStorage.getItem('brp.sidebarCollapsed')).toBe('true')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('cycles system, light and dark without losing the selected preference', () => {
    const store = useAppStore()
    store.cycleTheme()
    expect(store.theme).toBe('light')
    store.cycleTheme()
    expect(store.theme).toBe('dark')
    store.cycleTheme()
    expect(store.theme).toBe('system')
  })
})
