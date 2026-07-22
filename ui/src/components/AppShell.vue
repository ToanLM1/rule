<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  Activity,
  ArrowRight,
  Boxes,
  Building2,
  ChevronDown,
  ClipboardCheck,
  Command,
  FlaskConical,
  Gauge,
  GitPullRequest,
  Languages,
  Menu,
  Monitor,
  Moon,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  UploadCloud,
  X,
} from '@lucide/vue'
import { BrpApi, type PlatformContext } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const api = new BrpApi(store.apiBaseUrl)
const context = ref<PlatformContext | null>(null)
const contextError = ref('')
const commandQuery = ref('')
const commandInput = ref<HTMLInputElement | null>(null)
let timer: number | undefined
let systemTheme: MediaQueryList | undefined

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
const commandResults = computed(() => {
  const query = commandQuery.value.trim().toLocaleLowerCase()
  return query ? navigation.value.filter((item) => item.label.toLocaleLowerCase().includes(query)) : navigation.value
})
const themeIcon = computed(() => ({ system: Monitor, light: Sun, dark: Moon })[store.theme])
const themeLabel = computed(() => `Theme: ${store.theme}`)

watch(locale, (value) => store.setLocale(value as 'en' | 'ko'))
watch(
  () => store.workspaceId,
  () => {
    if (!sites.value.some((site) => site.id === store.siteId) && sites.value[0]) store.setContext(store.workspaceId, sites.value[0].id)
    else store.setContext(store.workspaceId, store.siteId)
  },
)
watch(
  () => store.siteId,
  (siteId) => store.setContext(store.workspaceId, siteId),
)
watch(
  () => route.fullPath,
  () => {
    store.mobileNavigationOpen = false
    closePalette()
  },
)

onMounted(async () => {
  window.addEventListener('keydown', handleKeyboard)
  systemTheme = window.matchMedia?.('(prefers-color-scheme: dark)')
  systemTheme?.addEventListener('change', handleSystemTheme)
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

onUnmounted(() => {
  window.clearInterval(timer)
  window.removeEventListener('keydown', handleKeyboard)
  systemTheme?.removeEventListener('change', handleSystemTheme)
})

function handleSystemTheme() {
  if (store.theme === 'system') store.applyTheme()
}

function handleKeyboard(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === 'k') {
    event.preventDefault()
    store.commandPaletteOpen ? closePalette() : openPalette()
  } else if (event.key === 'Escape' && store.commandPaletteOpen) closePalette()
}

function openPalette() {
  store.setCommandPaletteOpen(true)
  void nextTick(() => commandInput.value?.focus())
}

function closePalette() {
  store.setCommandPaletteOpen(false)
  commandQuery.value = ''
}

async function navigate(to: string) {
  await router.push(to)
  closePalette()
}

async function searchDecisions() {
  const query = commandQuery.value.trim()
  await router.push({ path: '/decisions', query: query ? { q: query } : {} })
  closePalette()
}

async function refreshJobs() {
  if (!store.siteId) return
  try {
    const jobs = await api.jobs(store.siteId)
    store.activeJobs = jobs.filter((job) => ['QUEUED', 'RUNNING'].includes(job.status)).length
  } catch {
    // The Operations page exposes request failures with actionable detail.
  }
}
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': store.sidebarCollapsed }">
    <button
      v-if="store.mobileNavigationOpen"
      class="navigation-scrim"
      aria-label="Close navigation"
      @click="store.mobileNavigationOpen = false"
    />
    <aside class="sidebar" :class="{ open: store.mobileNavigationOpen }">
      <div class="brand">
        <span class="brand-symbol"><Network :size="19" /></span>
        <div class="brand-copy"><strong>{{ t('app.name') }}</strong><small>{{ t('app.console') }}</small></div>
        <button class="icon-button mobile-only" aria-label="Close navigation" @click="store.mobileNavigationOpen = false"><X :size="18" /></button>
      </div>
      <nav aria-label="Primary navigation">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" :title="store.sidebarCollapsed ? item.label : undefined">
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <span class="environment-dot" />
        <div><strong>{{ t('app.environment') }}</strong><small>Protected governance boundary</small></div>
      </div>
      <button
        class="sidebar-collapse desktop-only"
        :aria-label="store.sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
        @click="store.setSidebarCollapsed(!store.sidebarCollapsed)"
      >
        <component :is="store.sidebarCollapsed ? PanelLeftOpen : PanelLeftClose" :size="16" />
        <span>{{ store.sidebarCollapsed ? 'Expand' : 'Collapse' }}</span>
      </button>
    </aside>

    <div class="shell-main">
      <header class="command-bar">
        <button class="icon-button mobile-only" aria-label="Open navigation" @click="store.mobileNavigationOpen = true"><Menu :size="20" /></button>
        <div class="context-selectors">
          <label>
            <span>Workspace</span>
            <select v-model="store.workspaceId" aria-label="Workspace"><option v-for="workspace in context?.workspaces" :key="workspace.id" :value="workspace.id">{{ workspace.name }}</option></select>
            <ChevronDown :size="14" />
          </label>
          <span class="context-separator">/</span>
          <label>
            <span>Site</span>
            <select v-model="store.siteId" aria-label="Site"><option v-for="site in sites" :key="site.id" :value="site.id">{{ site.name }}</option></select>
            <ChevronDown :size="14" />
          </label>
        </div>
        <button class="command-search" type="button" @click="openPalette"><Search :size="16" /><span>{{ t('app.search') }}</span><kbd>⌘ K</kbd></button>
        <RouterLink class="job-indicator" to="/operations"><span :class="{ pulse: store.activeJobs }" />{{ store.activeJobs }} {{ t('app.jobs') }}</RouterLink>
        <button class="icon-button theme-toggle" type="button" :title="themeLabel" :aria-label="themeLabel" @click="store.cycleTheme()"><component :is="themeIcon" :size="16" /></button>
        <label class="locale-picker"><Languages :size="16" /><select v-model="locale" aria-label="Language"><option value="en">EN</option><option value="ko">한국어</option></select></label>
        <label class="identity-picker" title="Authentication is intentionally deferred"><span>{{ t('app.developmentIdentity') }}</span><select :value="store.actor" @change="store.setActor(($event.target as HTMLSelectElement).value)"><option>maker-a</option><option>checker-b</option><option>reviewer-c</option><option>deployer-d</option></select></label>
      </header>

      <div v-if="contextError" class="global-alert" role="alert"><strong>Connection problem</strong><span>{{ contextError }}</span><button @click="$router.go(0)">Retry</button></div>
      <main class="page-frame">
        <div class="breadcrumbs"><span>Rule Platform</span><span>/</span><strong>{{ currentLabel }}</strong></div>
        <RouterView :key="`${route.path}:${store.siteId}`" />
      </main>
    </div>

    <Teleport to="body">
      <div v-if="store.commandPaletteOpen" class="command-palette-backdrop" @click.self="closePalette">
        <section class="command-palette" role="dialog" aria-modal="true" :aria-label="t('app.commandTitle')">
          <header>
            <span class="command-mark"><Command :size="18" /></span>
            <div><strong>{{ t('app.commandTitle') }}</strong><small>{{ t('app.commandHint') }}</small></div>
            <kbd>ESC</kbd>
          </header>
          <label class="command-input"><Search :size="18" /><input ref="commandInput" v-model="commandQuery" :placeholder="t('app.search')" @keydown.enter="searchDecisions" /></label>
          <div class="command-results">
            <p>Navigate</p>
            <button v-for="item in commandResults" :key="item.to" type="button" @click="navigate(item.to)">
              <span><component :is="item.icon" :size="17" />{{ item.label }}</span><ArrowRight :size="15" />
            </button>
            <button v-if="commandQuery.trim()" class="command-search-action" type="button" @click="searchDecisions">
              <span><Search :size="17" />Search decisions for “{{ commandQuery.trim() }}”</span><kbd>↵</kbd>
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>
