<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { FlaskConical, Play, Plus } from '@lucide/vue'
import { BrpApi, type DecisionSummary, type GoldenSuite, type LookupSnapshot } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const decisions = ref<DecisionSummary[]>([])
const decisionKey = ref('')
const suites = ref<GoldenSuite[]>([])
const snapshots = ref<LookupSnapshot[]>([])
const selectedSnapshots = ref<string[]>([])
const casesText = ref('[\n  {\n    "caseKey": "case-001",\n    "input": {},\n    "expected": {},\n    "provenance": {"source": "curated"}\n  }\n]')
const snapshotText = ref('{\n  "name": "region eligibility",\n  "rows": [{"region_code": "SEOUL", "eligible": true}],\n  "source": {"ref": "lookup://region_eligibility", "kind": "CURATED"}\n}')
const editing = ref(false)
const snapshotEditing = ref(false)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')

onMounted(async () => {
  try {
    const [page, loadedSnapshots] = await Promise.all([
      api.decisionPage(store.siteId, { pageSize: 100 }), api.lookupSnapshots(store.siteId),
    ])
    decisions.value = page.items
    snapshots.value = loadedSnapshots
    decisionKey.value = page.items[0]?.decisionKey ?? ''
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Evidence data unavailable' }
  finally { loading.value = false }
})
watch(decisionKey, loadSuites)

async function loadSuites() {
  if (!decisionKey.value) return
  loading.value = true
  try { suites.value = await api.goldenSuites(store.siteId, decisionKey.value) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Golden suites unavailable' }
  finally { loading.value = false }
}
async function createRevision() {
  let cases: Array<Record<string, unknown>>
  try { cases = JSON.parse(casesText.value); if (!Array.isArray(cases) || !cases.length) throw new Error() }
  catch { error.value = 'Cases must be a non-empty JSON array.'; return }
  busy.value = true
  try {
    await api.createGoldenSuite(store.siteId, decisionKey.value, cases, selectedSnapshots.value, store.actor)
    editing.value = false; notice.value = 'Golden suite revision created.'; await loadSuites()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Suite creation failed' }
  finally { busy.value = false }
}
async function createSnapshot() {
  let payload: Record<string, unknown>
  try { payload = JSON.parse(snapshotText.value) } catch { error.value = 'Lookup snapshot must be valid JSON.'; return }
  busy.value = true
  try {
    const snapshot = await api.createLookupSnapshot(store.siteId, payload, store.actor)
    snapshots.value.unshift(snapshot); selectedSnapshots.value.push(snapshot.contentHash)
    snapshotEditing.value = false; notice.value = 'Approved lookup snapshot captured.'
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Lookup snapshot creation failed' }
  finally { busy.value = false }
}
async function transition(suite: GoldenSuite, action: 'submit' | 'approve') {
  busy.value = true
  try { await api.transitionGoldenSuite(store.siteId, decisionKey.value, suite.revision, action, store.actor); notice.value = `Suite r${suite.revision} ${action}ted.`; await loadSuites() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Transition failed' }
  finally { busy.value = false }
}
async function run(suite: GoldenSuite) {
  const decision = decisions.value.find((item) => item.decisionKey === decisionKey.value)
  if (!decision) return
  busy.value = true
  try { const job = await api.runGoldenSuite(store.siteId, decisionKey.value, decision.latestRevision, suite.revision, store.actor); notice.value = `Golden run queued: ${job.id}` }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Run submission failed' }
  finally { busy.value = false }
}
</script>

<template>
  <section>
    <header class="page-header"><div><p class="page-kicker">Release evidence</p><h1>Test suites</h1><p>Versioned golden cases, approved lookup snapshots and asynchronous execution evidence.</p></div><button class="primary-button" :disabled="!decisionKey" @click="editing=!editing"><Plus :size="15"/>New suite revision</button></header>
    <div v-if="error" class="inline-alert" role="alert">{{ error }}</div><div v-if="notice" class="success-alert" role="status">{{ notice }}</div>
    <section class="surface suite-controls"><label>Governed decision<select v-model="decisionKey"><option v-for="decision in decisions" :key="decision.decisionKey" :value="decision.decisionKey">{{ decision.name }} · r{{ decision.latestRevision }}</option></select></label></section>
    <section v-if="editing" class="surface editor-panel"><h2>Golden cases</h2><p>Record exact input, expected output and provenance. Attach every lookup snapshot needed for deterministic execution.</p><textarea v-model="casesText" aria-label="Golden cases JSON" spellcheck="false"/><h3>Approved lookup evidence</h3><div class="snapshot-list"><label v-for="snapshot in snapshots" :key="snapshot.id"><input v-model="selectedSnapshots" type="checkbox" :value="snapshot.contentHash"/><span><strong>{{ snapshot.name }}</strong><small>{{ snapshot.rowCount }} rows · {{ snapshot.contentHash.slice(0,12) }}</small></span></label><button class="secondary-button" @click="snapshotEditing=!snapshotEditing">{{ snapshotEditing?'Cancel snapshot':'Add lookup snapshot' }}</button></div><div v-if="snapshotEditing" class="snapshot-editor"><textarea v-model="snapshotText" aria-label="Lookup snapshot JSON" spellcheck="false"/><button class="secondary-button" :disabled="busy" @click="createSnapshot">Capture and attest snapshot</button></div><div><button class="secondary-button" @click="editing=false">Cancel</button><button class="primary-button" :disabled="busy" @click="createRevision">Create immutable revision</button></div></section>
    <section class="surface table-surface section-gap"><div v-if="loading" class="skeleton-list"><span v-for="n in 4" :key="n"/></div><div v-else-if="!suites.length" class="empty-state tall"><FlaskConical :size="36"/><strong>No golden evidence for this decision</strong><span>Create cases, submit them for independent approval, then run them asynchronously.</span></div><div v-else class="responsive-table"><table><thead><tr><th>Revision</th><th>Status</th><th>Cases</th><th>Evidence hash</th><th>Created</th><th>Actions</th></tr></thead><tbody><tr v-for="suite in suites" :key="suite.id"><td><strong>r{{ suite.revision }}</strong></td><td><span class="status-badge" :class="suite.status.toLowerCase()">{{ suite.status }}</span></td><td>{{ suite.caseCount }}</td><td><code>{{ suite.contentHash.slice(0,12) }}</code></td><td>{{ new Date(suite.createdAt).toLocaleString() }}<small>{{ suite.createdBy }}</small></td><td><div class="row-actions"><button v-if="suite.status==='DRAFT'" class="secondary-button" :disabled="busy" @click="transition(suite,'submit')">Submit</button><button v-if="suite.status==='SUBMITTED'" class="secondary-button" :disabled="busy" @click="transition(suite,'approve')">Approve</button><button class="primary-button" :disabled="busy" @click="run(suite)"><Play :size="13"/>Run</button></div></td></tr></tbody></table></div></section>
  </section>
</template>
