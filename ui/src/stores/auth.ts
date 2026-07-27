import { defineStore } from 'pinia'
import { BrpApi, setSessionCsrfToken, type AuthPrincipal } from '../api'
import { useAppStore } from './app'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    principal: null as AuthPrincipal | null,
    resolved: false,
  }),
  actions: {
    apply(principal: AuthPrincipal | null) {
      this.principal = principal
      setSessionCsrfToken(principal?.csrfToken ?? '')
      if (principal) useAppStore().setActor(principal.username)
    },
    async restore() {
      if (this.resolved) return
      const app = useAppStore()
      try {
        this.apply(await new BrpApi(app.apiBaseUrl).me())
      } catch {
        this.apply(null)
      } finally {
        this.resolved = true
      }
    },
    async login(username: string, password: string) {
      const app = useAppStore()
      this.apply(await new BrpApi(app.apiBaseUrl).login(username, password))
      this.resolved = true
    },
    async logout() {
      const app = useAppStore()
      try {
        await new BrpApi(app.apiBaseUrl).logout()
      } finally {
        this.apply(null)
        this.resolved = true
      }
    },
    expire() {
      this.apply(null)
      this.resolved = true
    },
  },
})
