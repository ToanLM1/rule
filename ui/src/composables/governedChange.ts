import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '../stores/app'

/**
 * B-008 — one stable governed-change identity carried across the workflow.
 *
 * The decision key is the stable identity. Name plus revision is never used as a
 * human-unique label because the live corpus contains repeated name/revision pairs.
 * The key lives in the `decision` query parameter so every screen is deep-linkable,
 * and mirrors into the store so navigation without a query keeps the active change.
 */
export const DECISION_QUERY_KEY = 'decision'

export function useGovernedChange() {
  const store = useAppStore()
  const route = useRoute()
  const router = useRouter()

  const decisionKey = computed(() => {
    const fromQuery = route.query[DECISION_QUERY_KEY]
    if (typeof fromQuery === 'string' && fromQuery) return fromQuery
    return store.decisionKey
  })

  function adoptQuery() {
    const fromQuery = route.query[DECISION_QUERY_KEY]
    if (typeof fromQuery === 'string' && fromQuery && fromQuery !== store.decisionKey) {
      store.setDecisionKey(fromQuery)
    }
  }

  onMounted(adoptQuery)
  watch(() => route.query[DECISION_QUERY_KEY], adoptQuery)

  /** Selects the governed change and reflects it in the URL without adding history noise. */
  async function selectDecision(key: string) {
    store.setDecisionKey(key)
    const current = route.query[DECISION_QUERY_KEY]
    if (current === key) return
    const query = { ...route.query }
    if (key) query[DECISION_QUERY_KEY] = key
    else delete query[DECISION_QUERY_KEY]
    await router.replace({ path: route.path, query })
  }

  /** Builds a workflow link that preserves the active governed change. */
  function linkWithDecision(path: string) {
    return decisionKey.value ? { path, query: { [DECISION_QUERY_KEY]: decisionKey.value } } : { path }
  }

  return { decisionKey, selectDecision, linkWithDecision }
}
