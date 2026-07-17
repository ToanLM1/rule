<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Building2, KeyRound, Plus, ShieldCheck, X } from '@lucide/vue'
import { BrpApi, type PlatformContext, type SiteProfile } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const context = ref<PlatformContext | null>(null)
const profiles = ref<SiteProfile[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const editing = ref(false)
const documentText = ref('')
const site = computed(() => context.value?.sites.find((item) => item.id === store.siteId))

onMounted(load)
async function load() {
  loading.value = true
  try { [context.value, profiles.value] = await Promise.all([api.context(), api.siteProfiles(store.siteId)]) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Site configuration unavailable' }
  finally { loading.value = false }
}
function startRevision() {
  documentText.value = JSON.stringify(profiles.value[0]?.document ?? { site: site.value?.key ?? 'site', deliveryMode: 'A', language: 'java', source: { db: { kind: 'postgres', connectionEnv: 'BRP_SOURCE_DATABASE_URL' }, repositories: [{ alias: 'rules', path: 'sources', revision: 'main' }], programContexts: [{ programId: 'rules', kind: 'SERVICE', repository: 'rules', class: 'Rules', method: 'evaluate' }] }, adapters: ['db-postgres-stored-object'], mappingSpec: 'config/mapping.yaml' }, null, 2)
  editing.value = true
}
async function save() {
  let document: Record<string, unknown>
  try { document = JSON.parse(documentText.value) }
  catch { error.value = 'Profile must be valid JSON.'; return }
  saving.value = true
  error.value = ''
  try { await api.createSiteProfile(store.siteId, document, store.actor); editing.value = false; await load() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Profile revision failed' }
  finally { saving.value = false }
}
</script>

<template><section><header class="page-header"><div><p class="page-kicker">Configuration governance</p><h1>Sites</h1><p>Versioned capabilities, adapters, targets and secret references.</p></div><button class="primary-button" @click="startRevision"><Plus :size="15"/>Create profile revision</button></header><div v-if="error" class="inline-alert" role="alert">{{ error }}</div><div class="dashboard-grid"><section class="surface detail-card"><span class="large-icon"><Building2 :size="22"/></span><h2>Active site</h2><strong>{{ site?.name ?? (loading ? 'Loading…' : 'Unknown site') }}</strong><code>{{ store.siteId }}</code><dl><div><dt>Status</dt><dd><span class="status-badge approved">{{ site?.status ?? '—' }}</span></dd></div><div><dt>Default locale</dt><dd>{{ site?.defaultLocale ?? '—' }}</dd></div><div><dt>Timezone</dt><dd>{{ site?.timezone ?? '—' }}</dd></div></dl></section><section class="surface detail-card"><span class="large-icon"><ShieldCheck :size="22"/></span><h2>Configuration policy</h2><p>Profiles are immutable revisions. Parser capabilities remain explicit and fail closed.</p><div class="policy-note"><KeyRound :size="18"/><div><strong>Secrets stay outside PostgreSQL</strong><span>Only environment or file-provider references are stored.</span></div></div></section></div><section class="surface table-surface section-gap"><div class="surface-header"><div><h2>Profile history</h2><p>Newest immutable revision first</p></div></div><div v-if="loading" class="skeleton-list"><span v-for="n in 3" :key="n"/></div><div v-else-if="!profiles.length" class="empty-state"><ShieldCheck :size="30"/><strong>No site profile yet</strong><span>Create the first capability declaration before Mode-B delivery.</span></div><div v-else class="responsive-table"><table><thead><tr><th>Revision</th><th>Delivery</th><th>Adapters</th><th>Hash</th><th>Created</th></tr></thead><tbody><tr v-for="profile in profiles" :key="profile.id"><td><strong>r{{ profile.revision }}</strong></td><td>{{ profile.document.deliveryMode }}</td><td>{{ Array.isArray(profile.document.adapters) ? profile.document.adapters.join(', ') : '—' }}</td><td><code>{{ profile.contentHash.slice(0,12) }}</code></td><td>{{ new Date(profile.createdAt).toLocaleString() }}<small>{{ profile.createdBy }}</small></td></tr></tbody></table></div></section><div v-if="editing" class="drawer-backdrop" @click.self="editing=false"><section class="profile-dialog surface" role="dialog" aria-modal="true" aria-labelledby="profile-title"><header><div><p class="page-kicker">Immutable configuration</p><h2 id="profile-title">New profile revision</h2></div><button class="icon-button" aria-label="Close" @click="editing=false"><X :size="17"/></button></header><p>Credentials must be represented only by environment or mounted-file references.</p><textarea v-model="documentText" aria-label="Site profile JSON" spellcheck="false"/><footer><button class="secondary-button" @click="editing=false">Cancel</button><button class="primary-button" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Create revision' }}</button></footer></section></div></section></template>
