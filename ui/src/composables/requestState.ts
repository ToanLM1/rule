import { computed, ref, type ComputedRef, type Ref } from 'vue'

/**
 * B-007 — truthful request states.
 *
 * `empty` and any numeric zero are only reachable through a successful response.
 * A failed refresh over previously loaded data becomes `stale`, never `empty`.
 */
export type RequestPhase = 'idle' | 'loading' | 'ready' | 'empty' | 'error' | 'stale'

export type RequestState<T> = {
  phase: Ref<RequestPhase>
  data: Ref<T>
  error: Ref<string>
  loadedAt: Ref<string>
  /** True only when the current value came from a successful response. */
  trusted: ComputedRef<boolean>
  /** True when the last attempt failed, whether or not older data survives. */
  failed: ComputedRef<boolean>
  run: (loader: () => Promise<T>) => Promise<T | undefined>
  reset: () => void
}

export type RequestStateOptions<T> = {
  /** Decides whether a successful response should render as `empty`. */
  isEmpty?: (value: T) => boolean
  /** Message used when the thrown cause carries none. */
  fallbackMessage?: string
}

function defaultIsEmpty(value: unknown): boolean {
  if (Array.isArray(value)) return value.length === 0
  if (value === null || value === undefined) return true
  return false
}

export function useRequestState<T>(initial: T, options: RequestStateOptions<T> = {}): RequestState<T> {
  const isEmpty = options.isEmpty ?? (defaultIsEmpty as (value: T) => boolean)
  const fallback = options.fallbackMessage ?? 'Request failed'
  const phase = ref<RequestPhase>('idle') as Ref<RequestPhase>
  const data = ref(initial) as Ref<T>
  const error = ref('')
  const loadedAt = ref('')

  const trusted = computed(() => phase.value === 'ready' || phase.value === 'empty')
  const failed = computed(() => phase.value === 'error' || phase.value === 'stale')

  async function run(loader: () => Promise<T>): Promise<T | undefined> {
    const hadValue = Boolean(loadedAt.value)
    phase.value = 'loading'
    error.value = ''
    try {
      const value = await loader()
      data.value = value
      loadedAt.value = new Date().toISOString()
      phase.value = isEmpty(value) ? 'empty' : 'ready'
      return value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : fallback
      // Never downgrade an unknown result into "none": keep prior data as stale.
      phase.value = hadValue ? 'stale' : 'error'
      return undefined
    }
  }

  function reset() {
    phase.value = 'idle'
    data.value = initial
    error.value = ''
    loadedAt.value = ''
  }

  return { phase, data, error, loadedAt, trusted, failed, run, reset }
}

/**
 * Renders a count only when it came from a successful response.
 * Anything else is explicitly unavailable rather than `0`.
 */
export function truthfulCount(phase: RequestPhase, value: number | null | undefined, unavailable = 'Unavailable'): string {
  if (phase === 'loading' || phase === 'idle') return '—'
  if (phase === 'error' || phase === 'stale') return unavailable
  if (value === null || value === undefined) return unavailable
  return value.toLocaleString()
}

/** Normal empty-state copy is only honest after a successful, genuinely empty response. */
export function showsEmptyState(phase: RequestPhase): boolean {
  return phase === 'empty'
}

/** Consolidates several failed requests into one scoped, non-duplicated message. */
export function consolidateErrors(entries: Array<{ label: string; message: string }>): string {
  const failures = entries.filter((entry) => entry.message)
  if (!failures.length) return ''
  const unique = new Map<string, string[]>()
  for (const entry of failures) {
    const labels = unique.get(entry.message) ?? []
    labels.push(entry.label)
    unique.set(entry.message, labels)
  }
  return [...unique.entries()]
    .map(([message, labels]) => `${labels.join(', ')} unavailable: ${message}`)
    .join(' · ')
}
