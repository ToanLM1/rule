<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  BrpApi,
  type ExtractionResponse,
  type GenerationResponse,
  type OrchestrationCatalog,
} from '../api'
import { useAppStore } from '../stores/app'

type WorkbenchView = 'extract' | 'generate' | 'preflight'

const samples: Record<string, { filename: string; content: string }> = {
  'db-postgres-stored-object': {
    filename: 'eligibility.sql',
    content: `CREATE FUNCTION eligibility(age integer)
RETURNS text AS $$
BEGIN
  IF age < 18 THEN RETURN '미성년';
  ELSIF age > 65 THEN RETURN '연령 초과';
  ELSE RETURN '가입 가능';
  END IF;
END;
$$ LANGUAGE plpgsql;
`,
  },
  'ui-html-validation': {
    filename: 'eligibility.html',
    content: `<form id="eligibility" aria-label="가입 검증">
  <input id="age" name="age" type="number" data-rule-type="integer"
         min="18" max="65" data-error-min="미성년" data-error-max="연령 초과">
  <input id="product" name="productCode" data-rule-in="암보험,저축보험"
         data-error-in="상품 미지원">
</form>`,
  },
  'engine-native': {
    filename: 'eligibility.drl',
    content: `rule "under-age"
when
  Applicant(age < 18)
then
  result.setEligible(false);
  result.setReasonCode("미성년");
end

rule "default"
when
  Applicant()
then
  result.setEligible(true);
  result.setReasonCode("가입 가능");
end`,
  },
  'engine-dmn': {
    filename: 'eligibility.dmn',
    content: `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" id="defs" name="가입 규칙">
  <decision id="eligibility" name="가입 자격">
    <decisionTable id="table" hitPolicy="FIRST">
      <input id="in-age" label="age"><inputExpression id="expr-age" typeRef="integer"><text>age</text></inputExpression></input>
      <output id="out-result" name="result" typeRef="string"/>
      <rule id="under-age"><inputEntry id="age-under"><text>&lt; 18</text></inputEntry><outputEntry id="minor"><text>"미성년"</text></outputEntry></rule>
      <rule id="default"><inputEntry id="any"><text>-</text></inputEntry><outputEntry id="eligible"><text>"가입 가능"</text></outputEntry></rule>
    </decisionTable>
  </decision>
</definitions>`,
  },
}

const sampleProfile = {
  site: 'local-workbench',
  deliveryMode: 'B',
  language: 'java',
  source: {
    db: { kind: 'postgres', connectionEnv: 'BRP_DATABASE_URL' },
    repositories: [{ alias: 'local-fixture', path: 'fixtures/legacy-enrollment', revision: 'HEAD' }],
    programContexts: [{ programId: 'LOCAL-UI', kind: 'SCREEN', repository: 'local-fixture', class: 'local.UiForm', method: 'validate' }],
  },
  adapters: ['ui-html-validation'],
  generators: ['dmn-export'],
  mappingSpec: 'config/mappings/fixture-tables.yaml',
  target: {
    language: 'java', repository: 'out/local.git', baseBranch: 'main',
    generatedSourcePath: 'src/generated/java', generatedTestPath: 'src/generatedTest/java',
    javaPackage: 'brp.local.generated', buildCommand: './gradlew test', prProvider: 'local-report',
    composition: { facade: 'brp.local.RuleFacade', decisions: { eligibility: { field: 'result', aggregate: 'FIRST_NON_NULL' } } },
  },
}

const app = useAppStore()
const api = new BrpApi(app.apiBaseUrl)
const catalog = ref<OrchestrationCatalog | null>(null)
const view = ref<WorkbenchView>('extract')
const actor = ref('maker-a')
const adapter = ref('db-postgres-stored-object')
const filename = ref(samples[adapter.value].filename)
const sourceText = ref(samples[adapter.value].content)
const revision = ref('local-preview-v1')
const schemaName = ref('public')
const objectName = ref('eligibility')
const extraction = ref<ExtractionResponse | null>(null)
const selectedCandidate = ref(0)
const generator = ref('dmn-export')
const csharpNamespace = ref('Brp.LocalPreview')
const generation = ref<GenerationResponse | null>(null)
const profileText = ref(JSON.stringify(sampleProfile, null, 2))
const inventory = ref<Record<string, boolean>>({})
const preflightResult = ref<Record<string, unknown> | null>(null)
const busy = ref(false)
const error = ref('')

const decisions = computed(() => extraction.value?.batch.decisions ?? [])
const reviewItems = computed(() => extraction.value?.batch.unmappable ?? [])
const candidate = computed(() => decisions.value[selectedCandidate.value]?.content ?? null)

onMounted(loadCatalog)
watch(adapter, loadSample)

async function loadCatalog() {
  try {
    catalog.value = await api.orchestrationCatalog()
    inventory.value = { ...catalog.value.hostInventory }
  } catch (cause) {
    error.value = message(cause)
  }
}

function loadSample() {
  const sample = samples[adapter.value]
  filename.value = sample.filename
  sourceText.value = sample.content
  extraction.value = null
  generation.value = null
}

async function loadFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  filename.value = file.name
  sourceText.value = await file.text()
}

async function runExtraction() {
  busy.value = true
  error.value = ''
  generation.value = null
  try {
    extraction.value = await api.orchestrationExtract({
      adapter: adapter.value,
      content: sourceText.value,
      filename: filename.value,
      revision: revision.value,
      connectionAlias: 'LOCAL_INLINE',
      schemaName: schemaName.value,
      objectName: objectName.value,
    }, actor.value)
    selectedCandidate.value = 0
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}

async function runGeneration() {
  if (!candidate.value) return
  busy.value = true
  error.value = ''
  try {
    generation.value = await api.orchestrationGenerate(
      generator.value, candidate.value, actor.value, csharpNamespace.value,
    )
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}

async function runPreflight() {
  busy.value = true
  error.value = ''
  try {
    preflightResult.value = await api.orchestrationPreflight(
      [JSON.parse(profileText.value)], inventory.value,
    )
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}

function message(cause: unknown) {
  return cause instanceof Error ? cause.message : 'Orchestration request failed'
}
</script>

<template>
  <main class="orchestration-shell">
    <header class="topbar orchestration-topbar">
      <div class="brand-mark">BR</div>
      <div><p class="eyebrow">Local capability orchestration</p><h1>Phase 3 workbench</h1></div>
      <RouterLink class="top-link" to="/">Decision governance</RouterLink>
      <label class="actor-picker"><span>Acting as</span><select v-model="actor" aria-label="Workbench actor"><option>maker-a</option><option>checker-b</option></select></label>
    </header>

    <section class="workbench-hero">
      <div><span class="local-badge">{{ catalog?.evidenceLabel ?? 'LOCAL PREVIEW' }}</span><h2>Inspect → extract → generate</h2><p>Run restricted adapters against pasted or local files, inspect candidates and review items, then preview deterministic targets without persisting or approving anything.</p></div>
      <div class="boundary-card"><strong>Safety boundary</strong><span v-for="item in catalog?.boundaries ?? []" :key="item">{{ item }}</span></div>
    </section>

    <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
    <nav class="workbench-nav" aria-label="Workbench stages">
      <button :class="{ active: view === 'extract' }" @click="view = 'extract'">1. Extract</button>
      <button :class="{ active: view === 'generate' }" :disabled="!candidate" @click="view = 'generate'">2. Generate</button>
      <button :class="{ active: view === 'preflight' }" @click="view = 'preflight'">3. Preflight</button>
    </nav>

    <section v-if="view === 'extract'" class="workbench-grid">
      <div class="work-card controls-card">
        <div class="section-title"><span>Source</span><h3>Adapter input</h3></div>
        <label>Adapter<select v-model="adapter" aria-label="Source adapter"><option v-for="name in catalog?.adapters ?? Object.keys(samples)" :key="name">{{ name }}</option></select></label>
        <div class="form-row"><label>Filename<input v-model="filename" aria-label="Source filename"></label><label>Revision<input v-model="revision" aria-label="Source revision"></label></div>
        <div v-if="adapter === 'db-postgres-stored-object'" class="form-row"><label>Schema<input v-model="schemaName" aria-label="Schema name"></label><label>Object<input v-model="objectName" aria-label="Object name"></label></div>
        <label class="file-picker">Load local file<input type="file" @change="loadFile"></label>
        <textarea v-model="sourceText" class="source-editor" aria-label="Source content" spellcheck="false"></textarea>
        <button class="button primary run-button" :disabled="busy" @click="runExtraction">{{ busy ? 'Running…' : 'Run restricted extraction' }}</button>
      </div>

      <div class="work-card results-card">
        <div class="section-title result-heading"><div><span>Result</span><h3>Candidate evidence</h3></div><div v-if="extraction" class="result-stats"><strong>{{ decisions.length }}</strong><small>candidates</small><strong>{{ reviewItems.length }}</strong><small>review</small></div></div>
        <div v-if="!extraction" class="work-empty">Choose a sample or local file and run extraction.</div>
        <template v-else>
          <div class="evidence-strip"><span>{{ extraction.evidenceLabel }}</span><code>{{ extraction.batch.sourceSnapshot.contentHash.slice(0, 16) }}</code><span>not persisted</span></div>
          <div v-if="decisions.length" class="candidate-list"><button v-for="(item, index) in decisions" :key="item.decisionKey" :class="{ active: selectedCandidate === index }" @click="selectedCandidate = index"><strong>{{ item.content.decisionName }}</strong><small>{{ item.decisionKey }}</small></button></div>
          <pre class="result-code" data-testid="candidate-output">{{ candidate ? JSON.stringify(candidate, null, 2) : 'No candidate was produced.' }}</pre>
          <details v-if="reviewItems.length" class="review-details" open><summary>{{ reviewItems.length }} item(s) require review</summary><article v-for="item in reviewItems" :key="item.reasonCode + item.rawFragment"><strong>{{ item.reasonCode }}</strong><code>{{ item.rawFragment }}</code></article></details>
          <button v-if="candidate" class="button primary" @click="view = 'generate'">Continue to target preview</button>
        </template>
      </div>
    </section>

    <section v-else-if="view === 'generate'" class="workbench-grid">
      <div class="work-card controls-card">
        <div class="section-title"><span>Target</span><h3>Generator preview</h3></div>
        <label>Generator<select v-model="generator" aria-label="Target generator"><option v-for="name in catalog?.generators ?? ['dmn-export', 'csharp-source']" :key="name">{{ name }}</option></select></label>
        <label v-if="generator === 'csharp-source'">C# namespace<input v-model="csharpNamespace" aria-label="C# namespace"></label>
        <div class="candidate-summary"><span>Candidate</span><strong>{{ candidate?.decisionName }}</strong><small>{{ decisions[selectedCandidate]?.decisionKey }}</small></div>
        <div class="advisory"><strong>Preview only</strong><span>This bypasses neither approval nor release evidence. Governed delivery remains separate.</span></div>
        <button class="button primary run-button" :disabled="busy || !candidate" @click="runGeneration">{{ busy ? 'Rendering…' : 'Generate preview' }}</button>
      </div>
      <div class="work-card results-card">
        <div class="section-title result-heading"><div><span>Artifact</span><h3>Deterministic output</h3></div><code v-if="generation">{{ generation.contentHash.slice(0, 16) }}</code></div>
        <div v-if="!generation" class="work-empty">Select a target and generate a non-authoritative preview.</div>
        <template v-else><div class="evidence-strip"><span>{{ generation.evidenceLabel }}</span><span>{{ generation.path }}</span><span>not persisted</span></div><div v-if="generation.compileEvidence" class="compile-evidence"><strong>{{ generation.compileEvidence.status }}</strong><span>{{ generation.compileEvidence.detail }}</span></div><pre class="result-code artifact-code" data-testid="generated-output">{{ generation.content }}</pre></template>
      </div>
    </section>

    <section v-else class="workbench-grid preflight-grid">
      <div class="work-card controls-card"><div class="section-title"><span>Site profile</span><h3>Capability inputs</h3></div><textarea v-model="profileText" class="profile-editor" aria-label="Site profile JSON" spellcheck="false"></textarea><div class="inventory-grid"><label v-for="(_, name) in inventory" :key="name"><input v-model="inventory[name]" type="checkbox">{{ name }}</label></div><button class="button primary run-button" :disabled="busy" @click="runPreflight">Run capability preflight</button></div>
      <div class="work-card results-card"><div class="section-title"><span>Readiness</span><h3>Fail-closed matrix</h3></div><div v-if="!preflightResult" class="work-empty">Validate source, target, runtime and local toolchain compatibility before running work.</div><pre v-else class="result-code" data-testid="preflight-output">{{ JSON.stringify(preflightResult, null, 2) }}</pre></div>
    </section>
  </main>
</template>
