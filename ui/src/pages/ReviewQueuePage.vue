<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ClipboardCheck, Filter, LoaderCircle } from '@lucide/vue'
import { BrpApi } from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const items = ref<Array<Record<string, unknown>>>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const selected = ref(new Set<string>())

onMounted(load)
async function load() {
  loading.value = true
  error.value = ''
  try { items.value = await api.reviewItems(store.siteId) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Review queue unavailable' }
  finally { loading.value = false }
}
async function dispose(status: 'ACCEPTED' | 'DEFERRED' | 'REJECTED') {
  const reason = status === 'ACCEPTED' ? undefined : window.prompt(`Reason for ${status.toLowerCase()}:`)?.trim()
  if (status !== 'ACCEPTED' && !reason) return
  saving.value = true
  error.value = ''
  try {
    const dispositions = [...selected.value].map((itemId) => ({ itemId, status, reason }))
    await api.disposeReviews(store.siteId, dispositions, store.actor)
    notice.value = `${dispositions.length} review item(s) updated.`
    selected.value = new Set()
    await load()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Disposition failed' }
  finally { saving.value = false }
}
function toggle(id: string) {
  const next = new Set(selected.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selected.value = next
}
</script>

<template><section><header class="page-header"><div><p class="page-kicker">Human disposition</p><h1>Review queue</h1><p>Resolve unmapped fragments and extraction diagnostics before promotion.</p></div><button class="secondary-button"><Filter :size="15" />Filters</button></header><div v-if="error" class="inline-alert" role="alert">{{ error }} <button @click="load">Retry</button></div><div v-if="notice" class="success-alert" role="status">{{ notice }}</div><section class="surface table-surface"><div class="table-toolbar"><span>{{ selected.size }} selected</span><div><LoaderCircle v-if="saving" class="spin" :size="16"/><button class="secondary-button" :disabled="!selected.size || saving" @click="dispose('ACCEPTED')">Accept</button><button class="secondary-button" :disabled="!selected.size || saving" @click="dispose('DEFERRED')">Defer</button><button class="danger-button" :disabled="!selected.size || saving" @click="dispose('REJECTED')">Reject</button></div></div><div v-if="loading" class="skeleton-list"><span v-for="n in 6" :key="n"></span></div><div v-else-if="!items.length" class="empty-state"><ClipboardCheck :size="32"/><strong>Review queue is clear</strong><span>Unmapped source fragments will appear here.</span></div><div v-else class="responsive-table"><table><thead><tr><th><span class="sr-only">Select</span></th><th>Reason</th><th>Adapter</th><th>Source fragment</th><th>Status</th><th>Created</th></tr></thead><tbody><tr v-for="item in items" :key="String(item.id)"><td><input type="checkbox" :aria-label="`Select ${item.reasonCode}`" :checked="selected.has(String(item.id))" @change="toggle(String(item.id))"/></td><td><strong>{{ item.reasonCode }}</strong></td><td>{{ item.adapter }}</td><td><code>{{ String(item.rawFragment).slice(0,100) }}</code></td><td><span class="status-badge" :class="String(item.status).toLowerCase()">{{ item.status }}</span></td><td>{{ new Date(String(item.createdAt)).toLocaleString() }}</td></tr></tbody></table></div></section></section></template>
