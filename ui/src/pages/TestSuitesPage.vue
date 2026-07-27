<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { PhFlask, PhPlay, PhPlus, PhWarningCircle } from '@phosphor-icons/vue'

import { BrpApi, type DecisionSummary, type GoldenSuite, type LookupSnapshot } from '../api'
import DecisionPicker from '../components/DecisionPicker.vue'
import { useGovernedChange } from '../composables/governedChange'
import { consolidateErrors, showsEmptyState, useRequestState } from '../composables/requestState'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const { decisionKey, selectDecision, linkWithDecision } = useGovernedChange()

const suites = useRequestState<GoldenSuite[]>([], { fallbackMessage: 'Golden suites unavailable' })
const snapshots = useRequestState<LookupSnapshot[]>([], { fallbackMessage: 'Lookup snapshots unavailable' })
const selectedDecision = useRequestState<DecisionSummary | null>(null, {
  isEmpty: () => false,
  fallbackMessage: 'Decision identity unavailable',
})
const mutation = useRequestState<string>('', { isEmpty: () => false, fallbackMessage: 'Request failed' })

const selectedSnapshots = ref<string[]>([])
const casesText = ref('[\n  {\n    "caseKey": "case-001",\n    "input": {},\n    "expected": {},\n    "provenance": {"source": "curated"}\n  }\n]')
const snapshotText = ref('{\n  "name": "region eligibility",\n  "rows": [{"region_code": "SEOUL", "eligible": true}],\n  "source": {"ref": "lookup://region_eligibility", "kind": "CURATED"}\n}')
const editing = ref(false)
const snapshotEditing = ref(false)
const localError = ref('')

const busy = computed(() => mutation.phase.value === 'loading')
const notice = computed(() => (mutation.phase.value === 'ready' ? mutation.data.value : ''))
const alert = computed(() =>
  consolidateErrors([
    { label: 'Golden suites', message: suites.error.value },
    { label: 'Lookup snapshots', message: snapshots.error.value },
    { label: 'Decision identity', message: selectedDecision.error.value },
    { label: 'Last action', message: mutation.error.value },
    { label: 'Input', message: localError.value },
  ]),
)

onMounted(async () => {
  await Promise.all([snapshots.run(() => api.lookupSnapshots(store.siteId)), ensureDecision()])
  await loadSuites()
})
watch(decisionKey, async () => {
  await ensureDecision()
  await loadSuites()
})

async function ensureDecision() {
  if (decisionKey.value) {
    await selectedDecision.run(async () => {
      const page = await api.decisionPage(store.siteId, { q: decisionKey.value, pageSize: 10 })
      return page.items.find((item) => item.decisionKey === decisionKey.value) ?? null
    })
    return
  }
  const page = await api.decisionPage(store.siteId, { pageSize: 1 }).catch(() => null)
  const first = page?.items[0]
  if (first) await selectDecision(first.decisionKey)
}

async function loadSuites() {
  if (!decisionKey.value) {
    suites.reset()
    return
  }
  await suites.run(() => api.goldenSuites(store.siteId, decisionKey.value))
}

async function createRevision() {
  localError.value = ''
  let cases: Array<Record<string, unknown>>
  try {
    cases = JSON.parse(casesText.value)
    if (!Array.isArray(cases) || !cases.length) throw new Error()
  } catch {
    localError.value = 'Cases must be a non-empty JSON array.'
    return
  }
  await mutation.run(async () => {
    await api.createGoldenSuite(store.siteId, decisionKey.value, cases, selectedSnapshots.value, store.actor)
    editing.value = false
    await loadSuites()
    return 'Golden suite revision created.'
  })
}

async function createSnapshot() {
  localError.value = ''
  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(snapshotText.value)
  } catch {
    localError.value = 'Lookup snapshot must be valid JSON.'
    return
  }
  await mutation.run(async () => {
    const snapshot = await api.createLookupSnapshot(store.siteId, payload, store.actor)
    snapshots.data.value = [snapshot, ...snapshots.data.value]
    selectedSnapshots.value.push(snapshot.contentHash)
    snapshotEditing.value = false
    return 'Approved lookup snapshot captured.'
  })
}

async function transition(suite: GoldenSuite, action: 'submit' | 'approve') {
  await mutation.run(async () => {
    await api.transitionGoldenSuite(store.siteId, decisionKey.value, suite.revision, action, store.actor)
    await loadSuites()
    return `Suite r${suite.revision} ${action}ted.`
  })
}

async function run(suite: GoldenSuite) {
  const decision = selectedDecision.data.value
  if (!decision) {
    localError.value = 'The selected decision identity could not be resolved, so no run was submitted.'
    return
  }
  await mutation.run(async () => {
    const job = await api.runGoldenSuite(
      store.siteId,
      decisionKey.value,
      decision.latestRevision,
      suite.revision,
      store.actor,
    )
    return `Golden run queued: ${job.id}`
  })
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Release evidence · step 4</p>
        <h1>Test suites</h1>
        <p>Versioned golden cases, approved lookup snapshots and asynchronous execution evidence.</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" :disabled="!decisionKey" @click="editing = !editing">
          <PhPlus :size="15" />New suite revision
        </button>
        <RouterLink class="primary-button" :to="linkWithDecision('/releases')">Next: Releases →</RouterLink>
      </div>
    </header>

    <div v-if="alert" class="inline-alert" role="alert">{{ alert }}</div>
    <div v-if="notice" class="success-alert" role="status">{{ notice }}</div>

    <section class="surface suite-controls">
      <DecisionPicker label="Governed decision" :model-value="decisionKey" @update:model-value="selectDecision" />
    </section>

    <section v-if="editing" class="surface editor-panel">
      <h2>Golden cases</h2>
      <p>Record exact input, expected output and provenance. Attach every lookup snapshot needed for deterministic execution.</p>
      <textarea v-model="casesText" aria-label="Golden cases JSON" spellcheck="false" />
      <h3>Approved lookup evidence</h3>
      <div class="snapshot-list">
        <label v-for="snapshot in snapshots.data.value" :key="snapshot.id">
          <input v-model="selectedSnapshots" type="checkbox" :value="snapshot.contentHash" />
          <span><strong>{{ snapshot.name }}</strong><small>{{ snapshot.rowCount }} rows · {{ snapshot.contentHash.slice(0, 12) }}</small></span>
        </label>
        <button class="secondary-button" @click="snapshotEditing = !snapshotEditing">
          {{ snapshotEditing ? 'Cancel snapshot' : 'Add lookup snapshot' }}
        </button>
      </div>
      <div v-if="snapshotEditing" class="snapshot-editor">
        <textarea v-model="snapshotText" aria-label="Lookup snapshot JSON" spellcheck="false" />
        <button class="secondary-button" :disabled="busy" @click="createSnapshot">Capture and attest snapshot</button>
      </div>
      <div>
        <button class="secondary-button" @click="editing = false">Cancel</button>
        <button class="primary-button" :disabled="busy" @click="createRevision">Create immutable revision</button>
      </div>
    </section>

    <section class="surface table-surface section-gap">
      <div v-if="suites.phase.value === 'loading' || suites.phase.value === 'idle'" class="skeleton-list">
        <span v-for="n in 4" :key="n" />
      </div>
      <div v-else-if="suites.failed.value" class="empty-state tall">
        <PhWarningCircle :size="36" /><strong>Golden evidence unavailable</strong>
        <span>{{ suites.error.value }} — this is not a claim that the decision has no evidence.</span>
        <button class="secondary-button" @click="loadSuites">Retry</button>
      </div>
      <div v-else-if="showsEmptyState(suites.phase.value)" class="empty-state tall">
        <PhFlask :size="36" /><strong>No golden evidence for this decision</strong>
        <span>Create cases, submit them for independent approval, then run them asynchronously.</span>
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead><tr><th>Revision</th><th>Status</th><th>Cases</th><th>Evidence hash</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>
            <tr v-for="suite in suites.data.value" :key="suite.id">
              <td><strong>r{{ suite.revision }}</strong></td>
              <td><span class="status-badge" :class="suite.status.toLowerCase()">{{ suite.status }}</span></td>
              <td>{{ suite.caseCount }}</td>
              <td><code>{{ suite.contentHash.slice(0, 12) }}</code></td>
              <td>{{ new Date(suite.createdAt).toLocaleString() }}<small>{{ suite.createdBy }}</small></td>
              <td>
                <div class="row-actions">
                  <button v-if="suite.status === 'DRAFT'" class="secondary-button" :disabled="busy" @click="transition(suite, 'submit')">Submit</button>
                  <button v-if="suite.status === 'SUBMITTED'" class="secondary-button" :disabled="busy" @click="transition(suite, 'approve')">Approve</button>
                  <button class="primary-button" :disabled="busy" @click="run(suite)"><PhPlay :size="13" />Run</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
