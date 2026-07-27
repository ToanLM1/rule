<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { PhCaretDown, PhCaretLeft, PhCaretRight, PhMagnifyingGlass, PhWarningCircle } from '@phosphor-icons/vue'

import { BrpApi, type DecisionSummary, type Page } from '../api'
import { useRequestState } from '../composables/requestState'
import { useAppStore } from '../stores/app'

/**
 * B-008 — searchable, paginated governed-change picker.
 *
 * Replaces the native mega-select that silently truncated the site corpus to the
 * first 100 decisions and labelled distinct records identically as `name · revision`.
 * Every option is identified by its stable decision key, and the result scope is
 * always stated so a partial query is never mistaken for the whole corpus.
 */
const props = withDefaults(
  defineProps<{
    modelValue: string
    label?: string
    pageSize?: number
    /** Optional per-key readiness chip, e.g. approved golden evidence. */
    readiness?: Record<string, { label: string; tone: 'ready' | 'blocked' | 'unknown' }>
  }>(),
  { label: 'Governed decision', pageSize: 10, readiness: undefined },
)
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

const store = useAppStore()
const api = new BrpApi(store.apiBaseUrl)
const empty: Page<DecisionSummary> = { items: [], page: 1, pageSize: props.pageSize, total: 0, pages: 0 }
const results = useRequestState<Page<DecisionSummary>>(empty, {
  isEmpty: (value) => value.items.length === 0,
  fallbackMessage: 'Decision list unavailable',
})
const selectedState = useRequestState<DecisionSummary | null>(null, {
  isEmpty: () => false,
  fallbackMessage: 'Selected decision unavailable',
})
const open = ref(false)
const query = ref('')
const page = ref(1)
const activeIndex = ref(0)
const root = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
// Unique per instance so two pickers on one page never collide in the a11y tree.
const listboxId = `decision-picker-${useId()}`
let debounce: number | undefined

const items = computed(() => results.data.value.items)
const total = computed(() => results.data.value.total)
const pages = computed(() => Math.max(results.data.value.pages, 1))
const firstIndex = computed(() => (items.value.length ? (page.value - 1) * props.pageSize + 1 : 0))
const lastIndex = computed(() => (page.value - 1) * props.pageSize + items.value.length)

/** Always states what the visible options actually cover. */
const scopeLabel = computed(() => {
  if (results.phase.value === 'loading') return 'Searching the full site corpus…'
  if (results.failed.value) return 'Result scope unknown — the decision search failed.'
  if (!total.value) return query.value ? `No decision matches “${query.value}”.` : 'No governed decisions in this site yet.'
  const scope = query.value ? `matching “${query.value}”` : 'in this site'
  return `Showing ${firstIndex.value}–${lastIndex.value} of ${total.value} decisions ${scope}.`
})

const selected = computed(() => selectedState.data.value)
const summaryLabel = computed(() => {
  if (!props.modelValue) return 'Select a governed decision'
  if (selected.value) return selected.value.name
  if (selectedState.failed.value) return props.modelValue
  return props.modelValue
})

onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  void search()
  void loadSelected()
})
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick, true))

watch(() => props.modelValue, loadSelected)
watch(query, () => {
  window.clearTimeout(debounce)
  debounce = window.setTimeout(() => {
    page.value = 1
    void search()
  }, 220)
})
watch(page, () => void search())

async function search() {
  if (!store.siteId) return
  activeIndex.value = 0
  await results.run(() =>
    api.decisionPage(store.siteId, { q: query.value.trim() || undefined, page: page.value, pageSize: props.pageSize }),
  )
}

/**
 * The selected key must stay identifiable even when it is not on the current page,
 * so it is resolved independently instead of being looked up in the visible page.
 */
async function loadSelected() {
  if (!props.modelValue || !store.siteId) {
    selectedState.reset()
    return
  }
  const onPage = items.value.find((item) => item.decisionKey === props.modelValue)
  if (onPage) {
    await selectedState.run(async () => onPage)
    return
  }
  await selectedState.run(async () => {
    const matches = await api.decisionPage(store.siteId, { q: props.modelValue, pageSize: props.pageSize })
    return matches.items.find((item) => item.decisionKey === props.modelValue) ?? null
  })
}

function onDocumentClick(event: MouseEvent) {
  if (!open.value) return
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

async function toggle() {
  open.value = !open.value
  if (!open.value) return
  await nextTick()
  searchInput.value?.focus()
  if (results.phase.value === 'idle') await search()
}

function choose(item: DecisionSummary) {
  emit('update:modelValue', item.decisionKey)
  open.value = false
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    open.value = false
    return
  }
  if (!open.value && (event.key === 'ArrowDown' || event.key === 'Enter')) {
    event.preventDefault()
    void toggle()
    return
  }
  if (!items.value.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % items.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value - 1 + items.value.length) % items.value.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const item = items.value[activeIndex.value]
    if (item) choose(item)
  }
}

function optionId(item: DecisionSummary) {
  return `${listboxId}-option-${item.decisionKey}`
}
function sourceLabel(item: DecisionSummary) {
  return [item.productKey, item.flowKey].filter(Boolean).join(' · ') || 'No product/flow binding'
}
function readinessFor(item: DecisionSummary) {
  return props.readiness?.[item.decisionKey]
}
</script>

<template>
  <div ref="root" class="decision-picker">
    <span :id="`${listboxId}-label`" class="decision-picker-label">{{ props.label }}</span>
    <button
      type="button"
      class="decision-picker-trigger"
      role="combobox"
      :aria-expanded="open"
      :aria-controls="listboxId"
      :aria-labelledby="`${listboxId}-label`"
      aria-haspopup="listbox"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span class="decision-picker-summary">
        <strong>{{ summaryLabel }}</strong>
        <small v-if="props.modelValue">
          <code>{{ props.modelValue }}</code>
          <template v-if="selected"> · {{ selected.latestStatus }} · r{{ selected.latestRevision }} · {{ sourceLabel(selected) }}</template>
          <template v-else-if="selectedState.failed.value"> · identity unavailable</template>
        </small>
        <small v-else>Search by business name or decision key.</small>
      </span>
      <PhCaretDown :size="15" />
    </button>

    <div v-if="open" class="decision-picker-panel">
      <label class="decision-picker-search">
        <PhMagnifyingGlass :size="15" />
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          aria-label="Search decisions by name or key"
          placeholder="Search the full site corpus"
          @keydown="onKeydown"
        />
      </label>

      <p v-if="results.failed.value" class="decision-picker-alert" role="alert">
        <PhWarningCircle :size="15" />
        <span>{{ results.error.value }}</span>
        <button type="button" class="secondary-button" @click="search">Retry</button>
      </p>

      <p class="decision-picker-scope" aria-live="polite">{{ scopeLabel }}</p>

      <ul
        :id="listboxId"
        class="decision-picker-list"
        role="listbox"
        :aria-labelledby="`${listboxId}-label`"
        :aria-busy="results.phase.value === 'loading'"
      >
        <li
          v-for="(item, index) in items"
          :id="optionId(item)"
          :key="item.decisionKey"
          role="option"
          :aria-selected="item.decisionKey === props.modelValue"
          :class="{ active: index === activeIndex, chosen: item.decisionKey === props.modelValue }"
          @mouseenter="activeIndex = index"
          @click="choose(item)"
        >
          <span class="decision-option-main">
            <strong>{{ item.name }}</strong>
            <code>{{ item.decisionKey }}</code>
          </span>
          <span class="decision-option-meta">
            <span class="status-badge" :class="item.latestStatus.toLowerCase()">{{ item.latestStatus }}</span>
            <span>r{{ item.latestRevision }}</span>
            <span>{{ sourceLabel(item) }}</span>
            <span v-if="readinessFor(item)" class="readiness-chip" :class="readinessFor(item)!.tone">{{ readinessFor(item)!.label }}</span>
          </span>
        </li>
      </ul>

      <div class="decision-picker-pagination">
        <button type="button" class="secondary-button" :disabled="page <= 1" @click="page = page - 1">
          <PhCaretLeft :size="13" />Previous
        </button>
        <span>Page {{ page }} of {{ pages }}</span>
        <button type="button" class="secondary-button" :disabled="page >= pages" @click="page = page + 1">
          Next<PhCaretRight :size="13" />
        </button>
      </div>
    </div>
  </div>
</template>
