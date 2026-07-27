import { describe, expect, it } from 'vitest'

import type { ImportRun, JobRecord } from '../api'
import { classifyJob, linkedImport, redactedDetail, stageTimeline } from './jobDiagnostics'

function job(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    id: 'job-1',
    siteId: 'site-1',
    type: 'REPOSITORY_IMPORT',
    status: 'FAILED',
    progress: 40,
    attempts: 1,
    maxAttempts: 3,
    cancelRequested: false,
    correlationId: 'corr-1',
    createdBy: 'maker-a',
    createdAt: '2026-07-20T09:00:00Z',
    startedAt: '2026-07-20T09:00:05Z',
    finishedAt: '2026-07-20T09:00:40Z',
    ...overrides,
  }
}

describe('classifyJob', () => {
  it('classifies provider quota as transient and auto-retried while attempts remain', () => {
    const diagnosis = classifyJob(job({ errorCode: 'PROVIDER_ERROR', errorDetail: 'HTTP 429 rate limit' }))
    expect(diagnosis.failureClass).toBe('PROVIDER_QUOTA')
    expect(diagnosis.retryable).toBe(true)
    expect(diagnosis.nextAction).toContain('retries automatically')
  })

  it('does not offer retry once attempts are exhausted', () => {
    const diagnosis = classifyJob(job({ attempts: 3, maxAttempts: 3, errorDetail: 'HTTP 429' }))
    expect(diagnosis.retryable).toBe(false)
    expect(diagnosis.retryBlockedReason).toContain('3 attempt(s)')
  })

  it('separates invalid input from unsupported semantics', () => {
    expect(classifyJob(job({ errorCode: 'VALIDATION_ERROR' })).failureClass).toBe('INVALID_INPUT')
    expect(classifyJob(job({ errorCode: 'UNSUPPORTED_CONSTRUCT' })).failureClass).toBe('UNSUPPORTED_SEMANTICS')
  })

  it('separates a governance rejection and never marks it retryable', () => {
    const diagnosis = classifyJob(job({ errorCode: 'MAKER_CHECKER_VIOLATION' }))
    expect(diagnosis.failureClass).toBe('GOVERNANCE_REJECTED')
    expect(diagnosis.retryable).toBe(false)
    expect(diagnosis.nextAction).toContain('different actor')
  })

  it('separates cancellation from failure', () => {
    const diagnosis = classifyJob(job({ status: 'CANCELLED' }))
    expect(diagnosis.failureClass).toBe('CANCELLED')
    expect(diagnosis.retryable).toBe(false)
  })

  it('classifies network failures', () => {
    expect(classifyJob(job({ errorDetail: 'connection timeout to github.com' })).failureClass).toBe('NETWORK')
  })

  /**
   * Signals taken verbatim from failed IMPORT_EXTRACT jobs on the cloud dev site
   * (2026-07-26). Before these cases the generic "attempts used up" fallback
   * swallowed every one of them and reported RETRIES_EXHAUSTED.
   */
  describe('live cloud-dev failure signals', () => {
    it('reports a non-compiling candidate as a representability limit', () => {
      const diagnosis = classifyJob(
        job({
          errorCode: 'VALUEERROR',
          errorDetail:
            'candidate package does not compile: decisions[0]: Value error, defaultOutput.discount does not match declared type decimal',
          attempts: 1,
          maxAttempts: 1,
        }),
      )
      expect(diagnosis.failureClass).toBe('UNSUPPORTED_SEMANTICS')
      expect(diagnosis.retryable).toBe(false)
      expect(diagnosis.nextAction).toContain('review queue')
    })

    it('reports the documented input/output role collision as unsupported, not exhausted', () => {
      const diagnosis = classifyJob(
        job({
          errorCode: 'VALUEERROR',
          errorDetail: 'candidate package does not compile: decisions[0].inputFields[2]: item_quality',
          attempts: 1,
          maxAttempts: 1,
        }),
      )
      expect(diagnosis.failureClass).toBe('UNSUPPORTED_SEMANTICS')
    })

    it('reports a malformed extracted decision key as invalid input', () => {
      const diagnosis = classifyJob(
        job({
          errorCode: 'VALIDATIONERROR',
          errorDetail:
            "1 validation error for CandidateDecision decision_key String should match pattern '^[a-z][a-z0-9_]*$'",
          attempts: 1,
          maxAttempts: 1,
        }),
      )
      expect(diagnosis.failureClass).toBe('INVALID_INPUT')
    })

    it('reports provider exhaustion as a provider failure', () => {
      const diagnosis = classifyJob(
        job({
          errorCode: 'LLMEXHAUSTEDERROR',
          errorDetail: "provider openai-compatible exhausted 1 attempts: ['HTTPStatusError[400]']",
          attempts: 1,
          maxAttempts: 1,
        }),
      )
      expect(diagnosis.failureClass).toBe('PROVIDER_UNAVAILABLE')
      expect(diagnosis.retryable).toBe(false)
      expect(diagnosis.nextAction).toContain('provider configuration')
    })
  })

  it('falls back to an explicit unclassified state instead of guessing', () => {
    const diagnosis = classifyJob(job({ errorCode: 'WEIRD', errorDetail: 'something else' }))
    expect(diagnosis.failureClass).toBe('UNKNOWN')
    expect(diagnosis.retryable).toBe(false)
  })
})

describe('stageTimeline', () => {
  it('marks the terminal stage as failed for a failed job', () => {
    const timeline = stageTimeline(job())
    expect(timeline.map((entry) => entry.stage)).toEqual(['Queued', 'Started', 'Running', 'Failed'])
    expect(timeline[3].state).toBe('failed')
  })

  it('leaves unreached stages pending for a queued job', () => {
    const timeline = stageTimeline(job({ status: 'QUEUED', startedAt: undefined, finishedAt: undefined }))
    expect(timeline[1].state).toBe('current')
    expect(timeline[3].at).toBeNull()
    expect(timeline[3].state).toBe('pending')
  })
})

describe('redactedDetail', () => {
  it('redacts provider tokens and embedded credentials', () => {
    const detail = redactedDetail(
      job({ errorDetail: 'push failed for https://user:pass@github.com/o/r using ghp_abcdefghijklmnop token=zzzzzz' }),
    )
    expect(detail).not.toContain('ghp_abcdefghijklmnop')
    expect(detail).not.toContain('user:pass@')
    expect(detail).toContain('[redacted-token]')
    expect(detail).toContain('token=[redacted]')
  })

  it('bounds the terminal reason', () => {
    expect(redactedDetail(job({ errorDetail: 'x'.repeat(900) }), 100)).toHaveLength(101)
  })

  it('returns nothing when the job recorded no detail', () => {
    expect(redactedDetail(job({ errorDetail: undefined }))).toBe('')
  })
})

describe('linkedImport', () => {
  const run = { id: 'run-1', jobId: 'job-1', sourceName: 'dummy-rules' } as ImportRun

  it('links a job back to its preserved import configuration', () => {
    expect(linkedImport(job(), [run])?.sourceName).toBe('dummy-rules')
  })

  it('returns null for jobs with no import run', () => {
    expect(linkedImport(job({ id: 'job-9' }), [run])).toBeNull()
  })
})
