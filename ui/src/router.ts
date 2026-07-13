import { createRouter, createWebHistory } from 'vue-router'

import DecisionsPage from './pages/DecisionsPage.vue'
import OrchestrationPage from './pages/OrchestrationPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'decisions', component: DecisionsPage },
    { path: '/orchestration', name: 'orchestration', component: OrchestrationPage },
  ],
})
