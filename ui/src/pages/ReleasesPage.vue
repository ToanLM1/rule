<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import {
  PhArrowSquareOut,
  PhArrowCounterClockwise,
  PhCheckCircle,
  PhGitBranch,
  PhPackage,
  PhWarningCircle,
  PhXCircle,
} from '@phosphor-icons/vue'

import {
  BrpApi,
  type DecisionSummary,
  type GoldenSuite,
  type ModeAPublication,
  type ModeBDelivery,
  type Revision,
  type SiteProfile,
} from '../api'
import DecisionPicker from '../components/DecisionPicker.vue'
import { useGovernedChange } from '../composables/governedChange'
import { consolidateErrors, showsEmptyState, useRequestState } from '../composables/requestState'
import {
  approvedSuite as findApprovedSuite,
  blockedReason,
  modeAGates,
  modeBGates,
  modeBProfile,
  type ReleaseEvidence,
} from '../domain/releaseReadiness'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const { decisionKey, selectDecision } = useGovernedChange()

const profiles = useRequestState<SiteProfile[]>([], { fallbackMessage: 'Site profiles unavailable' })
const modeB = useRequestState<ModeBDelivery[]>([], { fallbackMessage: 'Mode-B delivery evidence unavailable' })
const modeA = useRequestState<ModeAPublication[]>([], { fallbackMessage: 'Mode-A publication history unavailable' })
const suites = useRequestState<GoldenSuite[]>([], { fallbackMessage: 'Golden evidence unavailable' })
const revisions = useRequestState<Revision[]>([], { fallbackMessage: 'Decision revisions unavailable' })
const selectedDecision = useRequestState<DecisionSummary | null>(null, {
  isEmpty: () => false,
  fallbackMessage: 'Decision identity unavailable',
})
const action = useRequestState<string>('', { isEmpty: () => false, fallbackMessage: 'Release action failed' })

const busy = computed(() => action.phase.value === 'loading')
const notice = computed(() => (action.phase.value === 'ready' ? action.data.value : ''))

/** One scoped alert instead of duplicated per-request errors (B-007). */
const alert = computed(() =>
  consolidateErrors([
    { label: 'Site profiles', message: profiles.error.value },
    { label: 'Delivery evidence', message: modeB.error.value },
    { label: 'Publication history', message: modeA.error.value },
    { label: 'Golden evidence', message: suites.error.value },
    { label: 'Decision revisions', message: revisions.error.value },
    { label: 'Decision identity', message: selectedDecision.error.value },
    { label: 'Release action', message: action.error.value },
  ]),
)

const approvedRevision = computed(
  () => revisions.data.value.find((item) => item.envelope.lifecycleStatus === 'APPROVED') ?? null,
)

/**
 * Gates fail closed while decision-scoped evidence is missing, still loading, or
 * could not be trusted. A red requirement never coexists with an active action.
 */
const evidence = computed<ReleaseEvidence>(() => ({
  decisionKey: decisionKey.value,
  decision: selectedDecision.data.value,
  approvedRevision: approvedRevision.value,
  suites: suites.data.value,
  profiles: profiles.data.value,
  evidenceUnavailable:
    !decisionKey.value ||
    profiles.failed.value ||
    suites.failed.value ||
    revisions.failed.value ||
    selectedDecision.failed.value ||
    !suites.trusted.value ||
    !revisions.trusted.value ||
    !profiles.trusted.value,
}))

const gatesA = computed(() => modeAGates(evidence.value))
const gatesB = computed(() => modeBGates(evidence.value))
const reasonA = computed(() => blockedReason(gatesA.value))
const reasonB = computed(() => blockedReason(gatesB.value))

onMounted(async () => {
  await Promise.all([
    profiles.run(() => api.siteProfiles(store.siteId)),
    modeB.run(() => api.modeBHistory(store.siteId)),
    ensureDecision(),
  ])
  await loadDecisionEvidence()
})

watch(decisionKey, async () => {
  await ensureDecision()
  await loadDecisionEvidence()
})

/** Defaults to a decision only when none is carried in from the workflow. */
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

async function loadDecisionEvidence() {
  if (!decisionKey.value) {
    suites.reset()
    modeA.reset()
    revisions.reset()
    return
  }
  await Promise.all([
    suites.run(() => api.goldenSuites(store.siteId, decisionKey.value)),
    modeA.run(() => api.modeAHistory(store.siteId, decisionKey.value)),
    revisions.run(() => api.decisionRevisions(store.siteId, decisionKey.value)),
  ])
}

async function publish() {
  // Defence in depth: the backend still enforces these prerequisites.
  if (!gatesA.value.ready) return
  const decision = approvedRevision.value
  const suite = findApprovedSuite(suites.data.value)
  if (!decision || !suite) return
  await action.run(async () => {
    const job = await api.publishModeA(
      store.siteId,
      decisionKey.value,
      decision.envelope.revision,
      suite.revision,
      store.actor,
    )
    await modeA.run(() => api.modeAHistory(store.siteId, decisionKey.value))
    return `Mode-A publication queued: ${job.id}`
  })
}

async function deliver() {
  if (!gatesB.value.ready) return
  const decision = approvedRevision.value
  const profile = modeBProfile(profiles.data.value)
  if (!decision || !profile) return
  await action.run(async () => {
    const job = await api.deliverModeB(
      store.siteId,
      decisionKey.value,
      decision.envelope.revision,
      profile.revision,
      store.actor,
    )
    await modeB.run(() => api.modeBHistory(store.siteId))
    return `Mode-B delivery queued: ${job.id}`
  })
}

// Exposed so tests can prove the handlers themselves are fail-closed, not just the
// disabled attribute. The backend remains the authoritative gate.
defineExpose({ publish, deliver })

async function rollback(publication: ModeAPublication) {
  if (!window.confirm(`Rollback ${decisionKey.value} to publication ${publication.id}?`)) return
  await action.run(async () => {
    const job = await api.rollbackModeA(store.siteId, decisionKey.value, publication.id, store.actor)
    await modeA.run(() => api.modeAHistory(store.siteId, decisionKey.value))
    return `Rollback queued: ${job.id}`
  })
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Controlled delivery · step 5</p>
        <h1>Releases</h1>
        <p>Mode-A publications and Mode-B Git delivery with immutable artifact evidence.</p>
      </div>
      <DecisionPicker
        class="header-picker"
        label="Governed change"
        :model-value="decisionKey"
        @update:model-value="selectDecision"
      />
    </header>

    <div v-if="alert" class="inline-alert" role="alert">{{ alert }}</div>
    <div v-if="notice" class="success-alert" role="status">
      {{ notice }} <RouterLink to="/operations">Track job</RouterLink>
    </div>

    <div class="release-grid">
      <section class="surface release-card">
        <span class="large-icon"><PhPackage :size="22" /></span>
        <div>
          <p class="page-kicker">Mode A</p>
          <h2>Managed runtime</h2>
          <p>Publish approved revisions to the authoritative Zen runtime with validation, immutable history and rollback.</p>
        </div>
        <ul class="readiness-list" aria-label="Mode-A release readiness">
          <li v-for="item in gatesA.items" :key="item.id" :class="item.satisfied ? 'ready' : 'blocked'">
            <component :is="item.satisfied ? PhCheckCircle : PhXCircle" :size="15" />
            <div>
              <strong>{{ item.label }}</strong>
              <small>{{ item.detail }}</small>
              <small v-if="!item.satisfied" class="readiness-owner">
                Owner: {{ item.owner }} ·
                <RouterLink :to="item.remediationTo">{{ item.remediationLabel }}</RouterLink>
              </small>
            </div>
          </li>
        </ul>
        <p v-if="reasonA" :id="'mode-a-blocked'" class="readiness-reason" role="status">
          <PhWarningCircle :size="14" />{{ reasonA }}
        </p>
        <button
          class="primary-button"
          :disabled="busy || !gatesA.ready"
          :aria-describedby="reasonA ? 'mode-a-blocked' : undefined"
          @click="publish"
        >
          Create publication
        </button>
      </section>

      <section class="surface release-card">
        <span class="large-icon"><PhGitBranch :size="22" /></span>
        <div>
          <p class="page-kicker">Mode B</p>
          <h2>Git delivery</h2>
          <p>Generate from a pinned baseline, run gates and create a deterministic GitHub PR or GitLab MR.</p>
        </div>
        <div class="provider-row">
          <span>GitHub</span><span>GitLab</span><small>Credentials resolved from secret references</small>
        </div>
        <ul class="readiness-list" aria-label="Mode-B release readiness">
          <li v-for="item in gatesB.items" :key="item.id" :class="item.satisfied ? 'ready' : 'blocked'">
            <component :is="item.satisfied ? PhCheckCircle : PhXCircle" :size="15" />
            <div>
              <strong>{{ item.label }}</strong>
              <small>{{ item.detail }}</small>
              <small v-if="!item.satisfied" class="readiness-owner">
                Owner: {{ item.owner }} ·
                <RouterLink :to="item.remediationTo">{{ item.remediationLabel }}</RouterLink>
              </small>
            </div>
          </li>
        </ul>
        <p v-if="reasonB" :id="'mode-b-blocked'" class="readiness-reason" role="status">
          <PhWarningCircle :size="14" />{{ reasonB }}
        </p>
        <button
          class="primary-button"
          :disabled="busy || !gatesB.ready"
          :aria-describedby="reasonB ? 'mode-b-blocked' : undefined"
          @click="deliver"
        >
          Start delivery
        </button>
      </section>
    </div>

    <section class="surface table-surface section-gap">
      <div class="surface-header">
        <div><h2>Mode-A publication history</h2><p>Every artifact is content-addressed and reversible.</p></div>
      </div>
      <div v-if="modeA.phase.value === 'loading'" class="skeleton-list"><span v-for="n in 3" :key="n" /></div>
      <div v-else-if="modeA.failed.value" class="empty-state">
        <PhWarningCircle :size="30" /><strong>Publication history unavailable</strong>
        <span>{{ modeA.error.value }}</span>
      </div>
      <div v-else-if="showsEmptyState(modeA.phase.value)" class="empty-state">
        <PhPackage :size="30" /><strong>No publications</strong><span>Approved releases will appear here.</span>
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead><tr><th>ID</th><th>Action</th><th>Decision</th><th>Suite</th><th>Artifact hash</th><th>Created</th><th></th></tr></thead>
          <tbody>
            <tr v-for="publication in modeA.data.value" :key="publication.id">
              <td>#{{ publication.id }}</td>
              <td><span class="status-badge approved">{{ publication.action }}</span></td>
              <td>r{{ publication.decisionRevision }}</td>
              <td>r{{ publication.suiteRevision }}</td>
              <td><code>{{ publication.artifactHash.slice(0, 14) }}</code></td>
              <td>{{ new Date(publication.createdAt).toLocaleString() }}</td>
              <td>
                <button class="secondary-button" :disabled="busy" @click="rollback(publication)">
                  <PhArrowCounterClockwise :size="13" />Rollback
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="surface table-surface section-gap">
      <div class="surface-header">
        <div><h2>Mode-B delivery evidence</h2><p>Pinned commits, gate results and provider links.</p></div>
      </div>
      <div v-if="modeB.phase.value === 'loading'" class="skeleton-list"><span v-for="n in 3" :key="n" /></div>
      <div v-else-if="modeB.failed.value" class="empty-state">
        <PhWarningCircle :size="30" /><strong>Delivery evidence unavailable</strong>
        <span>{{ modeB.error.value }}</span>
      </div>
      <div v-else-if="showsEmptyState(modeB.phase.value)" class="empty-state">
        <PhGitBranch :size="30" /><strong>No Git deliveries</strong>
        <span>Successful branches and change requests will appear here.</span>
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead><tr><th>Decision</th><th>Provider</th><th>Branch</th><th>Status</th><th>Created</th><th>Change request</th></tr></thead>
          <tbody>
            <tr v-for="delivery in modeB.data.value" :key="delivery.id">
              <td><strong>{{ delivery.decisionKey }}</strong><small>r{{ delivery.decisionRevision }}</small></td>
              <td>{{ delivery.provider }}</td>
              <td><code>{{ delivery.branch }}</code></td>
              <td><span class="status-badge approved">{{ delivery.status }}</span></td>
              <td>{{ new Date(delivery.createdAt).toLocaleString() }}</td>
              <td>
                <a v-if="delivery.externalUrl" class="secondary-button" :href="delivery.externalUrl" target="_blank" rel="noreferrer">
                  Open <PhArrowSquareOut :size="13" />
                </a>
                <span v-else>Local Git evidence</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
