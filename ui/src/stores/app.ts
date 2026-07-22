import { defineStore } from 'pinia'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

function preferredSystemTheme(): ResolvedTheme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveTheme(theme: ThemePreference): ResolvedTheme {
  return theme === 'system' ? preferredSystemTheme() : theme
}

export const useAppStore = defineStore('app', {
  state: () => ({
    apiBaseUrl: import.meta.env.VITE_BRP_API_BASE_URL ?? 'http://localhost:8100',
    workspaceId: localStorage.getItem('brp.workspace') ?? '',
    siteId: localStorage.getItem('brp.site') ?? '',
    actor: localStorage.getItem('brp.actor') ?? 'maker-a',
    locale: (localStorage.getItem('brp.locale') ?? 'en') as 'en' | 'ko',
    theme: (localStorage.getItem('brp.theme') ?? 'system') as ThemePreference,
    resolvedTheme: 'light' as ResolvedTheme,
    sidebarCollapsed: localStorage.getItem('brp.sidebarCollapsed') === 'true',
    mobileNavigationOpen: false,
    commandPaletteOpen: false,
    activeJobs: 0,
  }),
  actions: {
    hydrateAppearance() {
      this.applyTheme()
      document.documentElement.style.colorScheme = this.resolvedTheme
    },
    applyTheme() {
      this.resolvedTheme = resolveTheme(this.theme)
      document.documentElement.dataset.theme = this.resolvedTheme
      document.documentElement.style.colorScheme = this.resolvedTheme
    },
    setTheme(theme: ThemePreference) {
      this.theme = theme
      localStorage.setItem('brp.theme', theme)
      this.applyTheme()
    },
    cycleTheme() {
      const order: ThemePreference[] = ['system', 'light', 'dark']
      const index = order.indexOf(this.theme)
      this.setTheme(order[(index + 1) % order.length] ?? 'system')
    },
    setSidebarCollapsed(collapsed: boolean) {
      this.sidebarCollapsed = collapsed
      localStorage.setItem('brp.sidebarCollapsed', String(collapsed))
    },
    setCommandPaletteOpen(open: boolean) {
      this.commandPaletteOpen = open
    },
    setContext(workspaceId: string, siteId: string) {
      this.workspaceId = workspaceId
      this.siteId = siteId
      localStorage.setItem('brp.workspace', workspaceId)
      localStorage.setItem('brp.site', siteId)
    },
    setActor(actor: string) {
      this.actor = actor
      localStorage.setItem('brp.actor', actor)
    },
    setLocale(locale: 'en' | 'ko') {
      this.locale = locale
      localStorage.setItem('brp.locale', locale)
    },
  },
})
