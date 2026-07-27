<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  PhArrowClockwise,
  PhMagnifyingGlass,
  PhProhibit,
  PhPulse,
  PhWarningCircle,
  PhX,
} from '@phosphor-icons/vue'

import { BrpApi, type ImportRun, type JobRecord } from '../api'
import { showsEmptyState, consolidateErrors, useRequestState } from '../composables/requestState'
import { classifyJob, linkedImport, redactedDetail, stageTimeline } from '../domain/jobDiagnostics'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const route = useRoute()
const api = new BrpApi(store.apiBaseUrl)

const jobs = useRequestState<JobRecord[]>([], { fallbackMessage: 'Jobs unavailable' })
const runs = useRequestState<ImportRun[]>([], { isEmpty: () => false, fallbackMessage: 'Import history unavailable' })
const statusFilter = ref(typeof route.query.status === 'string' ? route.query.status : '')
const selectedId = ref('')
let timer: number | undefined

const alert = computed(() =>
  consolidateErrors([
    { label: 'Jobs', message: jobs.error.value },
    { label: 'Import history', message: runs.error.value },
  ]),
)
const visible = computed(() =>
  statusFilter.value ? jobs.data.value.filter((job) => job.status === statusFilter.value) : jobs.data.value,
)
const selected = computed(() => jobs.data.value.find((job) => job.id === selectedId.value) ?? null)
const diagnosis = computed(() => (selected.value ? classifyJob(selected.value) : null))
const timeline = computed(() => (selected.value ? stageTimeline(selected.value) : []))
const detail = computed(() => (selected.value ? redactedDetail(selected.value) : ''))
const relatedImport = computed(() => (selected.value ? linkedImport(selected.value, runs.data.value) : null))
const evidence = computed(() => {
  const result = selected.value?.result
  return result ? Object.entries(result) : []
})

onMounted(() => {
  void load()
  timer = window.setInterval(load, 4000)
})
onUnmounted(() => clearInterval(timer))
watch(() => route.query.status, (value) => (statusFilter.value = typeof value === 'string' ? value : ''))

async function load() {
  if (!store.siteId) return
  await Promise.all([jobs.run(() => api.jobs(store.siteId)), runs.run(() => api.importRuns(store.siteId))])
}
async function cancel(job: JobRecord) {
  await api.cancelJob(store.siteId, job.id, store.actor)
  await load()
}
function statusCount(status: string) {
  return jobs.trusted.value ? jobs.data.value.filter((job) => job.status === status).length : null
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime control</p>
        <h1>Operations</h1>
        <p>Durable jobs, retries, correlation IDs and worker progress.</p>
      </div>
      <div class="header-actions">
        <label class="header-select">
          Status
          <select v-model="statusFilter" aria-label="Filter jobs by status">
            <option value="">All</option>
            <option v-for="status in ['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED']" :key="status" :value="status">
              {{ status }}<template v-if="statusCount(status) !== null"> ({{ statusCount(status) }})</template>
            </option>
          </select>
        </label>
        <button class="secondary-button" @click="load"><PhArrowClockwise :size="15" />Refresh</button>
      </div>
    </header>

    <div v-if="alert" class="inline-alert" role="alert">{{ alert }} <button @click="load">Retry</button></div>

    <section class="surface table-surface">
      <div v-if="jobs.phase.value === 'loading' || jobs.phase.value === 'idle'" class="skeleton-list">
        <span v-for="n in 5" :key="n" />
      </div>
      <div v-else-if="jobs.failed.value" class="empty-state">
        <PhWarningCircle :size="32" /><strong>Job records unavailable</strong>
        <span>{{ jobs.error.value }} — this is not a claim that the site has no jobs.</span>
      </div>
      <div v-else-if="showsEmptyState(jobs.phase.value)" class="empty-state">
        <PhPulse :size="32" /><strong>No jobs for this site</strong>
      </div>
      <div v-else-if="!visible.length" class="empty-state">
        <PhPulse :size="32" /><strong>No {{ statusFilter.toLowerCase() }} jobs</strong>
        <span>Clear the status filter to see all durable jobs.</span>
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead>
            <tr><th>Job</th><th>Status</th><th>Progress</th><th>Attempts</th><th>Correlation ID</th><th>Submitted</th><th>Actions</th></tr>
          </thead>
          <tbody>
            <tr v-for="job in visible" :key="job.id" :class="{ selected: job.id === selectedId }">
              <td><strong>{{ job.type.replaceAll('_', ' ') }}</strong><small>{{ job.createdBy }}</small></td>
              <td><span class="status-badge" :class="job.status.toLowerCase()">{{ job.status }}</span></td>
              <td><div class="progress-cell"><progress :value="job.progress" max="100" /><span>{{ job.progress }}%</span></div></td>
              <td>{{ job.attempts }} / {{ job.maxAttempts }}</td>
              <td><code>{{ job.correlationId.slice(0, 12) }}</code></td>
              <td>{{ new Date(job.createdAt).toLocaleString() }}</td>
              <td>
                <div class="row-actions">
                  <button class="secondary-button" :aria-label="`Open job detail for ${job.type}`" @click="selectedId = job.id">
                    <PhMagnifyingGlass :size="13" />Detail
                  </button>
                  <button
                    v-if="['QUEUED', 'RUNNING'].includes(job.status)"
                    class="icon-button"
                    aria-label="Cancel job"
                    @click="cancel(job)"
                  >
                    <PhProhibit :size="15" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <aside v-if="selected && diagnosis" class="job-detail" role="dialog" aria-label="Job detail" aria-modal="false">
      <header>
        <div>
          <p class="page-kicker">{{ selected.type.replaceAll('_', ' ') }}</p>
          <h2>{{ diagnosis.title }}</h2>
        </div>
        <button class="icon-button" aria-label="Close job detail" @click="selectedId = ''"><PhX :size="16" /></button>
      </header>

      <dl class="job-identity">
        <div><dt>Job ID</dt><dd><code>{{ selected.id }}</code></dd></div>
        <div><dt>Correlation ID</dt><dd><code>{{ selected.correlationId }}</code></dd></div>
        <div><dt>Status</dt><dd><span class="status-badge" :class="selected.status.toLowerCase()">{{ selected.status }}</span></dd></div>
        <div><dt>Attempts</dt><dd>{{ selected.attempts }} of {{ selected.maxAttempts }}</dd></div>
        <div><dt>Submitted by</dt><dd>{{ selected.createdBy }}</dd></div>
        <div><dt>Failure class</dt><dd>{{ diagnosis.failureClass }}</dd></div>
      </dl>

      <section>
        <h3>Stage timeline</h3>
        <ol class="job-timeline">
          <li v-for="entry in timeline" :key="entry.stage" :class="entry.state">
            <strong>{{ entry.stage }}</strong>
            <small>{{ entry.at ? new Date(entry.at).toLocaleString() : 'not reached' }}</small>
          </li>
        </ol>
      </section>

      <section v-if="selected.errorCode || detail">
        <h3>Terminal reason</h3>
        <p v-if="selected.errorCode"><code>{{ selected.errorCode }}</code></p>
        <pre v-if="detail" class="job-error">{{ detail }}</pre>
        <p class="job-note">Tokens and credentials are redacted before display.</p>
      </section>

      <section>
        <h3>Retry classification</h3>
        <p>{{ diagnosis.nextAction }}</p>
        <p v-if="!diagnosis.retryable" class="job-note">{{ diagnosis.retryBlockedReason }}</p>
      </section>

      <section v-if="evidence.length">
        <h3>Produced evidence</h3>
        <dl class="job-identity">
          <div v-for="[key, value] in evidence" :key="key"><dt>{{ key }}</dt><dd><code>{{ String(value) }}</code></dd></div>
        </dl>
      </section>

      <section v-if="relatedImport">
        <h3>Affected governed change</h3>
        <p>
          <strong>{{ relatedImport.sourceName }}</strong> · {{ relatedImport.adapter }} ·
          pinned <code>{{ relatedImport.sourceRevision }}</code>
        </p>
        <RouterLink class="secondary-button" to="/imports">Open the preserved import configuration</RouterLink>
      </section>
      <p v-else class="job-note">
        This job is not linked to an import run, so no preserved source configuration is available.
      </p>
    </aside>
  </section>
</template>
