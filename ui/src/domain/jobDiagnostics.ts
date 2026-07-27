import type { ImportRun, JobRecord } from '../api'

/**
 * B-109 — turn a failed job into an actionable operational record.
 *
 * Classification is derived from the durable job record only. Nothing here retries
 * on its own: retry is offered exclusively when the backend record shows attempts
 * remain and the terminal reason is transient, because job execution is idempotent
 * by job id.
 */
export type FailureClass =
  | 'PROVIDER_QUOTA'
  | 'PROVIDER_UNAVAILABLE'
  | 'NETWORK'
  | 'INVALID_INPUT'
  | 'UNSUPPORTED_SEMANTICS'
  | 'NO_CANDIDATE'
  | 'GOVERNANCE_REJECTED'
  | 'CANCELLED'
  | 'RETRIES_EXHAUSTED'
  | 'UNKNOWN'

export type Diagnosis = {
  failureClass: FailureClass
  title: string
  /** What the user can safely do next. */
  nextAction: string
  /** True only when re-running the same durable job is safe. */
  retryable: boolean
  retryBlockedReason: string
}

const CLASS_TITLES: Record<FailureClass, string> = {
  PROVIDER_QUOTA: 'Provider quota or rate limit',
  PROVIDER_UNAVAILABLE: 'Provider unavailable',
  NETWORK: 'Network or source unreachable',
  INVALID_INPUT: 'Invalid input configuration',
  UNSUPPORTED_SEMANTICS: 'Unsupported source semantics',
  NO_CANDIDATE: 'No candidate produced',
  GOVERNANCE_REJECTED: 'Rejected by governance',
  CANCELLED: 'Cancelled by an operator',
  RETRIES_EXHAUSTED: 'Retries exhausted',
  UNKNOWN: 'Unclassified failure',
}

function matches(haystack: string, needles: string[]): boolean {
  return needles.some((needle) => haystack.includes(needle))
}

export function classifyJob(job: JobRecord): Diagnosis {
  const signal = `${job.errorCode ?? ''} ${job.errorDetail ?? ''}`.toUpperCase()
  const attemptsLeft = job.attempts < job.maxAttempts

  // Ordering matters: the more specific cause wins over the generic
  // "attempts used up" fallback, which otherwise hides every real reason.
  let failureClass: FailureClass = 'UNKNOWN'
  if (job.status === 'CANCELLED' || job.cancelRequested) failureClass = 'CANCELLED'
  else if (matches(signal, ['QUOTA', 'RATE_LIMIT', 'RATE LIMIT', '429', 'TOO MANY REQUESTS'])) failureClass = 'PROVIDER_QUOTA'
  else if (
    matches(signal, [
      'LLMEXHAUSTED',
      'PROVIDER_UNAVAILABLE',
      'PROVIDER_NOT_CONFIGURED',
      'PROVIDER OPENAI',
      'HTTPSTATUSERROR',
      '503',
      '502',
      'UPSTREAM',
    ])
  ) {
    failureClass = 'PROVIDER_UNAVAILABLE'
  } else if (matches(signal, ['TIMEOUT', 'CONNECTION', 'NETWORK', 'DNS', 'UNREACHABLE', 'CLONE_FAILED'])) {
    failureClass = 'NETWORK'
  } else if (
    // A candidate that will not compile against the restricted profile is a
    // representability limit, not a transient fault.
    matches(signal, ['DOES NOT COMPILE', 'DECLARED TYPE', 'UNSUPPORTED', 'UNRESOLVED', 'NOT_REPRESENTABLE'])
  ) {
    failureClass = 'UNSUPPORTED_SEMANTICS'
  } else if (
    matches(signal, ['VALIDATION', 'INVALID', 'SCHEMA', 'SHOULD MATCH PATTERN', 'NOT_FOUND', 'ENTRY_POINT'])
  ) {
    failureClass = 'INVALID_INPUT'
  } else if (matches(signal, ['NO_CANDIDATE', 'EMPTY_CANDIDATE'])) failureClass = 'NO_CANDIDATE'
  else if (matches(signal, ['MAKER', 'CHECKER', 'FORBIDDEN', 'GOVERNANCE', 'APPROVAL'])) failureClass = 'GOVERNANCE_REJECTED'
  else if (!attemptsLeft && job.status === 'FAILED') failureClass = 'RETRIES_EXHAUSTED'

  const transient = ['PROVIDER_QUOTA', 'PROVIDER_UNAVAILABLE', 'NETWORK'].includes(failureClass)
  const retryable = transient && attemptsLeft && job.status === 'FAILED'

  return {
    failureClass,
    title: CLASS_TITLES[failureClass],
    retryable,
    retryBlockedReason: retryable
      ? ''
      : !attemptsLeft && job.status === 'FAILED'
        ? `All ${job.maxAttempts} attempt(s) were used. Submit a new run after correcting the cause.`
        : transient
          ? 'Retry is only offered for a failed job that still has attempts left.'
          : 'This failure is not transient. Correct the configuration or source and start a new run.',
    nextAction: nextActionFor(failureClass, retryable),
  }
}

function nextActionFor(failureClass: FailureClass, retryable: boolean): string {
  if (retryable) {
    return 'Transient and idempotent by job id: the durable worker retries automatically while attempts remain. No manual action is required yet.'
  }
  switch (failureClass) {
    case 'PROVIDER_QUOTA':
      return 'Wait for the provider quota window to reset, then start a new import.'
    case 'PROVIDER_UNAVAILABLE':
      return 'Confirm the structured LLM provider configuration, then start a new import.'
    case 'NETWORK':
      return 'Confirm the repository URL, revision and network access, then start a new import.'
    case 'INVALID_INPUT':
      return 'Correct the repository, revision, subpath or entry point in Imports and run preflight again.'
    case 'UNSUPPORTED_SEMANTICS':
      return 'Record the unresolved fragment in the review queue; the source semantics are outside the restricted profile.'
    case 'NO_CANDIDATE':
      return 'Narrow the entry-point hint or subpath so the evidence agent has a bounded decision to extract.'
    case 'GOVERNANCE_REJECTED':
      return 'A different actor must perform this step. Maker-checker separation is enforced by the backend.'
    case 'CANCELLED':
      return 'Nothing failed. Start a new run when you are ready.'
    case 'RETRIES_EXHAUSTED':
      return 'Fix the underlying cause and submit a new run.'
    default:
      return 'Inspect the terminal reason below, then either correct the configuration or start a new run.'
  }
}

/** Stage timeline reconstructed from the durable timestamps the job actually records. */
export type StageEntry = { stage: string; at: string | null; state: 'done' | 'current' | 'pending' | 'failed' }

export function stageTimeline(job: JobRecord): StageEntry[] {
  const terminalFailed = job.status === 'FAILED'
  return [
    { stage: 'Queued', at: job.createdAt, state: 'done' },
    {
      stage: 'Started',
      at: job.startedAt ?? null,
      state: job.startedAt ? 'done' : job.status === 'QUEUED' ? 'current' : 'pending',
    },
    {
      stage: 'Running',
      at: job.startedAt ?? null,
      state: job.status === 'RUNNING' ? 'current' : job.finishedAt ? 'done' : 'pending',
    },
    {
      stage: terminalFailed ? 'Failed' : job.status === 'CANCELLED' ? 'Cancelled' : 'Finished',
      at: job.finishedAt ?? null,
      state: job.finishedAt ? (terminalFailed ? 'failed' : 'done') : 'pending',
    },
  ]
}

/** Bounded, redacted terminal reason. Secrets never reach the operations surface. */
export function redactedDetail(job: JobRecord, limit = 600): string {
  const raw = job.errorDetail ?? ''
  if (!raw) return ''
  const redacted = raw
    .replace(/(gh[pousr]_[A-Za-z0-9]{10,})/g, '[redacted-token]')
    .replace(/(glpat-[A-Za-z0-9_-]{10,})/g, '[redacted-token]')
    .replace(/((?:token|secret|password|authorization|api[_-]?key)\s*[=:]\s*)\S+/gi, '$1[redacted]')
    .replace(/https:\/\/[^@\s/]+:[^@\s/]+@/g, 'https://[redacted]@')
  return redacted.length > limit ? `${redacted.slice(0, limit)}…` : redacted
}

/** Links a job back to the import run whose preserved configuration produced it. */
export function linkedImport(job: JobRecord, runs: ImportRun[]): ImportRun | null {
  return runs.find((run) => run.jobId === job.id) ?? null
}
