<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { PhArrowClockwise, PhCheck, PhPlus, PhUploadSimple } from "@phosphor-icons/vue";
import {
  BrpApi,
  type CanonicalPackageRevision,
  type CanonicalPackageSummary,
} from "../api";
import GoRulesDecisionTable from "../components/GoRulesDecisionTable.vue";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const api = new BrpApi(store.apiBaseUrl);
const packages = ref<CanonicalPackageSummary[]>([]);
const selected = ref<CanonicalPackageRevision | null>(null);
const draft = ref<CanonicalPackageRevision["package"] | null>(null);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const maker = ref("business-author");
const checker = ref("business-checker");
const changeReason = ref("Business policy update");

const currentDecision = computed(() => draft.value?.decisions[0]);
const inputFields = computed(() =>
  (draft.value?.vocabulary ?? []).filter((item) => item.role === "INPUT"),
);
const outputFields = computed(() =>
  (draft.value?.vocabulary ?? []).filter((item) => item.role === "OUTPUT"),
);

onMounted(loadPackages);
watch(() => store.siteId, loadPackages);

async function loadPackages() {
  if (!store.siteId) return;
  packages.value = await api.canonicalPackages(store.siteId).catch((cause) => {
    showError(cause);
    return [];
  });
  if (selected.value) await openPackage(selected.value.packageKey);
}

async function openPackage(key: string) {
  if (!store.siteId) return;
  clearMessages();
  try {
    selected.value = await api.canonicalPackage(store.siteId, key);
  } catch (cause) {
    showError(cause);
    selected.value = null;
  }
  draft.value = selected.value
    ? JSON.parse(JSON.stringify(selected.value.package))
    : null;
}

async function saveRevision() {
  if (!store.siteId || !selected.value || !draft.value) return;
  await run(async () => {
    selected.value = await api.reviseCanonicalPackage(
      store.siteId,
      selected.value!.packageKey,
      selected.value!.revision,
      draft.value!,
      maker.value,
      changeReason.value,
    );
    draft.value = JSON.parse(JSON.stringify(selected.value.package));
    notice.value = `Saved immutable revision ${selected.value.revision}.`;
    await loadPackages();
  });
}

async function transition(action: "submit" | "approve" | "reject") {
  if (!store.siteId || !selected.value) return;
  await run(async () => {
    const actor = action === "submit" ? maker.value : checker.value;
    selected.value = await api.transitionCanonicalPackage(
      store.siteId,
      selected.value!.packageKey,
      selected.value!.revision,
      action,
      actor,
      action === "reject" ? changeReason.value : undefined,
    );
    draft.value = JSON.parse(JSON.stringify(selected.value.package));
    notice.value = `Revision ${selected.value.revision} is ${selected.value.status}.`;
    await loadPackages();
  });
}

function addScenario() {
  if (!draft.value) return;
  draft.value.businessScenarios.push({
    scenarioId: `scenario_${draft.value.businessScenarios.length + 1}`,
    name: "New business scenario",
    inputs: Object.fromEntries(inputFields.value.map((field) => [field.key, defaultValue(field.type)])),
    expected: Object.fromEntries(outputFields.value.map((field) => [field.key, defaultValue(field.type)])),
    evidenceIds: [],
  });
}

function updateDecision(value: NonNullable<typeof currentDecision.value>) {
  if (!draft.value) return;
  draft.value.decisions[0] = value;
  error.value = "";
}

function setScenario(target: Record<string, unknown>, field: string, value: string, type: string) {
  target[field] = parseValue(value, type);
}

function parseValue(value: string, type: string): unknown {
  if (type === "boolean") return value === "true";
  if (type === "integer") return Number.parseInt(value || "0", 10);
  if (type === "decimal") return Number.parseFloat(value || "0");
  return value;
}

function defaultValue(type: string): unknown {
  return type === "boolean" ? false : ["integer", "decimal"].includes(type) ? 0 : "";
}

function clearMessages() {
  error.value = "";
  notice.value = "";
}

async function run(task: () => Promise<void>) {
  clearMessages();
  busy.value = true;
  try {
    await task();
  } catch (cause) {
    showError(cause);
  } finally {
    busy.value = false;
  }
}

function showError(cause: unknown) {
  error.value = cause instanceof Error ? cause.message : "Request failed";
}
</script>

<template>
  <main class="studio-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Author · governed change · step 3</p>
        <h1>Canonical Studio</h1>
        <p>Business decision packages. Edit vocabulary, rules and scenarios; executable Rule IR stays generated and read-only. Start a source in Imports; govern immutable revisions in Decisions.</p>
      </div>
      <div class="studio-header-side">
        <div class="studio-actors">
          <label>Maker<input v-model="maker" /></label>
          <label>Checker<input v-model="checker" /></label>
        </div>
        <RouterLink class="secondary-button" to="/test-suites">Next: Test suites →</RouterLink>
      </div>
    </header>

    <p v-if="error" class="studio-message error">{{ error }}</p>
    <p v-if="notice" class="studio-message success">{{ notice }}</p>

    <section class="studio-layout">
      <aside class="studio-list">
        <div class="section-title"><strong>Packages</strong><button class="icon-button" @click="loadPackages"><PhArrowClockwise :size="16" /></button></div>
        <button v-for="item in packages" :key="item.id" :class="{ selected: selected?.packageKey === item.packageKey }" @click="openPackage(item.packageKey)">
          <strong>{{ item.name }}</strong>
          <span>r{{ item.latestRevision }} · {{ item.latestStatus }}</span>
        </button>
        <p v-if="!packages.length" class="empty-copy">No canonical package yet. Import a small PostgreSQL table or repository candidate.</p>
      </aside>

      <div v-if="draft && selected" class="studio-editor">
        <div class="studio-toolbar">
          <div><p class="eyebrow">{{ selected.packageKey }}</p><h2>{{ draft.packageName }}</h2><span class="status-pill">{{ selected.status }} · revision {{ selected.revision }}</span></div>
          <div class="button-row">
            <button class="secondary-button" :disabled="busy || selected.status !== 'DRAFT'" @click="saveRevision"><PhUploadSimple :size="16" /> Save revision</button>
            <button class="primary-button" :disabled="busy || selected.status !== 'DRAFT'" @click="transition('submit')">Submit</button>
            <button class="primary-button" :disabled="busy || selected.status !== 'SUBMITTED'" @click="transition('approve')"><PhCheck :size="16" /> Approve</button>
          </div>
        </div>
        <label class="reason-field">Change reason<input v-model="changeReason" /></label>

        <section class="studio-card">
          <h3>Business vocabulary</h3>
          <div class="vocabulary-grid">
            <label v-for="field in draft.vocabulary" :key="field.key">
              <span>{{ field.role }}</span>
              <input v-model="field.label" :disabled="selected.status !== 'DRAFT'" />
              <small>{{ field.key }} · {{ field.type }}<template v-if="field.sourcePath"> · {{ field.sourcePath }}</template></small>
            </label>
          </div>
        </section>

        <section v-if="currentDecision" class="studio-card table-card">
          <div class="section-title">
            <div>
              <p class="eyebrow">GoRules JDM Editor · constrained profile</p>
              <h3>{{ currentDecision.name }}</h3>
              <p>Use the mature spreadsheet editor for values and rows. Vocabulary, evidence, and unsupported expressions remain governed by the platform.</p>
            </div>
          </div>
          <GoRulesDecisionTable
            :decision="currentDecision"
            :vocabulary="draft.vocabulary"
            :disabled="selected.status !== 'DRAFT'"
            @change="updateDecision"
            @error="error = $event"
          />
          <div class="gorules-evidence-strip">
            <span v-for="row in currentDecision.rows" :key="row.rowId">
              <strong>{{ row.rowId }}</strong>
              {{ row.evidenceIds?.length ?? 0 }} refs
              <small v-if="row.confidence != null">{{ Math.round(row.confidence * 100) }}%</small>
            </span>
          </div>
        </section>

        <section class="studio-card">
          <div class="section-title"><div><h3>Business scenarios</h3><p>At least one scenario is required before submit.</p></div><button class="secondary-button" :disabled="selected.status !== 'DRAFT'" @click="addScenario"><PhPlus :size="15" /> Scenario</button></div>
          <article v-for="scenario in draft.businessScenarios" :key="scenario.scenarioId" class="scenario-editor">
            <input v-model="scenario.name" :disabled="selected.status !== 'DRAFT'" />
            <div><label v-for="field in inputFields" :key="field.key">Given {{ field.label }}<input :value="String(scenario.inputs[field.key] ?? '')" :disabled="selected.status !== 'DRAFT'" @input="setScenario(scenario.inputs, field.key, ($event.target as HTMLInputElement).value, field.type)" /></label></div>
            <div><label v-for="field in outputFields" :key="field.key">Expect {{ field.label }}<input :value="String(scenario.expected[field.key] ?? '')" :disabled="selected.status !== 'DRAFT'" @input="setScenario(scenario.expected, field.key, ($event.target as HTMLInputElement).value, field.type)" /></label></div>
          </article>
        </section>
      </div>
      <div v-else class="studio-empty">Select a package to edit its business model. New here? Start a source in <RouterLink to="/imports">Imports</RouterLink>.</div>
    </section>
  </main>
</template>
