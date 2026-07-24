<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { PhArrowSquareOut, PhGitBranch, PhPackage, PhArrowCounterClockwise } from '@phosphor-icons/vue'
import { BrpApi, type DecisionSummary, type GoldenSuite, type ModeAPublication, type ModeBDelivery, type Revision, type SiteProfile } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const decisions = ref<DecisionSummary[]>([])
const decisionKey = ref('')
const suites = ref<GoldenSuite[]>([])
const profiles = ref<SiteProfile[]>([])
const modeA = ref<ModeAPublication[]>([])
const modeB = ref<ModeBDelivery[]>([])
const approvedRevision = ref<Revision | null>(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')

onMounted(async () => {
  try {
    const [page, siteProfiles, deliveries] = await Promise.all([api.decisionPage(store.siteId, { pageSize: 100 }), api.siteProfiles(store.siteId), api.modeBHistory(store.siteId)])
    decisions.value = page.items; profiles.value = siteProfiles; modeB.value = deliveries; decisionKey.value = page.items[0]?.decisionKey ?? ''
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Release data unavailable' }
})
watch(decisionKey, async () => {
  if (!decisionKey.value) return
  try { const [loadedSuites, publications, revisions] = await Promise.all([api.goldenSuites(store.siteId, decisionKey.value), api.modeAHistory(store.siteId, decisionKey.value), api.decisionRevisions(store.siteId, decisionKey.value)]); suites.value = loadedSuites; modeA.value = publications; approvedRevision.value = revisions.find((item) => item.envelope.lifecycleStatus === 'APPROVED') ?? null }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Release evidence unavailable' }
})
function chosen() { return decisions.value.find((item) => item.decisionKey === decisionKey.value) }
function approvedSuite() { return suites.value.find((item) => item.status === 'APPROVED') }
async function publish() {
  const decision = approvedRevision.value; const suite = approvedSuite(); if (!decision || !suite) { error.value = 'An approved decision revision and golden suite are required.'; return }
  busy.value = true
  try { const job = await api.publishModeA(store.siteId, decisionKey.value, decision.envelope.revision, suite.revision, store.actor); notice.value = `Mode-A publication queued: ${job.id}` }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Publication failed' }
  finally { busy.value = false }
}
async function rollback(publication: ModeAPublication) {
  if (!window.confirm(`Rollback ${decisionKey.value} to publication ${publication.id}?`)) return
  busy.value = true
  try { const job = await api.rollbackModeA(store.siteId, decisionKey.value, publication.id, store.actor); notice.value = `Rollback queued: ${job.id}` }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Rollback failed' }
  finally { busy.value = false }
}
async function deliver() {
  const decision = approvedRevision.value; const profile = profiles.value.find((item) => item.document.deliveryMode === 'B'); if (!decision || !profile) { error.value = 'An approved decision revision and Mode-B site profile are required.'; return }
  busy.value = true
  try { const job = await api.deliverModeB(store.siteId, decisionKey.value, decision.envelope.revision, profile.revision, store.actor); notice.value = `Mode-B delivery queued: ${job.id}` }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Delivery failed' }
  finally { busy.value = false }
}
</script>

<template><section><header class="page-header"><div><p class="page-kicker">Controlled delivery</p><h1>Releases</h1><p>Mode-A publications and Mode-B Git delivery with immutable artifact evidence.</p></div><label class="header-select">Decision<select v-model="decisionKey"><option v-for="decision in decisions" :key="decision.decisionKey" :value="decision.decisionKey">{{ decision.name }} · r{{ decision.latestRevision }}</option></select></label></header><div v-if="error" class="inline-alert" role="alert">{{ error }}</div><div v-if="notice" class="success-alert" role="status">{{ notice }} <RouterLink to="/operations">Track job</RouterLink></div><div class="release-grid"><section class="surface release-card"><span class="large-icon"><PhPackage :size="22"/></span><div><p class="page-kicker">Mode A</p><h2>Managed runtime</h2><p>Publish approved revisions to the authoritative Zen runtime with validation, immutable history and rollback.</p></div><div class="evidence-check"><span :class="{ready:chosen()?.latestStatus==='APPROVED'}">Decision approved</span><span :class="{ready:approvedSuite()}">Golden suite approved</span></div><button class="primary-button" :disabled="busy || !decisionKey" @click="publish">Create publication</button></section><section class="surface release-card"><span class="large-icon"><PhGitBranch :size="22"/></span><div><p class="page-kicker">Mode B</p><h2>Git delivery</h2><p>Generate from a pinned baseline, run gates and create a deterministic GitHub PR or GitLab MR.</p></div><div class="provider-row"><span>GitHub</span><span>GitLab</span><small>Credentials resolved from secret references</small></div><button class="primary-button" :disabled="busy || !decisionKey" @click="deliver">Start delivery</button></section></div><section class="surface table-surface section-gap"><div class="surface-header"><div><h2>Mode-A publication history</h2><p>Every artifact is content-addressed and reversible.</p></div></div><div v-if="!modeA.length" class="empty-state"><PhPackage :size="30"/><strong>No publications</strong><span>Approved releases will appear here.</span></div><div v-else class="responsive-table"><table><thead><tr><th>ID</th><th>Action</th><th>Decision</th><th>Suite</th><th>Artifact hash</th><th>Created</th><th></th></tr></thead><tbody><tr v-for="publication in modeA" :key="publication.id"><td>#{{ publication.id }}</td><td><span class="status-badge approved">{{ publication.action }}</span></td><td>r{{ publication.decisionRevision }}</td><td>r{{ publication.suiteRevision }}</td><td><code>{{ publication.artifactHash.slice(0,14) }}</code></td><td>{{ new Date(publication.createdAt).toLocaleString() }}</td><td><button class="secondary-button" :disabled="busy" @click="rollback(publication)"><PhArrowCounterClockwise :size="13"/>Rollback</button></td></tr></tbody></table></div></section><section class="surface table-surface section-gap"><div class="surface-header"><div><h2>Mode-B delivery evidence</h2><p>Pinned commits, gate results and provider links.</p></div></div><div v-if="!modeB.length" class="empty-state"><PhGitBranch :size="30"/><strong>No Git deliveries</strong><span>Successful branches and change requests will appear here.</span></div><div v-else class="responsive-table"><table><thead><tr><th>Decision</th><th>Provider</th><th>Branch</th><th>Status</th><th>Created</th><th>Change request</th></tr></thead><tbody><tr v-for="delivery in modeB" :key="delivery.id"><td><strong>{{ delivery.decisionKey }}</strong><small>r{{ delivery.decisionRevision }}</small></td><td>{{ delivery.provider }}</td><td><code>{{ delivery.branch }}</code></td><td><span class="status-badge approved">{{ delivery.status }}</span></td><td>{{ new Date(delivery.createdAt).toLocaleString() }}</td><td><a v-if="delivery.externalUrl" class="secondary-button" :href="delivery.externalUrl" target="_blank" rel="noreferrer">Open <PhArrowSquareOut :size="13"/></a><span v-else>Local Git evidence</span></td></tr></tbody></table></div></section></section></template>
