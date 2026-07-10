<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { BrpApi, type AuditEvent, type DecisionSummary, type Revision } from '../api'
import { useAppStore } from '../stores/app'

type Tab = 'rules' | 'diff' | 'audit' | 'review' | 'golden' | 'preview'
const tabs: Tab[] = ['rules', 'diff', 'audit', 'review', 'golden', 'preview']

const app = useAppStore()
const api = new BrpApi(app.apiBaseUrl)
const decisions = ref<DecisionSummary[]>([])
const selected = ref<Revision | null>(null)
const audit = ref<AuditEvent[]>([])
const reviewItems = ref<Array<Record<string, unknown>>>([])
const golden = ref<Array<Record<string, unknown>>>([])
const diff = ref<Record<string, unknown> | null>(null)
const actor = ref('maker-a')
const tab = ref<Tab>('rules')
const loading = ref(true)
const error = ref('')
const editing = ref(false)
const editorText = ref('')
const previewText = ref('{\n  "age": 17,\n  "productCode": "CANCER_BASIC",\n  "regionCode": "SEOUL"\n}')
const previewResult = ref<Record<string, unknown> | null>(null)
const statusTone = computed(() => selected.value?.envelope.lifecycleStatus.toLowerCase() ?? 'draft')

onMounted(loadDecisions)

async function loadDecisions() {
  loading.value = true
  error.value = ''
  try {
    decisions.value = await api.decisions()
    if (!selected.value && decisions.value.length) await choose(decisions.value[0].decisionKey)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to load decisions'
  } finally {
    loading.value = false
  }
}

async function choose(key: string) {
  selected.value = await api.decision(key)
  tab.value = 'rules'
  await Promise.all([loadAudit(), loadGolden()])
}

async function loadAudit() {
  if (selected.value) audit.value = await api.audit(selected.value.envelope.decisionKey)
}

async function loadGolden() {
  if (selected.value) golden.value = await api.goldenStatus(selected.value.envelope.decisionKey)
}

async function activate(next: Tab) {
  tab.value = next
  if (next === 'review') reviewItems.value = await api.reviewQueue()
  if (next === 'diff' && selected.value && selected.value.envelope.revision > 1) {
    diff.value = await api.diff(selected.value.envelope.decisionKey, selected.value.envelope.revision - 1, selected.value.envelope.revision)
  }
}

async function transition(action: string) {
  if (!selected.value) return
  error.value = ''
  try {
    selected.value = await api.transition(
      selected.value.envelope.decisionKey,
      selected.value.envelope.revision,
      action,
      actor.value,
      action === 'reject' ? 'Rejected during governance review' : undefined,
    )
    await Promise.all([loadAudit(), loadDecisions()])
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Transition failed'
  }
}

function beginEdit() {
  if (!selected.value) return
  editorText.value = JSON.stringify(selected.value.content, null, 2)
  editing.value = true
}

async function saveRevision() {
  if (!selected.value) return
  try {
    selected.value = await api.addRevision(
      selected.value.envelope.decisionKey,
      JSON.parse(editorText.value),
      actor.value,
      new Date().toISOString(),
    )
    editing.value = false
    await loadDecisions()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Revision could not be saved'
  }
}

async function runPreview() {
  if (!selected.value) return
  previewResult.value = await api.preview(
    selected.value.envelope.decisionKey,
    selected.value.envelope.revision,
    JSON.parse(previewText.value),
  )
}
</script>

<template>
  <main class="workspace">
    <header class="topbar">
      <div class="brand-mark">BR</div>
      <div><p class="eyebrow">Business Rules Platform</p><h1>Decision governance</h1></div>
      <label class="actor-picker"><span>Acting as</span><select v-model="actor" aria-label="Actor"><option>maker-a</option><option>checker-b</option><option>reviewer-c</option></select></label>
    </header>

    <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
    <div class="layout">
      <aside class="decision-rail" aria-label="Decision list">
        <div class="rail-title"><div><span>Portfolio</span><strong>Decisions</strong></div><span class="count">{{ decisions.length }}</span></div>
        <p v-if="loading" class="empty">Loading governed decisions…</p>
        <p v-else-if="!decisions.length" class="empty">No decisions found.</p>
        <button v-for="item in decisions" :key="item.decisionKey" class="decision-item" :class="{ active: selected?.envelope.decisionKey === item.decisionKey }" @click="choose(item.decisionKey)">
          <span class="decision-glyph">{{ item.name.slice(0, 1) }}</span>
          <span class="decision-copy"><strong>{{ item.name }}</strong><small>{{ item.decisionKey }}</small></span>
          <span class="revision">r{{ item.latestRevision }}</span>
        </button>
      </aside>

      <section v-if="selected" class="detail" aria-label="Decision detail">
        <div class="detail-head">
          <div><div class="breadcrumb">Decisions / {{ selected.envelope.decisionKey }}</div><h2>{{ selected.content.decisionName }}</h2><div class="meta-line"><span :class="['status', statusTone]">{{ selected.envelope.lifecycleStatus }}</span><span>Revision {{ selected.envelope.revision }}</span><span class="hash">{{ selected.envelope.contentHash.slice(0, 12) }}</span></div></div>
          <div class="actions"><button class="button ghost" @click="beginEdit">Edit as new revision</button><button v-if="selected.envelope.lifecycleStatus === 'DRAFT'" class="button primary" @click="transition('submit')">Submit</button><template v-if="selected.envelope.lifecycleStatus === 'SUBMITTED'"><button class="button danger" @click="transition('reject')">Reject</button><button class="button primary" @click="transition('approve')">Approve</button></template></div>
        </div>

        <div class="envelope-grid" aria-label="Revision envelope"><div><span>Effective from</span><strong>{{ new Date(selected.envelope.effectiveFrom).toLocaleDateString() }}</strong></div><div><span>Created by</span><strong>{{ selected.envelope.createdBy }}</strong></div><div><span>Submitted by</span><strong>{{ selected.envelope.submittedBy ?? '—' }}</strong></div><div><span>Approved by</span><strong>{{ selected.envelope.approvedBy ?? '—' }}</strong></div></div>
        <nav class="tabs" aria-label="Decision views"><button v-for="name in tabs" :key="name" :class="{ active: tab === name }" @click="activate(name)">{{ name }}</button></nav>

        <div v-if="tab === 'rules'" class="panel">
          <div class="panel-heading"><div><span>Canonical content</span><h3>Rules</h3></div><strong>{{ selected.content.rules.length }} rules</strong></div>
          <article v-for="(rule, index) in selected.content.rules" :key="String(rule.ruleId)" class="rule-row"><span class="rule-index">{{ String(index + 1).padStart(2, '0') }}</span><div><strong>{{ rule.ruleId }}</strong><code>{{ JSON.stringify(rule.when) }}</code></div><div class="then"><span>THEN</span><code>{{ JSON.stringify(rule.then) }}</code></div><span class="confidence">{{ Math.round(Number(rule.confidence ?? 0) * 100) }}%</span></article>
        </div>
        <div v-else-if="tab === 'diff'" class="panel code-panel"><h3>Semantic revision diff</h3><pre>{{ diff ? JSON.stringify(diff, null, 2) : 'No prior revision to compare.' }}</pre></div>
        <div v-else-if="tab === 'audit'" class="panel"><h3>Append-only audit trail</h3><div v-for="event in audit" :key="event.id" class="timeline"><span></span><div><strong>{{ event.action }}</strong><p>{{ event.actor }} · {{ event.fromStatus }} → {{ event.toStatus }}</p></div><time>{{ new Date(event.at).toLocaleString() }}</time></div></div>
        <div v-else-if="tab === 'review'" class="panel"><h3>Review queue</h3><div v-if="!reviewItems.length" class="empty-state">No unmappable source fragments are waiting.</div><pre v-else>{{ JSON.stringify(reviewItems, null, 2) }}</pre></div>
        <div v-else-if="tab === 'golden'" class="panel"><h3>Golden-suite evidence</h3><div v-if="!golden.length" class="empty-state warning">Approval is blocked until a golden suite is approved.</div><div v-for="suite in golden" :key="String(suite.revision)" class="suite-row"><strong>Suite r{{ suite.revision }}</strong><span class="status approved">{{ suite.status }}</span><code>{{ String(suite.contentHash).slice(0, 16) }}</code></div></div>
        <div v-else class="panel preview-panel"><div class="advisory"><strong>Advisory preview</strong><span>ZEN is not the Mode-B production authority</span></div><div class="preview-grid"><textarea v-model="previewText" aria-label="Preview input"></textarea><pre data-testid="preview-result">{{ previewResult ? JSON.stringify(previewResult, null, 2) : 'Run a scenario to inspect the advisory result.' }}</pre></div><button class="button primary" @click="runPreview">Run Zen preview</button></div>
      </section>
    </div>

    <div v-if="editing" class="modal-backdrop" @click.self="editing = false"><section class="modal" role="dialog" aria-modal="true" aria-label="Edit as new revision"><div><span class="eyebrow">Immutable revision workflow</span><h2>Create new draft</h2></div><textarea v-model="editorText" aria-label="Decision JSON"></textarea><div class="actions"><button class="button ghost" @click="editing = false">Cancel</button><button class="button primary" @click="saveRevision">Save draft revision</button></div></section></div>
  </main>
</template>
