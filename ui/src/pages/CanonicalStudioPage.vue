<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { PhArrowClockwise, PhCheck, PhDatabase, PhPlus, PhUploadSimple } from "@phosphor-icons/vue";
import {
  BrpApi,
  type CanonicalPackageRevision,
  type CanonicalPackageSummary,
  type DiscoveredTable,
} from "../api";
import GoRulesDecisionTable from "../components/GoRulesDecisionTable.vue";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const api = new BrpApi(store.apiBaseUrl);
const tab = ref<"packages" | "database">("packages");
const packages = ref<CanonicalPackageSummary[]>([]);
const selected = ref<CanonicalPackageRevision | null>(null);
const draft = ref<CanonicalPackageRevision["package"] | null>(null);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const maker = ref("business-author");
const checker = ref("business-checker");
const changeReason = ref("Business policy update");

const connectionAlias = ref("BRP_PSQL_URL");
const schemaName = ref("brp_demo_source");
const tables = ref<DiscoveredTable[]>([]);
const selectedTableName = ref("");
const primaryKeys = ref<string[]>([]);
const conditionColumns = ref<string[]>([]);
const outcomeColumns = ref<string[]>([]);
const newPackageId = ref("db_eligibility_rules");
const newPackageName = ref("DB eligibility rules");

const selectedTable = computed(() =>
  tables.value.find((item) => item.table === selectedTableName.value),
);
const currentDecision = computed(() => draft.value?.decisions[0]);
const inputFields = computed(() =>
  (draft.value?.vocabulary ?? []).filter((item) => item.role === "INPUT"),
);
const outputFields = computed(() =>
  (draft.value?.vocabulary ?? []).filter((item) => item.role === "OUTPUT"),
);

onMounted(loadPackages);
watch(() => store.siteId, loadPackages);
watch(selectedTableName, () => {
  const columns = selectedTable.value?.columns.map((item) => item.name) ?? [];
  primaryKeys.value = columns.filter((name) => /(^id$|_id$)/i.test(name)).slice(0, 1);
  outcomeColumns.value = columns.filter((name) =>
    /eligible|reason|status|result|outcome/i.test(name),
  );
  conditionColumns.value = columns.filter(
    (name) => !primaryKeys.value.includes(name) && !outcomeColumns.value.includes(name),
  );
});

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

async function discover() {
  await run(async () => {
    tables.value = await api.discoverDbTables(
      connectionAlias.value,
      schemaName.value,
      maker.value,
    );
    selectedTableName.value = tables.value[0]?.table ?? "";
    notice.value = `Found ${tables.value.length} table/view(s).`;
  });
}

async function importTable() {
  if (!store.siteId || !selectedTable.value) return;
  await run(async () => {
    const result = await api.importDbTable(
      store.siteId,
      {
        connectionAlias: connectionAlias.value,
        schemaName: schemaName.value,
        table: selectedTable.value!.table,
        packageId: newPackageId.value,
        packageName: newPackageName.value,
        decisionId: newPackageId.value.replace(/_rules$/, ""),
        decisionName: newPackageName.value,
        conditionColumns: conditionColumns.value,
        outcomeColumns: outcomeColumns.value,
        primaryKeyColumns: primaryKeys.value,
        maxRows: 100,
        programId: "DB_RULE_IMPORT",
        programKind: "SERVICE",
        entryPoint: `${schemaName.value}.${selectedTable.value!.table}`,
        scenarios: [],
      },
      maker.value,
    );
    tab.value = "packages";
    await loadPackages();
    await openPackage(result.packageKey);
    notice.value = "Imported read-only DB snapshot. Add a business scenario before submit.";
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
        <p class="eyebrow">Business authoring</p>
        <h1>Canonical Studio</h1>
        <p>Maintain business decisions first; executable Rule IR remains generated and read-only.</p>
      </div>
      <div class="studio-actors">
        <label>Maker<input v-model="maker" /></label>
        <label>Checker<input v-model="checker" /></label>
      </div>
    </header>

    <div class="studio-tabs">
      <button :class="{ active: tab === 'packages' }" @click="tab = 'packages'">Decision packages</button>
      <button :class="{ active: tab === 'database' }" @click="tab = 'database'"><PhDatabase :size="16" /> PostgreSQL import</button>
    </div>
    <p v-if="error" class="studio-message error">{{ error }}</p>
    <p v-if="notice" class="studio-message success">{{ notice }}</p>

    <section v-if="tab === 'packages'" class="studio-layout">
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
      <div v-else class="studio-empty">Select a package to edit its business model.</div>
    </section>

    <section v-else class="studio-card db-import-card">
      <div><p class="eyebrow">Read-only source</p><h2>Guided PostgreSQL table import</h2><p>No model-authored SQL. Schema, table and selected columns are validated and bounded.</p></div>
      <div class="form-grid">
        <label>Connection reference<input v-model="connectionAlias" /></label>
        <label>Schema<input v-model="schemaName" /></label>
        <button class="secondary-button align-end" :disabled="busy" @click="discover"><PhArrowClockwise :size="16" /> Discover</button>
        <label>Table/view<select v-model="selectedTableName"><option v-for="item in tables" :key="item.table" :value="item.table">{{ item.table }} · {{ item.kind }}</option></select></label>
        <label>Package ID<input v-model="newPackageId" /></label>
        <label>Package name<input v-model="newPackageName" /></label>
      </div>
      <div v-if="selectedTable" class="column-mapping">
        <div><h3>Primary key</h3><label v-for="column in selectedTable.columns" :key="column.name"><input v-model="primaryKeys" type="checkbox" :value="column.name" />{{ column.name }} <small>{{ column.databaseType }}</small></label></div>
        <div><h3>Conditions</h3><label v-for="column in selectedTable.columns" :key="column.name"><input v-model="conditionColumns" type="checkbox" :value="column.name" />{{ column.name }} <small>{{ column.databaseType }}</small></label></div>
        <div><h3>Outcomes</h3><label v-for="column in selectedTable.columns" :key="column.name"><input v-model="outcomeColumns" type="checkbox" :value="column.name" />{{ column.name }} <small>{{ column.databaseType }}</small></label></div>
      </div>
      <button class="primary-button" :disabled="busy || !selectedTable || !primaryKeys.length || !conditionColumns.length || !outcomeColumns.length" @click="importTable"><PhDatabase :size="16" /> Import bounded snapshot</button>
    </section>
  </main>
</template>
