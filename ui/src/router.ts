import { createRouter, createWebHistory } from 'vue-router'

import DecisionsPage from './pages/DecisionsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'decisions', component: DecisionsPage }],
})
