<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PhCircleNotch, PhClipboardText, PhWarningCircle } from '@phosphor-icons/vue'

import { BrpApi } from '../api'
import { useGovernedChange } from '../composables/governedChange'
import { consolidateErrors, showsEmptyState, useRequestState } from '../composables/requestState'
import { useAppStore } from '../stores/app'

type ReviewItem = Record<string, unknown> & {
  id: string
  adapter: string
  reasonCode: string
  rawFragment: string
  provenance: Record<string, unknown>
  status: string
  history: Array<Record<string, unknown>>
  createdAt: string
  importRunId: string | null
}

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const { linkWithDecision } = useGovernedChange()

const queue = useRequestState<ReviewItem[]>([], { fallbackMessage: 'Review queue unavailable' })
const mutation = useRequestState<string>('', { isEmpty: () => false, fallbackMessage: 'Disposition failed' })
/** B-103: the queue defaults to actionable OPEN work; history stays discoverable. */
const statusFilter = ref<'OPEN' | 'DEFERRED' | 'ACCEPTED' | 'REJECTED' | 'ALL'>('OPEN')
const selected = ref(new Set<string>())

const saving = computed(() => mutation.phase.value === 'loading')
const notice = computed(() => (mutation.phase.value === 'ready' ? mutation.data.value : ''))
const alert = computed(() =>
  consolidateErrors([
    { label: 'Review queue', message: queue.error.value },
    { label: 'Last disposition', message: mutation.error.value },
  ]),
)
const counts = computed(() => {
  if (!queue.trusted.value) return null
  const tally: Record<string, number> = { OPEN: 0, DEFERRED: 0, ACCEPTED: 0, REJECTED: 0 }
  for (const item of queue.data.value) tally[item.status] = (tally[item.status] ?? 0) + 1
  return tally
})
const visible = computed(() =>
  statusFilter.value === 'ALL' ? queue.data.value : queue.data.value.filter((item) => item.status === statusFilter.value),
)

onMounted(load)

async function load() {
  await queue.run(() => api.reviewItems(store.siteId) as Promise<ReviewItem[]>)
  selected.value = new Set()
}

async function dispose(status: 'ACCEPTED' | 'DEFERRED' | 'REJECTED') {
  const reason = status === 'ACCEPTED' ? undefined : window.prompt(`Reason for ${status.toLowerCase()}:`)?.trim()
  if (status !== 'ACCEPTED' && !reason) return
  const dispositions = [...selected.value].map((itemId) => ({ itemId, status, reason }))
  await mutation.run(async () => {
    await api.disposeReviews(store.siteId, dispositions, store.actor)
    await load()
    return `${dispositions.length} review item(s) updated.`
  })
}

function toggle(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function sourceOf(item: ReviewItem) {
  const provenance = item.provenance ?? {}
  const parts = [provenance.repository, provenance.path ?? provenance.file, provenance.revision]
    .filter((value) => typeof value === 'string' && value)
    .map(String)
  return parts.length ? parts.join(' · ') : 'No pinned source reference recorded'
}
function lastDisposition(item: ReviewItem) {
  const entry = item.history?.[item.history.length - 1]
  if (!entry) return ''
  const actor = typeof entry.actor === 'string' ? entry.actor : 'unknown actor'
  const reason = typeof entry.reason === 'string' && entry.reason ? ` — ${entry.reason}` : ''
  return `${actor}${reason}`
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Human disposition · step 2</p>
        <h1>Review queue</h1>
        <p>Resolve unmapped fragments and extraction diagnostics before promotion.</p>
      </div>
      <div class="header-actions">
        <label class="header-select">
          Show
          <select v-model="statusFilter" aria-label="Filter review items by disposition">
            <option value="OPEN">Open{{ counts ? ` (${counts.OPEN})` : '' }}</option>
            <option value="DEFERRED">Deferred{{ counts ? ` (${counts.DEFERRED})` : '' }}</option>
            <option value="ACCEPTED">Accepted{{ counts ? ` (${counts.ACCEPTED})` : '' }}</option>
            <option value="REJECTED">Rejected{{ counts ? ` (${counts.REJECTED})` : '' }}</option>
            <option value="ALL">All history</option>
          </select>
        </label>
        <RouterLink class="primary-button" :to="linkWithDecision('/studio')">Next: Author →</RouterLink>
      </div>
    </header>

    <div v-if="alert" class="inline-alert" role="alert">{{ alert }} <button @click="load">Retry</button></div>
    <div v-if="notice" class="success-alert" role="status">{{ notice }}</div>

    <section class="surface table-surface">
      <div class="table-toolbar">
        <span>{{ selected.size }} selected</span>
        <div>
          <PhCircleNotch v-if="saving" class="spin" :size="16" />
          <button class="secondary-button" :disabled="!selected.size || saving" @click="dispose('ACCEPTED')">Accept</button>
          <button class="secondary-button" :disabled="!selected.size || saving" @click="dispose('DEFERRED')">Defer</button>
          <button class="danger-button" :disabled="!selected.size || saving" @click="dispose('REJECTED')">Reject</button>
        </div>
      </div>

      <div v-if="queue.phase.value === 'loading' || queue.phase.value === 'idle'" class="skeleton-list">
        <span v-for="n in 6" :key="n" />
      </div>
      <div v-else-if="queue.failed.value" class="empty-state">
        <PhWarningCircle :size="32" /><strong>Review queue unavailable</strong>
        <span>{{ queue.error.value }} — the queue is not clear, its state is unknown.</span>
        <button class="secondary-button" @click="load">Retry</button>
      </div>
      <div v-else-if="showsEmptyState(queue.phase.value)" class="empty-state">
        <PhClipboardText :size="32" /><strong>Review queue is clear</strong>
        <span>Unmapped source fragments will appear here.</span>
      </div>
      <div v-else-if="!visible.length" class="empty-state">
        <PhClipboardText :size="32" /><strong>No {{ statusFilter.toLowerCase() }} items</strong>
        <span>Switch the filter to see the remaining disposition history.</span>
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead>
            <tr>
              <th><span class="sr-only">Select</span></th>
              <th>Reason</th>
              <th>Adapter</th>
              <th>Source evidence</th>
              <th>Source fragment</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in visible" :key="item.id">
              <td>
                <input
                  type="checkbox"
                  :aria-label="`Select ${item.reasonCode}`"
                  :disabled="item.status !== 'OPEN' && item.status !== 'DEFERRED'"
                  :checked="selected.has(item.id)"
                  @change="toggle(item.id)"
                />
              </td>
              <td><strong>{{ item.reasonCode }}</strong></td>
              <td>{{ item.adapter }}</td>
              <td><small>{{ sourceOf(item) }}</small></td>
              <td><code>{{ String(item.rawFragment).slice(0, 100) }}</code></td>
              <td>
                <span class="status-badge" :class="String(item.status).toLowerCase()">{{ item.status }}</span>
                <small v-if="lastDisposition(item)">{{ lastDisposition(item) }}</small>
              </td>
              <td>{{ new Date(item.createdAt).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
