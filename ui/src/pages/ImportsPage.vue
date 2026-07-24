<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import {
  PhCheck,
  PhCaretRight,
  PhFileCode,
  PhGitBranch,
  PhPlay,
  PhArrowClockwise,
  PhCloudArrowUp,
} from "@phosphor-icons/vue";
import {
  BrpApi,
  type Candidate,
  type ImportRun,
  type SiteProfile,
} from "../api";
import { useAppStore } from "../stores/app";

const store = useAppStore();
const api = new BrpApi(store.apiBaseUrl);
const runs = ref<ImportRun[]>([]);
const profiles = ref<SiteProfile[]>([]);
const active = ref<ImportRun | null>(null);
const preflight = ref<Record<string, unknown> | null>(null);
const javaSourceMode = ref<"github" | "profile">("github");
const step = ref(1);
const running = ref(false);
const promoting = ref("");
const error = ref("");
let timer: number | undefined;
const form = ref({
  adapter: "db-postgres-stored-object",
  filename: "eligibility.sql",
  revision: "uploaded-v1",
  connectionAlias: "LOCAL_INLINE",
  schemaName: "public",
  objectName: "eligibility",
  content:
    "CREATE FUNCTION eligibility(age integer) RETURNS boolean AS $$\nBEGIN\n  RETURN age >= 18;\nEND;\n$$ LANGUAGE plpgsql;",
  profileRevision: null as number | null,
  repositoryUrl: "" as string | null,
  repositoryPath: ".",
  repositoryAlias: "",
  className: "",
  method: "",
});
const javaMode = computed(() => form.value.adapter === "code-java");

onMounted(async () => {
  await load();
  timer = window.setInterval(load, 4000);
});
onUnmounted(() => clearInterval(timer));
async function load() {
  if (!store.siteId) return;
  try {
    const [history, siteProfiles] = await Promise.all([
      api.importRuns(store.siteId),
      api.siteProfiles(store.siteId),
    ]);
    runs.value = history;
    profiles.value = siteProfiles;
    if (active.value)
      active.value = await api.importRun(store.siteId, active.value.id);
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Imports unavailable";
  }
}
function selectAdapter(adapter: string) {
  form.value.adapter = adapter;
  preflight.value = null;
  if (adapter === "code-java") configureProfile(profiles.value[0]);
}
function configureProfile(profile?: SiteProfile) {
  if (!profile) return;
  form.value.profileRevision = profile.revision;
  const source = profile.document.source as Record<string, unknown> | undefined;
  const repositories = source?.repositories as
    | Array<Record<string, unknown>>
    | undefined;
  const contexts = source?.programContexts as
    | Array<Record<string, unknown>>
    | undefined;
  const repository = repositories?.[0];
  const context = contexts?.[0];
  form.value.repositoryAlias = String(repository?.alias ?? "");
  form.value.revision = String(repository?.revision ?? "");
  form.value.className = String(context?.class ?? "");
  form.value.method = String(context?.method ?? "");
  form.value.filename = "repository.java";
}
function payload() {
  const value = { siteId: store.siteId, ...form.value };
  if (javaMode.value && javaSourceMode.value === "github") value.profileRevision = null;
  if (javaMode.value && javaSourceMode.value === "profile") value.repositoryUrl = null;
  return value;
}
async function runPreflight() {
  running.value = true;
  error.value = "";
  try {
    preflight.value = await api.preflightImport(payload());
    step.value = 3;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Preflight failed";
  } finally {
    running.value = false;
  }
}
async function submit() {
  running.value = true;
  error.value = "";
  try {
    active.value = await api.createImport(payload(), store.actor);
    step.value = 4;
    await load();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Import could not be queued";
  } finally {
    running.value = false;
  }
}
async function promote(candidate: Candidate) {
  promoting.value = candidate.id;
  error.value = "";
  try {
    const packageDocument = candidate.sourceSnapshot?.canonicalPackage as
      | Record<string, unknown>
      | undefined;
    if (packageDocument) {
      const packageKey = String(packageDocument.packageId ?? "");
      let baseRevision: number | undefined;
      try {
        baseRevision = (
          await api.canonicalPackage(store.siteId, packageKey)
        ).revision;
      } catch {
        /* new package */
      }
      await api.promoteCanonicalCandidate(
        candidate.id,
        { effectiveFrom: new Date().toISOString(), baseRevision },
        store.actor,
      );
      if (active.value)
        active.value = await api.importRun(store.siteId, active.value.id);
      return;
    }
    let baseRevision: number | undefined;
    try {
      baseRevision = (await api.decisionV1(store.siteId, candidate.decisionKey))
        .envelope.revision;
    } catch {
      /* new decision */
    }
    await api.promoteCandidate(
      candidate.id,
      { effectiveFrom: new Date().toISOString(), baseRevision },
      store.actor,
    );
    if (active.value)
      active.value = await api.importRun(store.siteId, active.value.id);
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Candidate promotion failed";
  } finally {
    promoting.value = "";
  }
}
function evidenceBundle(candidate: Candidate) {
  return candidate.sourceSnapshot?.evidenceBundle as
    | Record<string, unknown>
    | undefined;
}
function isPackageCandidate(candidate: Candidate) {
  return Boolean(candidate.sourceSnapshot?.canonicalPackage);
}
function evidenceCount(candidate: Candidate, field: string) {
  const value = evidenceBundle(candidate)?.[field];
  return Array.isArray(value) ? value.length : 0;
}
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <p class="page-kicker">Source onboarding</p>
        <h1>Imports</h1>
        <p>
          Connect a pinned repository or upload supported source, then promote
          reviewed candidates.
        </p>
      </div>
    </header>
    <div v-if="error" class="inline-alert" role="alert">{{ error }}</div>
    <div class="import-layout">
      <section class="surface wizard">
        <ol class="stepper">
          <li
            v-for="(label, index) in [
              'Source',
              'Configure',
              'Preflight',
              'Run & review',
            ]"
            :key="label"
            :class="{ active: step === index + 1, complete: step > index + 1 }"
          >
            <span
              ><PhCheck v-if="step > index + 1" :size="13" />{{
                step > index + 1 ? "" : index + 1
              }}</span
            >{{ label }}
          </li>
        </ol>
        <div v-if="step === 1" class="wizard-panel">
          <h2>Choose a source profile</h2>
          <p>
            Only explicit parser profiles are accepted. Unsupported syntax fails
            closed into review.
          </p>
          <div class="choice-grid">
            <button
              v-for="item in [
                {
                  id: 'code-java',
                  name: 'Pinned Java repository',
                  detail:
                    'Bounded configured entry point with immutable Git revision',
                },
                {
                  id: 'db-postgres-stored-object',
                  name: 'PostgreSQL stored object',
                  detail: 'PL/pgSQL functions and procedures',
                },
                {
                  id: 'ui-html-validation',
                  name: 'HTML validation',
                  detail: 'Declarative browser constraints',
                },
                {
                  id: 'engine-dmn',
                  name: 'DMN decision',
                  detail: 'DMN XML decision tables',
                },
                {
                  id: 'engine-native',
                  name: 'Native rule engine',
                  detail: 'Supported DRL subset',
                },
              ]"
              :key="item.id"
              :class="{ selected: form.adapter === item.id }"
              @click="selectAdapter(item.id)"
            >
              <PhGitBranch
                v-if="item.id === 'code-java'"
                :size="20"
              /><PhFileCode v-else :size="20" /><strong>{{ item.name }}</strong
              ><span>{{ item.detail }}</span>
            </button>
          </div>
          <div class="wizard-actions">
            <button class="primary-button" @click="step = 2">
              Continue <PhCaretRight :size="15" />
            </button>
          </div>
        </div>
        <div v-else-if="step === 2" class="wizard-panel">
          <h2>Configure source</h2>
          <div v-if="javaMode" class="form-grid">
            <label class="span-2"
              >Repository source<select v-model="javaSourceMode">
                <option value="github">Public GitHub URL</option>
                <option value="profile">Governed local profile</option>
              </select></label
            >
            <template v-if="javaSourceMode === 'github'">
              <label class="span-2">Public GitHub repository URL<input v-model="form.repositoryUrl" placeholder="https://github.com/owner/repository" /><small>Public HTTPS github.com repositories only. Credentials and private repositories are rejected.</small></label>
              <label>Repository alias<input v-model="form.repositoryAlias" placeholder="dummy-rules" /></label>
              <label>Repository subpath<input v-model="form.repositoryPath" placeholder="." /><small>Use <code>.</code> for a standalone repo.</small></label>
              <label>Branch, tag, or commit<input v-model="form.revision" placeholder="main" /></label>
              <label>Entry class<input v-model="form.className" placeholder="com.example.Rules" /></label>
              <label>Entry method<input v-model="form.method" placeholder="evaluate" /></label>
              <div class="policy-note span-2">Public repositories use the lightweight evidence agent: Git and ripgrep first, bounded source/test reads, then structured candidate extraction. Joern is not required. Preflight fails closed until a live structured LLM provider is configured.</div>
            </template>
            <template v-else>
            <label class="span-2"
              >Governed site profile<select
                :value="form.profileRevision ?? ''"
                @change="
                  configureProfile(
                    profiles.find(
                      (item) =>
                        item.revision ===
                        Number(($event.target as HTMLSelectElement).value),
                    ),
                  )
                "
              >
                <option value="" disabled>Select profile revision</option>
                <option
                  v-for="profile in profiles"
                  :key="profile.id"
                  :value="profile.revision"
                >
                  Revision {{ profile.revision }} ·
                  {{ profile.contentHash.slice(0, 10) }}
                </option></select
              ><small
                >Repository, revision and entry point must be allowlisted by
                this immutable profile.</small
              ></label
            ><label
              >Repository alias<input
                v-model="form.repositoryAlias"
                readonly /></label
            ><label
              >Pinned revision<input v-model="form.revision" readonly /></label
            ><label
              >Entry class<input v-model="form.className" readonly /></label
            ><label>Entry method<input v-model="form.method" readonly /></label>
            <div v-if="!profiles.length" class="inline-alert span-2">
              Create a site profile with a source repository and program context
              first.
            </div>
            </template>
          </div>
          <div v-else class="form-grid">
            <label>File name<input v-model="form.filename" /></label
            ><label>Source revision<input v-model="form.revision" /></label
            ><label
              >Connection reference<input
                v-model="form.connectionAlias"
              /><small
                >Reference only; credentials resolve outside PostgreSQL.</small
              ></label
            ><label>Object name<input v-model="form.objectName" /></label
            ><label class="span-2"
              >Source content<textarea
                v-model="form.content"
                spellcheck="false"
              />
            </label>
          </div>
          <div class="wizard-actions">
            <button class="secondary-button" @click="step = 1">Back</button
            ><button
              class="primary-button"
              :disabled="running || (javaMode && javaSourceMode === 'profile' && !form.profileRevision) || (javaMode && javaSourceMode === 'github' && (!form.repositoryUrl || !form.repositoryAlias || !form.revision || !form.className || !form.method))"
              @click="runPreflight"
            >
              <PhArrowClockwise
                v-if="running"
                class="spin"
                :size="15"
              />Preflight <PhCaretRight v-if="!running" :size="15" />
            </button>
          </div>
        </div>
        <div v-else-if="step === 3" class="wizard-panel">
          <h2>{{ preflight?.ready ? "Preflight passed" : "Preflight needs configuration" }}</h2>
          <div v-if="!preflight?.ready" class="inline-alert" role="alert">
            Repository and entry-point evidence were found, but the live structured
            LLM provider is not configured. Set the BRP_LLM_* environment variables
            and restart API/worker before queueing extraction.
          </div>
          <div class="check-list">
            <article
              v-for="check in (preflight?.checks as string[]) ?? []"
              :key="check"
            >
              <span class="check-ok"><PhCheck :size="15" /></span>
              <div>
                <strong>{{ check }}</strong>
                <p v-if="preflight?.resolvedRevision">
                  Commit {{ String(preflight.resolvedRevision).slice(0, 12) }}
                </p>
              </div>
            </article>
          </div>
          <div class="wizard-actions">
            <button class="secondary-button" @click="step = 2">Back</button
            ><button class="primary-button" :disabled="running || !preflight?.ready" @click="submit">
              <PhArrowClockwise v-if="running" class="spin" :size="15" /><PhPlay
                v-else
                :size="15"
              />Queue extraction
            </button>
          </div>
        </div>
        <div v-else class="wizard-panel">
          <h2>Run and review</h2>
          <div v-if="active" class="run-summary">
            <div>
              <span :class="['status-dot', active.status.toLowerCase()]" />
              <div>
                <strong>{{ active.sourceName }}</strong>
                <p>{{ active.status }} · {{ active.progress }}%</p>
              </div>
            </div>
            <progress :value="active.progress" max="100" />
            <div v-if="active.candidates?.length" class="candidate-cards">
              <article
                v-for="candidate in active.candidates"
                :key="candidate.id"
              >
                <div>
                  <strong>{{ candidate.name }}</strong
                  ><small>{{ candidate.decisionKey }}</small>
                  <details v-if="evidenceBundle(candidate)" class="evidence-summary">
                    <summary>Source evidence</summary>
                    <p>{{ String(evidenceBundle(candidate)?.hypothesis ?? "Candidate hypothesis") }}</p>
                    <ul>
                      <li>{{ evidenceCount(candidate, "spans") }} bounded source/test spans</li>
                      <li>{{ evidenceCount(candidate, "fieldEvidence") }} fields with linked evidence</li>
                      <li>{{ evidenceCount(candidate, "assumptions") }} assumptions</li>
                      <li>{{ evidenceCount(candidate, "unresolvedCalls") }} unresolved calls</li>
                    </ul>
                  </details>
                </div>
                <div class="row-actions">
                  <span class="status-badge">{{ candidate.status }}</span
                  ><button
                    v-if="candidate.status !== 'PROMOTED'"
                    class="primary-button"
                    :disabled="promoting === candidate.id"
                    @click="promote(candidate)"
                  >
                    {{
                      promoting === candidate.id ? "Promoting…" : "Promote"
                    }}</button
                  ><RouterLink
                    v-else
                    class="secondary-button"
                    :to="isPackageCandidate(candidate) ? '/studio' : '/decisions'"
                    >{{
                      isPackageCandidate(candidate)
                        ? "Open in Canonical Studio"
                        : "View decision"
                    }}</RouterLink
                  >
                </div>
              </article>
            </div>
            <div v-if="active.status === 'FAILED'" class="inline-alert">
              Open Operations using job {{ active.jobId }} for the structured
              error and retry history.
            </div>
          </div>
          <button
            class="secondary-button"
            @click="
              step = 1;
              active = null;
            "
          >
            Start another import
          </button>
        </div>
      </section>
      <aside class="surface history-panel">
        <header class="surface-header">
          <div>
            <h2>Import history</h2>
            <p>Most recent runs for this site</p>
          </div>
        </header>
        <div v-if="!runs.length" class="empty-state">
          <PhCloudArrowUp :size="28" /><strong>No import runs</strong>
        </div>
        <button
          v-for="run in runs"
          :key="run.id"
          class="history-row"
          @click="
            active = run;
            step = 4;
          "
        >
          <span :class="['status-dot', run.status.toLowerCase()]" />
          <div>
            <strong>{{ run.sourceName }}</strong
            ><small
              >{{ run.adapter }} ·
              {{ new Date(run.createdAt).toLocaleString() }}</small
            >
          </div>
          <span>{{ run.progress }}%</span>
        </button>
      </aside>
    </div>
  </section>
</template>
