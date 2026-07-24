import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    { path: '/overview', name: 'overview', component: () => import('./pages/OverviewPage.vue') },
    { path: '/guide', name: 'guide', component: () => import('./pages/GuidePage.vue') },
    { path: '/decisions', name: 'decisions', component: () => import('./pages/DecisionsPage.vue') },
    { path: '/studio', name: 'studio', component: () => import('./pages/CanonicalStudioPage.vue') },
    { path: '/imports', name: 'imports', component: () => import('./pages/ImportsPage.vue') },
    { path: '/orchestration', redirect: '/imports' },
    { path: '/reviews', name: 'reviews', component: () => import('./pages/ReviewQueuePage.vue') },
    { path: '/test-suites', name: 'test-suites', component: () => import('./pages/TestSuitesPage.vue') },
    { path: '/releases', name: 'releases', component: () => import('./pages/ReleasesPage.vue') },
    { path: '/sites', name: 'sites', component: () => import('./pages/SitesPage.vue') },
    { path: '/operations', name: 'operations', component: () => import('./pages/OperationsPage.vue') },
  ],
})
