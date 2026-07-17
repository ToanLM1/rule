import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    apiBaseUrl: import.meta.env.VITE_BRP_API_BASE_URL ?? 'http://localhost:8100',
    workspaceId: localStorage.getItem('brp.workspace') ?? '',
    siteId: localStorage.getItem('brp.site') ?? '',
    actor: localStorage.getItem('brp.actor') ?? 'maker-a',
    locale: (localStorage.getItem('brp.locale') ?? 'en') as 'en' | 'ko',
    mobileNavigationOpen: false,
    activeJobs: 0,
  }),
  actions: {
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
