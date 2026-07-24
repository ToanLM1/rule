<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";
import {
  PhCaretLeft,
  PhCaretRight,
  PhCode,
  PhFunnel,
  PhPencilSimple,
  PhMagnifyingGlass,
  PhTable,
  PhX,
} from "@phosphor-icons/vue";
import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
} from "ag-grid-community";
import type { ColDef } from "ag-grid-community";
import { BrpApi, type DecisionSummary, type Page, type Revision } from "../api";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const route = useRoute();
const api = new BrpApi(store.apiBaseUrl);
const result = ref<Page<DecisionSummary>>({
  items: [],
  page: 1,
  pageSize: 25,
  total: 0,
  pages: 0,
});
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const q = ref(typeof route.query.q === "string" ? route.query.q : "");
const status = ref("");
const selected = ref<Revision | null>(null);
const editorMode = ref<"table" | "json">("table");
const editing = ref(false);
const dirty = ref(false);
const jsonHost = ref<HTMLElement | null>(null);
const AgGridVue = shallowRef();
let debounce: number | undefined;
let monacoEditor:
  | {
      dispose(): void;
      getValue(): string;
      updateOptions(value: { readOnly: boolean }): void;
      onDidChangeModelContent(listener: () => void): unknown;
    }
  | undefined;
let setMonacoTheme: ((theme: string) => void) | undefined;

ModuleRegistry.registerModules([AllCommunityModule]);
type IrField = {
  name: string;
  type: "boolean" | "integer" | "decimal" | "string" | "date";
  sourcePath?: string;
};
type IrCondition = {
  left?: { kind?: string; name?: string };
  operator?: string;
  right?: { kind?: string; value?: unknown };
};
type IrRule = Record<string, unknown> & {
  ruleId?: string;
  when?: { all?: Array<IrCondition | Record<string, unknown>>; any?: unknown[] };
  then?: Array<{ output?: string; value?: unknown }>;
  sourceReferences?: unknown[];
  confidence?: number;
};
const operatorLabels: Record<string, string> = {
  EQ: "Equals",
  NE: "Does not equal",
  GT: "Greater than",
  GTE: "At least",
  LT: "Less than",
  LTE: "At most",
  IN: "Is one of",
  NOT_IN: "Is not one of",
  BETWEEN: "Between",
  EXISTS: "Has a value",
  STARTS_WITH: "Starts with",
};
const operatorCodes = Object.fromEntries(
  Object.entries(operatorLabels).map(([code, label]) => [label, code]),
);
const inputs = computed<IrField[]>(() => selected.value?.content.inputs ?? []);
const outputs = computed<IrField[]>(() => selected.value?.content.outputs ?? []);
const columns = computed<ColDef[]>(() => {
  const result: ColDef[] = [
    {
      field: "ruleId",
      headerName: "Rule",
      minWidth: 150,
      pinned: "left",
      editable: () => editing.value,
    },
  ];
  for (const input of inputs.value) {
    result.push(
      {
        colId: `condition-${input.name}-operator`,
        headerName: `${input.name} condition`,
        minWidth: 170,
        valueGetter: (params) => {
          const condition = simpleCondition(params.data as IrRule, input.name);
          return condition?.operator
            ? operatorLabels[condition.operator] ?? condition.operator
            : "—";
        },
        editable: (params) => editing.value && isSimpleRule(params.data as IrRule),
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: Object.values(operatorLabels) },
        valueSetter: (params) => {
          const condition = ensureCondition(params.data as IrRule, input);
          const code = operatorCodes[String(params.newValue)];
          if (!code) return false;
          condition.operator = code;
          if (code === "EXISTS") delete condition.right;
          else if (!condition.right)
            condition.right = { kind: "LITERAL", value: defaultValue(input.type) };
          return true;
        },
      },
      {
        colId: `condition-${input.name}-value`,
        headerName: `${input.name} value`,
        minWidth: 150,
        valueGetter: (params) =>
          displayValue(simpleCondition(params.data as IrRule, input.name)?.right?.value),
        editable: (params) =>
          editing.value &&
          isSimpleRule(params.data as IrRule) &&
          simpleCondition(params.data as IrRule, input.name)?.operator !== "EXISTS",
        valueSetter: (params) => {
          const condition = ensureCondition(params.data as IrRule, input);
          try {
            condition.right = {
              kind: "LITERAL",
              value: parseBusinessValue(
                String(params.newValue),
                input.type,
                Array.isArray(condition.right?.value),
              ),
            };
            return true;
          } catch (cause) {
            error.value = cause instanceof Error ? cause.message : "Invalid condition value";
            return false;
          }
        },
      },
    );
  }
  for (const output of outputs.value) {
    result.push({
      colId: `outcome-${output.name}`,
      headerName: `${output.name} outcome`,
      minWidth: 170,
      valueGetter: (params) =>
        displayValue(
          (params.data as IrRule).then?.find((item) => item.output === output.name)?.value,
        ),
      editable: () => editing.value,
      valueSetter: (params) => {
        const rule = params.data as IrRule;
        const action = rule.then?.find((item) => item.output === output.name);
        if (!action) return false;
        try {
          action.value = parseBusinessValue(String(params.newValue), output.type, false);
          return true;
        } catch (cause) {
          error.value = cause instanceof Error ? cause.message : "Invalid outcome value";
          return false;
        }
      },
    });
  }
  result.push(
    {
      colId: "evidence",
      headerName: "Evidence",
      width: 110,
      valueGetter: (params) => `${(params.data as IrRule).sourceReferences?.length ?? 0} links`,
      editable: false,
    },
    {
      field: "confidence",
      headerName: "Confidence",
      width: 120,
      editable: false,
      valueFormatter: (params) =>
        typeof params.value === "number" ? `${Math.round(params.value * 100)}%` : "Authored",
    },
  );
  return result;
});
const rules = computed(() => selected.value?.content.rules ?? []);

function isCondition(value: unknown): value is IrCondition {
  return Boolean(value && typeof value === "object" && "operator" in value);
}
function isSimpleRule(rule: IrRule) {
  return Boolean(rule.when?.all && !rule.when.any && rule.when.all.every(isCondition));
}
function simpleCondition(rule: IrRule, input: string) {
  if (!isSimpleRule(rule)) return undefined;
  return rule.when?.all?.find(
    (item): item is IrCondition => isCondition(item) && item.left?.kind === "INPUT" && item.left.name === input,
  );
}
function ensureCondition(rule: IrRule, input: IrField) {
  if (!isSimpleRule(rule) || !rule.when?.all)
    throw new Error("Nested/lookup rules must be edited in Advanced JSON.");
  const existing = simpleCondition(rule, input.name);
  if (existing) return existing;
  const created: IrCondition = {
    left: { kind: "INPUT", name: input.name },
    operator: "EQ",
    right: { kind: "LITERAL", value: defaultValue(input.type) },
  };
  rule.when.all.push(created);
  return created;
}
function defaultValue(type: IrField["type"]) {
  if (type === "boolean") return false;
  if (type === "integer" || type === "decimal") return 0;
  if (type === "date") return new Date().toISOString().slice(0, 10);
  return "";
}
function parseBusinessValue(
  value: string,
  type: IrField["type"],
  list: boolean,
): unknown {
  const trimmed = value.trim();
  if (list)
    return trimmed
      .split(",")
      .map((item) => parseBusinessValue(item.trim(), type, false));
  if (type === "boolean") {
    if (!["true", "false"].includes(trimmed.toLowerCase()))
      throw new Error("Boolean values must be true or false.");
    return trimmed.toLowerCase() === "true";
  }
  if (type === "integer") {
    const parsed = Number(trimmed);
    if (!Number.isInteger(parsed)) throw new Error("Enter a whole number.");
    return parsed;
  }
  if (type === "decimal") {
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) throw new Error("Enter a number.");
    return parsed;
  }
  if (type === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(trimmed))
    throw new Error("Enter a date as YYYY-MM-DD.");
  return trimmed;
}
function displayValue(value: unknown) {
  if (Array.isArray(value)) return value.join(", ");
  if (value === undefined || value === null || value === "") return "—";
  return String(value);
}
const gridTheme = computed(() =>
  themeQuartz.withParams(
    store.resolvedTheme === "dark"
      ? {
          accentColor: "#60a5fa",
          backgroundColor: "#111a29",
          foregroundColor: "#d2dae7",
          borderColor: "#263348",
          headerBackgroundColor: "#151f30",
          fontFamily: "Outfit Variable, Outfit, ui-sans-serif, system-ui",
          fontSize: 12,
          rowBorder: true,
        }
      : {
          accentColor: "#1268f3",
          backgroundColor: "#ffffff",
          foregroundColor: "#344054",
          borderColor: "#dbe2ea",
          headerBackgroundColor: "#f8fafc",
          fontFamily: "Outfit Variable, Outfit, ui-sans-serif, system-ui",
          fontSize: 12,
          rowBorder: true,
        },
  ),
);

onMounted(async () => {
  void import("ag-grid-vue3").then((module) => {
    AgGridVue.value = module.AgGridVue;
  });
  window.addEventListener("beforeunload", protectUnload);
  await load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", protectUnload);
  monacoEditor?.dispose();
  setMonacoTheme = undefined;
});
onBeforeRouteLeave(
  () => !dirty.value || window.confirm("Discard unsaved decision changes?"),
);
watch([q, status], () => {
  clearTimeout(debounce);
  debounce = window.setTimeout(() => {
    result.value.page = 1;
    void load();
  }, 300);
});
watch(
  () => route.query.q,
  (value) => {
    const next = typeof value === "string" ? value : "";
    if (q.value !== next) q.value = next;
  },
);
watch(
  () => store.resolvedTheme,
  (theme) => setMonacoTheme?.(theme === "dark" ? "vs-dark" : "vs"),
);
watch(editorMode, (mode) => {
  if (mode === "json") void mountMonaco();
  else {
    monacoEditor?.dispose();
    monacoEditor = undefined;
  }
});
watch(editing, (value) => monacoEditor?.updateOptions({ readOnly: !value }));

function protectUnload(event: BeforeUnloadEvent) {
  if (dirty.value) event.preventDefault();
}
async function load(page = result.value.page) {
  loading.value = true;
  error.value = "";
  try {
    result.value = await api.decisionPage(store.siteId, {
      q: q.value,
      status: status.value,
      page,
      pageSize: 25,
    });
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Decisions unavailable";
  } finally {
    loading.value = false;
  }
}
async function open(item: DecisionSummary) {
  error.value = "";
  try {
    selected.value = await api.decisionV1(store.siteId, item.decisionKey);
    editorMode.value = "table";
    editing.value = false;
    dirty.value = false;
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Decision unavailable";
  }
}
function close() {
  if (dirty.value && !window.confirm("Discard unsaved changes?")) return;
  monacoEditor?.dispose();
  monacoEditor = undefined;
  selected.value = null;
  editing.value = false;
  dirty.value = false;
}
async function mountMonaco() {
  await nextTick();
  if (!jsonHost.value || !selected.value) return;
  monacoEditor?.dispose();
  const [monaco] = await Promise.all([
    import("monaco-editor/esm/vs/editor/editor.api.js"),
    import("monaco-editor/esm/vs/language/json/monaco.contribution.js"),
  ]);
  setMonacoTheme = monaco.editor.setTheme;
  const editor = monaco.editor.create(jsonHost.value, {
    value: JSON.stringify(selected.value.content, null, 2),
    language: "json",
    theme: store.resolvedTheme === "dark" ? "vs-dark" : "vs",
    automaticLayout: true,
    minimap: { enabled: false },
    readOnly: !editing.value,
    tabSize: 2,
    scrollBeyondLastLine: false,
  });
  editor.onDidChangeModelContent(() => {
    if (editing.value) dirty.value = true;
  });
  monacoEditor = editor;
}
async function save() {
  if (!selected.value || !dirty.value) return;
  let content: Record<string, unknown>;
  try {
    content =
      editorMode.value === "json" && monacoEditor
        ? JSON.parse(monacoEditor.getValue())
        : selected.value.content;
  } catch {
    error.value = "Canonical IR must be valid JSON.";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const base = selected.value.envelope.revision;
    selected.value = await api.createDecisionRevision(
      store.siteId,
      selected.value.envelope.decisionKey,
      content,
      base,
      new Date().toISOString(),
      store.actor,
    );
    notice.value = `Draft revision r${selected.value.envelope.revision} created.`;
    dirty.value = false;
    editing.value = false;
    await load();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Revision creation failed";
  } finally {
    saving.value = false;
  }
}
async function govern(action: "submit" | "approve" | "reject" | "retire") {
  if (!selected.value) return;
  const reason = ["reject", "retire"].includes(action)
    ? window.prompt(`${action} reason:`)?.trim()
    : undefined;
  if (["reject", "retire"].includes(action) && !reason) return;
  saving.value = true;
  error.value = "";
  try {
    selected.value = await api.transitionDecision(
      store.siteId,
      selected.value.envelope.decisionKey,
      selected.value.envelope.revision,
      action,
      store.actor,
      reason,
    );
    notice.value = `Revision r${selected.value.envelope.revision} ${action}d.`;
    await load();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Lifecycle transition failed";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Decision portfolio</p>
        <h1>Decisions</h1>
        <p>
          Search, govern and inspect immutable rule revisions scoped
          to this site.
        </p>
      </div>
      <RouterLink class="primary-button" to="/imports"
        >Import decision</RouterLink
      >
    </header>
    <div v-if="error" class="inline-alert" role="alert">
      {{ error }}<button @click="load()">Retry</button>
    </div>
    <div v-if="notice" class="success-alert" role="status">{{ notice }}</div>
    <section class="surface table-surface">
      <div class="portfolio-toolbar">
        <label class="search-field"
          ><PhMagnifyingGlass :size="16" /><input
            v-model="q"
            placeholder="Search name or decision key"
            aria-label="Search decisions" /></label
        ><label class="filter-select"
          ><PhFunnel :size="15" /><select
            v-model="status"
            aria-label="Lifecycle status"
          >
            <option value="">All statuses</option>
            <option>DRAFT</option>
            <option>SUBMITTED</option>
            <option>APPROVED</option>
            <option>REJECTED</option>
            <option>RETIRED</option>
          </select></label
        ><span class="result-count"
          >{{ result.total.toLocaleString() }} decisions</span
        >
      </div>
      <div v-if="loading" class="skeleton-list">
        <span v-for="n in 8" :key="n" />
      </div>
      <div v-else-if="!result.items.length" class="empty-state tall">
        <PhTable :size="34" /><strong>No matching decisions</strong
        ><span>Change the filters or import a supported source.</span
        ><RouterLink class="secondary-button" to="/imports"
          >Start import</RouterLink
        >
      </div>
      <div v-else class="responsive-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Product / flow</th>
              <th>Status</th>
              <th>Owner</th>
              <th>Revision</th>
              <th>Last activity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in result.items"
              :key="item.decisionKey"
              @dblclick="open(item)"
            >
              <td>
                <strong>{{ item.name }}</strong
                ><small>{{ item.decisionKey }}</small>
              </td>
              <td>
                <span>{{ item.productKey ?? "—" }}</span
                ><small>{{ item.flowKey ?? "Unassigned flow" }}</small>
              </td>
              <td>
                <span
                  :class="['status-badge', item.latestStatus.toLowerCase()]"
                  >{{ item.latestStatus }}</span
                >
              </td>
              <td>{{ item.owner ?? "—" }}</td>
              <td>r{{ item.latestRevision }}</td>
              <td>
                {{
                  item.updatedAt
                    ? new Date(item.updatedAt).toLocaleString()
                    : "—"
                }}
              </td>
              <td>
                <button
                  class="icon-button"
                  aria-label="Open decision"
                  @click="open(item)"
                >
                  <PhCaretRight :size="16" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="pagination">
        <span>Page {{ result.page }} of {{ Math.max(result.pages, 1) }}</span>
        <div>
          <button
            class="icon-button"
            :disabled="result.page <= 1"
            aria-label="Previous page"
            @click="load(result.page - 1)"
          >
            <PhCaretLeft :size="16" /></button
          ><button
            class="icon-button"
            :disabled="result.page >= result.pages"
            aria-label="Next page"
            @click="load(result.page + 1)"
          >
            <PhCaretRight :size="16" />
          </button>
        </div>
      </footer>
    </section>
    <div v-if="selected" class="drawer-backdrop" @click.self="close">
      <aside
        class="decision-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Decision editor"
      >
        <header>
          <div>
            <p class="page-kicker">
              {{ selected.envelope.decisionKey }} · revision
              {{ selected.envelope.revision }}
            </p>
            <h2>{{ selected.content.decisionName }}</h2>
            <div class="drawer-meta">
              <span
                :class="[
                  'status-badge',
                  selected.envelope.lifecycleStatus.toLowerCase(),
                ]"
                >{{ selected.envelope.lifecycleStatus }}</span
              ><code>{{ selected.envelope.contentHash.slice(0, 12) }}</code
              ><span>Owner {{ selected.envelope.createdBy }}</span>
            </div>
          </div>
          <button class="icon-button" aria-label="Close" @click="close">
            <PhX :size="18" />
          </button>
        </header>
        <div class="drawer-toolbar">
          <div class="segmented">
            <button
              :class="{ active: editorMode === 'table' }"
              @click="editorMode = 'table'"
            >
              <PhTable :size="14" />Decision table</button
            ><button
              :class="{ active: editorMode === 'json' }"
              @click="editorMode = 'json'"
            >
              <PhCode :size="14" />Advanced JSON
            </button>
          </div>
          <button class="secondary-button" @click="editing = !editing">
            <PhPencilSimple :size="14" />{{
              editing ? "Stop editing" : "Edit as new revision"
            }}
          </button>
        </div>
        <div class="provenance-strip">
          <span>Immutable revision</span
          ><span
            >Optimistic concurrency: base r{{
              selected.envelope.revision
            }}</span
          ><span>Source content is never translated</span>
        </div>
        <section v-if="editorMode === 'table'" class="business-model-strip">
          <div>
            <strong>Business inputs</strong>
            <span v-for="field in inputs" :key="`input-${field.name}`">
              {{ field.name }} · {{ field.type }}<small v-if="field.sourcePath">{{ field.sourcePath }}</small>
            </span>
          </div>
          <div>
            <strong>Business outcomes</strong>
            <span v-for="field in outputs" :key="`output-${field.name}`">
              {{ field.name }} · {{ field.type }}
            </span>
          </div>
          <p>
            Edit operators, values and outcomes directly in the table. Evidence and
            extraction confidence remain read-only. Nested or lookup expressions stay
            protected in Advanced JSON until the guided editor supports them.
          </p>
        </section>
        <div v-if="editorMode === 'table'" class="grid-container">
          <component
            :is="AgGridVue"
            v-if="AgGridVue"
            :theme="gridTheme"
            :rowData="rules"
            :columnDefs="columns"
            :readOnlyEdit="!editing"
            @cell-value-changed="dirty = true"
          />
        </div>
        <div v-else class="json-editor">
          <div class="advanced-warning">
            <PhCode :size="17" />
            <div>
              <strong>Advanced canonical IR</strong
              ><span
                >Schema validation runs before a revision can be created.</span
              >
            </div>
          </div>
          <div ref="jsonHost" class="monaco-host" />
        </div>
        <footer>
          <span v-if="dirty" class="unsaved-dot">Unsaved changes</span>
          <div class="row-actions">
            <button
              v-if="selected.envelope.lifecycleStatus === 'DRAFT'"
              class="secondary-button"
              :disabled="saving"
              @click="govern('submit')"
            >
              Submit</button
            ><button
              v-if="selected.envelope.lifecycleStatus === 'SUBMITTED'"
              class="secondary-button"
              :disabled="saving"
              @click="govern('approve')"
            >
              Approve</button
            ><button
              v-if="selected.envelope.lifecycleStatus === 'SUBMITTED'"
              class="danger-button"
              :disabled="saving"
              @click="govern('reject')"
            >
              Reject</button
            ><button
              v-if="selected.envelope.lifecycleStatus === 'APPROVED'"
              class="danger-button"
              :disabled="saving"
              @click="govern('retire')"
            >
              Retire</button
            ><button class="secondary-button" @click="close">Cancel</button
            ><button
              class="primary-button"
              :disabled="!dirty || saving"
              @click="save"
            >
              {{ saving ? "Creating…" : "Validate and create draft" }}
            </button>
          </div>
        </footer>
      </aside>
    </div>
  </section>
</template>
