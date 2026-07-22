import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/outfit'
import './styles/tokens.css'
import './styles/base.css'
import './style.css'
import './styles/polish.css'
import './styles/motion.css'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import { useAppStore } from './stores/app'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia).use(i18n).use(router)
useAppStore(pinia).hydrateAppearance()
app.mount('#app')
