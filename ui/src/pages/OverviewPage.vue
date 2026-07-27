<script setup lang="ts">
import { computed, onMounted } from 'vue'
import {
  PhPulse,
  PhWarning,
  PhArrowRight,
  PhStack,
  PhCheckCircle,
  PhClipboardText,
  PhGitPullRequest,
  PhTestTube,
  PhCloudArrowUp,
  PhTreeStructure,
  PhWarningCircle,
} from '@phosphor-icons/vue'

import { BrpApi, type ImportRun, type JobRecord } from '../api'
import { useGovernedChange } from '../composables/governedChange'
import { consolidateErrors, showsEmptyState, truthfulCount, useRequestState } from '../composables/requestState'
import { useAppStore } from '../stores/app'

type Metrics = { decisions: number; openReviews: number; activeJobs: number; failedJobs: number }

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const { linkWithDecision } = useGovernedChange()

const metrics = useRequestState<Metrics | null>(null, { isEmpty: () => false, fallbackMessage: 'Overview metrics unavailable' })
const jobs = useRequestState<JobRecord[]>([], { fallbackMessage: 'Job activity unavailable' })
const imports = useRequestState<ImportRun[]>([], { fallbackMessage: 'Import history unavailable' })

/**
 * B-007: a failed request renders as explicitly unavailable. It never becomes `0`,
 * "No imports yet", or a "no failed jobs" health claim.
 */
const cards = computed(() => [
  {
    label: 'Governed decisions',
    value: truthfulCount(metrics.phase.value, metrics.data.value?.decisions),
    icon: PhStack,
    tone: 'blue',
    detail: 'Immutable revisions in this site',
  },
  {
    label: 'Awaiting review',
    value: truthfulCount(metrics.phase.value, metrics.data.value?.openReviews),
    icon: PhClipboardText,
    tone: 'amber',
    detail: 'Items requiring an independent actor',
  },
  {
    label: 'Active jobs',
    value: truthfulCount(metrics.phase.value, metrics.data.value?.activeJobs),
    icon: PhPulse,
    tone: 'green',
    detail: 'Queued or currently running',
  },
  {
    label: 'Failed jobs',
    value: truthfulCount(metrics.phase.value, metrics.data.value?.failedJobs),
    icon: PhWarning,
    tone: 'red',
    detail: 'Runs requiring investigation',
  },
])

const alert = computed(() =>
  consolidateErrors([
    { label: 'Site metrics', message: metrics.error.value },
    { label: 'Job activity', message: jobs.error.value },
    { label: 'Import history', message: imports.error.value },
  ]),
)

/** Workspace/site context missing means primary workflow actions cannot be trusted. */
const contextUnavailable = computed(() => !store.siteId)
const healthClaimAllowed = computed(() => metrics.trusted.value && metrics.data.value?.failedJobs === 0)
const failedJobCount = computed(() => (metrics.trusted.value ? metrics.data.value?.failedJobs ?? 0 : 0))

onMounted(load)

async function load() {
  if (!store.siteId) return
  await Promise.all([
    metrics.run(() => api.overview(store.siteId)),
    jobs.run(() => api.jobs(store.siteId)),
    imports.run(() => api.importRuns(store.siteId)),
  ])
}
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
        <RouterLink class="secondary-button" :to="linkWithDecision('/reviews')">Open review queue</RouterLink>
        <RouterLink class="primary-button" to="/imports"><PhCloudArrowUp :size="16" />New import</RouterLink>
      </div>
    </header>

    <div v-if="contextUnavailable" class="inline-alert" role="alert">
      No workspace/site context is available, so no site counts or workflow actions can be shown.
    </div>
    <div v-else-if="alert" class="inline-alert" role="alert">
      {{ alert }} <button @click="load">Retry</button>
    </div>

    <div class="metric-grid" :aria-busy="metrics.phase.value === 'loading'">
      <article v-for="card in cards" :key="card.label" class="metric-card">
        <span :class="['metric-icon', card.tone]"><component :is="card.icon" :size="17" /></span>
        <div class="metric-copy"><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.detail }}</small></div>
      </article>
    </div>

    <section class="surface workflow-strip">
      <header class="surface-header">
        <div><h2>Governance workflow</h2><p>Every change follows the same controlled path.</p></div>
      </header>
      <div class="workflow-stages">
        <RouterLink to="/imports"><span>01</span><PhCloudArrowUp :size="17" /><div><strong>Import</strong><small>Pin and validate source</small></div><PhArrowRight :size="14" /></RouterLink>
        <RouterLink :to="linkWithDecision('/reviews')"><span>02</span><PhClipboardText :size="17" /><div><strong>Review</strong><small>Enforce maker-checker</small></div><PhArrowRight :size="14" /></RouterLink>
        <RouterLink :to="linkWithDecision('/studio')"><span>03</span><PhTreeStructure :size="17" /><div><strong>Author</strong><small>Edit and approve rules</small></div><PhArrowRight :size="14" /></RouterLink>
        <RouterLink :to="linkWithDecision('/test-suites')"><span>04</span><PhTestTube :size="17" /><div><strong>Test</strong><small>Capture golden evidence</small></div><PhArrowRight :size="14" /></RouterLink>
        <RouterLink :to="linkWithDecision('/releases')"><span>05</span><PhGitPullRequest :size="17" /><div><strong>Release</strong><small>Deliver pinned artifacts</small></div><PhArrowRight :size="14" /></RouterLink>
      </div>
    </section>

    <div class="dashboard-grid section-gap">
      <section class="surface">
        <header class="surface-header">
          <div><h2>Recent workflow activity</h2><p>Durable jobs across import, tests and releases</p></div>
          <RouterLink to="/operations">View operations <PhArrowRight :size="14" /></RouterLink>
        </header>
        <div v-if="jobs.phase.value === 'loading' || jobs.phase.value === 'idle'" class="skeleton-list"><span v-for="n in 4" :key="n" /></div>
        <div v-else-if="jobs.failed.value" class="empty-state">
          <PhWarningCircle :size="26" /><strong>Job activity unavailable</strong><span>{{ jobs.error.value }}</span>
        </div>
        <div v-else-if="showsEmptyState(jobs.phase.value)" class="empty-state">
          <PhPulse :size="26" /><strong>No job activity</strong><span>Jobs will appear here when workflows are submitted.</span>
        </div>
        <div v-else class="data-list">
          <article v-for="job in jobs.data.value.slice(0, 6)" :key="job.id">
            <span :class="['status-dot', job.status.toLowerCase()]" />
            <div><strong>{{ job.type.replaceAll('_', ' ') }}</strong><small>{{ job.createdBy }} · {{ new Date(job.createdAt).toLocaleString() }}</small></div>
            <span class="status-badge">{{ job.status }}</span>
            <progress :value="job.progress" max="100" />
          </article>
        </div>
      </section>
      <section class="surface">
        <header class="surface-header">
          <div><h2>Latest imports</h2><p>Sources entering governance</p></div>
          <RouterLink to="/imports">Open imports <PhArrowRight :size="14" /></RouterLink>
        </header>
        <div v-if="imports.phase.value === 'loading' || imports.phase.value === 'idle'" class="skeleton-list"><span v-for="n in 4" :key="n" /></div>
        <div v-else-if="imports.failed.value" class="empty-state">
          <PhWarningCircle :size="26" /><strong>Import history unavailable</strong><span>{{ imports.error.value }}</span>
        </div>
        <div v-else-if="showsEmptyState(imports.phase.value)" class="empty-state">
          <PhCloudArrowUp :size="26" /><strong>No imports yet</strong><span>Start with a supported source profile.</span>
        </div>
        <div v-else class="compact-list">
          <article v-for="run in imports.data.value.slice(0, 6)" :key="run.id">
            <div><strong>{{ run.sourceName }}</strong><small>{{ run.adapter }} · {{ run.sourceRevision }}</small></div>
            <span class="status-badge">{{ run.status }}</span>
          </article>
        </div>
      </section>
    </div>

    <section v-if="failedJobCount" class="overview-health failing" aria-label="Platform health">
      <PhWarning :size="17" />
      <span>
        <strong>{{ failedJobCount }} failed job(s).</strong>
        Open the failure to see its stage, terminal reason and whether a retry is safe.
      </span>
      <RouterLink class="secondary-button" to="/operations?status=FAILED">Investigate failures</RouterLink>
    </section>
    <section v-else-if="healthClaimAllowed" class="overview-health" aria-label="Platform health">
      <PhCheckCircle :size="17" /><span><strong>No failed jobs.</strong> The current operational view has no workflow failures requiring action.</span>
    </section>
  </section>
</template>
