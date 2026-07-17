<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { Activity, Boxes, Building2, ChevronDown, ClipboardCheck, FlaskConical, Gauge, GitPullRequest, Languages, Menu, Network, Search, UploadCloud, X } from '@lucide/vue'
import { BrpApi, type PlatformContext } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const route = useRoute()
const { t, locale } = useI18n()
const api = new BrpApi(store.apiBaseUrl)
const context = ref<PlatformContext | null>(null)
const contextError = ref('')
let timer: number | undefined

const navigation = computed(() => [
  { to: '/overview', label: t('nav.overview'), icon: Gauge },
  { to: '/decisions', label: t('nav.decisions'), icon: Boxes },
  { to: '/imports', label: t('nav.imports'), icon: UploadCloud },
  { to: '/reviews', label: t('nav.reviews'), icon: ClipboardCheck },
  { to: '/test-suites', label: t('nav.suites'), icon: FlaskConical },
  { to: '/releases', label: t('nav.releases'), icon: GitPullRequest },
  { to: '/sites', label: t('nav.sites'), icon: Building2 },
  { to: '/operations', label: t('nav.operations'), icon: Activity },
])
const currentLabel = computed(() => navigation.value.find((item) => item.to === route.path)?.label ?? '')
const sites = computed(() => context.value?.sites.filter((site) => !store.workspaceId || site.workspaceId === store.workspaceId) ?? [])

watch(locale, (value) => store.setLocale(value as 'en' | 'ko'))
watch(() => store.workspaceId, () => {
  if (!sites.value.some((site) => site.id === store.siteId) && sites.value[0]) store.setContext(store.workspaceId, sites.value[0].id)
})

onMounted(async () => {
  try {
    context.value = await api.context()
    const workspace = context.value.workspaces.find((item) => item.id === store.workspaceId) ?? context.value.workspaces[0]
    const site = context.value.sites.find((item) => item.id === store.siteId) ?? context.value.sites.find((item) => item.workspaceId === workspace?.id)
    if (workspace && site) store.setContext(workspace.id, site.id)
    await refreshJobs()
    timer = window.setInterval(refreshJobs, 5000)
  } catch (cause) {
    contextError.value = cause instanceof Error ? cause.message : 'Platform context is unavailable'
  }
})
onUnmounted(() => window.clearInterval(timer))

async function refreshJobs() {
  if (!store.siteId) return
  try {
    const jobs = await api.jobs(store.siteId)
    store.activeJobs = jobs.filter((job) => ['QUEUED', 'RUNNING'].includes(job.status)).length
  } catch { /* page-level operations view exposes details */ }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ open: store.mobileNavigationOpen }">
      <div class="brand"><span class="brand-symbol"><Network :size="20" /></span><div><strong>{{ t('app.name') }}</strong><small>Governance console</small></div><button class="icon-button mobile-only" aria-label="Close navigation" @click="store.mobileNavigationOpen = false"><X :size="18" /></button></div>
      <nav aria-label="Primary navigation">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" @click="store.mobileNavigationOpen = false"><component :is="item.icon" :size="17" /><span>{{ item.label }}</span></RouterLink>
      </nav>
      <div class="sidebar-foot"><span class="environment-dot"></span><div><strong>{{ t('app.environment') }}</strong><small>OIDC required before internet exposure</small></div></div>
    </aside>

    <div class="shell-main">
      <header class="command-bar">
        <button class="icon-button mobile-only" aria-label="Open navigation" @click="store.mobileNavigationOpen = true"><Menu :size="20" /></button>
        <div class="context-selectors">
          <label><span>Workspace</span><select v-model="store.workspaceId"><option v-for="workspace in context?.workspaces" :key="workspace.id" :value="workspace.id">{{ workspace.name }}</option></select><ChevronDown :size="14" /></label>
          <span class="context-separator">/</span>
          <label><span>Site</span><select v-model="store.siteId"><option v-for="site in sites" :key="site.id" :value="site.id">{{ site.name }}</option></select><ChevronDown :size="14" /></label>
        </div>
        <button class="command-search" type="button"><Search :size="16" /><span>Search decisions and jobs</span><kbd>⌘ K</kbd></button>
        <RouterLink class="job-indicator" to="/operations"><span :class="{ pulse: store.activeJobs }"></span>{{ store.activeJobs }} {{ t('app.jobs') }}</RouterLink>
        <label class="locale-picker"><Languages :size="16" /><select v-model="locale" aria-label="Language"><option value="en">EN</option><option value="ko">한국어</option></select></label>
        <label class="identity-picker" title="Authentication is intentionally deferred"><span>{{ t('app.developmentIdentity') }}</span><select :value="store.actor" @change="store.setActor(($event.target as HTMLSelectElement).value)"><option>maker-a</option><option>checker-b</option><option>reviewer-c</option><option>deployer-d</option></select></label>
      </header>

      <div v-if="contextError" class="global-alert" role="alert"><strong>Connection problem</strong><span>{{ contextError }}</span><button @click="$router.go(0)">Retry</button></div>
      <main class="page-frame"><div class="breadcrumbs"><span>Rule Platform</span><span>/</span><strong>{{ currentLabel }}</strong></div><RouterView :key="`${route.path}:${store.siteId}`" /></main>
    </div>
  </div>
</template>
