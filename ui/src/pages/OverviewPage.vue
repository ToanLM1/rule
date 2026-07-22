<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, AlertTriangle, ArrowRight, Boxes, CheckCircle2, ClipboardCheck, GitPullRequest, TestTube2, UploadCloud } from '@lucide/vue'
import { BrpApi, type ImportRun, type JobRecord } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const metrics = ref({ decisions: 0, openReviews: 0, activeJobs: 0, failedJobs: 0 })
const jobs = ref<JobRecord[]>([])
const imports = ref<ImportRun[]>([])
const loading = ref(true)
const error = ref('')

const cards = computed(() => [
  { label: 'Governed decisions', value: metrics.value.decisions, icon: Boxes, tone: 'blue', detail: 'Immutable revisions in this site' },
  { label: 'Awaiting review', value: metrics.value.openReviews, icon: ClipboardCheck, tone: 'amber', detail: 'Items requiring an independent actor' },
  { label: 'Active jobs', value: metrics.value.activeJobs, icon: Activity, tone: 'green', detail: 'Queued or currently running' },
  { label: 'Failed jobs', value: metrics.value.failedJobs, icon: AlertTriangle, tone: 'red', detail: 'Runs requiring investigation' },
])

onMounted(async () => {
  try {
    ;[metrics.value, jobs.value, imports.value] = await Promise.all([
      api.overview(store.siteId),
      api.jobs(store.siteId),
      api.importRuns(store.siteId),
    ])
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Overview unavailable'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="enterprise-overview">
    <header class="page-header overview-header">
      <div>
        <p class="page-kicker">Governance control plane</p>
        <h1>Overview</h1>
        <p>Operational health and governed workflow activity for the selected site.</p>
      </div>
      <div class="header-actions">
        <RouterLink class="secondary-button" to="/reviews">Open review queue</RouterLink>
        <RouterLink class="primary-button" to="/imports"><UploadCloud :size="16" />New import</RouterLink>
      </div>
    </header>

    <div v-if="error" class="inline-alert" role="alert">{{ error }} <button @click="$router.go(0)">Retry</button></div>

    <div class="metric-grid" :aria-busy="loading">
      <article v-for="card in cards" :key="card.label" class="metric-card">
        <span :class="['metric-icon', card.tone]"><component :is="card.icon" :size="17" /></span>
        <div class="metric-copy"><span>{{ card.label }}</span><strong>{{ loading ? '—' : card.value.toLocaleString() }}</strong><small>{{ card.detail }}</small></div>
      </article>
    </div>

    <section class="surface workflow-strip">
      <header class="surface-header">
        <div><h2>Governance workflow</h2><p>Every change follows the same controlled path.</p></div>
      </header>
      <div class="workflow-stages">
        <RouterLink to="/imports"><span>01</span><UploadCloud :size="17" /><div><strong>Import</strong><small>Pin and validate source</small></div><ArrowRight :size="14" /></RouterLink>
        <RouterLink to="/reviews"><span>02</span><ClipboardCheck :size="17" /><div><strong>Review</strong><small>Enforce maker-checker</small></div><ArrowRight :size="14" /></RouterLink>
        <RouterLink to="/test-suites"><span>03</span><TestTube2 :size="17" /><div><strong>Test</strong><small>Capture golden evidence</small></div><ArrowRight :size="14" /></RouterLink>
        <RouterLink to="/releases"><span>04</span><GitPullRequest :size="17" /><div><strong>Release</strong><small>Deliver pinned artifacts</small></div><ArrowRight :size="14" /></RouterLink>
      </div>
    </section>

    <div class="dashboard-grid section-gap">
      <section class="surface">
        <header class="surface-header"><div><h2>Recent workflow activity</h2><p>Durable jobs across import, tests and releases</p></div><RouterLink to="/operations">View operations <ArrowRight :size="14" /></RouterLink></header>
        <div v-if="!jobs.length" class="empty-state"><Activity :size="26" /><strong>No job activity</strong><span>Jobs will appear here when workflows are submitted.</span></div>
        <div v-else class="data-list"><article v-for="job in jobs.slice(0, 6)" :key="job.id"><span :class="['status-dot', job.status.toLowerCase()]" /><div><strong>{{ job.type.replaceAll('_', ' ') }}</strong><small>{{ job.createdBy }} · {{ new Date(job.createdAt).toLocaleString() }}</small></div><span class="status-badge">{{ job.status }}</span><progress :value="job.progress" max="100" /></article></div>
      </section>
      <section class="surface">
        <header class="surface-header"><div><h2>Latest imports</h2><p>Sources entering governance</p></div><RouterLink to="/imports">Open imports <ArrowRight :size="14" /></RouterLink></header>
        <div v-if="!imports.length" class="empty-state"><UploadCloud :size="26" /><strong>No imports yet</strong><span>Start with a supported source profile.</span></div>
        <div v-else class="compact-list"><article v-for="run in imports.slice(0, 6)" :key="run.id"><div><strong>{{ run.sourceName }}</strong><small>{{ run.adapter }} · {{ run.sourceRevision }}</small></div><span class="status-badge">{{ run.status }}</span></article></div>
      </section>
    </div>

    <section v-if="!loading && !error && metrics.failedJobs === 0" class="overview-health" aria-label="Platform health">
      <CheckCircle2 :size="17" /><span><strong>No failed jobs.</strong> The current operational view has no workflow failures requiring action.</span>
    </section>
  </section>
</template>
