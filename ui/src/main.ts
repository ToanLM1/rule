import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/outfit'
import './styles/tokens.css'
import './styles/base.css'
import './style.css'
import './styles/polish.css'
import './styles/workflow.css'
import './styles/motion.css'
import './styles/guide.css'
import './styles/docs.css'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import { useAppStore } from './stores/app'
import { useAuthStore } from './stores/auth'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia).use(i18n).use(router)
useAppStore(pinia).hydrateAppearance()
const auth = useAuthStore(pinia)
router.beforeEach(async (to) => {
  if (to.meta.public) return true
  await auth.restore()
  if (!auth.principal) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})
window.addEventListener('brp:unauthorized', () => {
  auth.expire()
  if (router.currentRoute.value.name !== 'login') {
    void router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})
app.mount('#app')
