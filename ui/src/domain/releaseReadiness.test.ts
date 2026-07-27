import { describe, expect, it } from 'vitest'

import type { DecisionSummary, GoldenSuite, Revision, SiteProfile } from '../api'
import { blockedReason, modeAGates, modeBGates, type ReleaseEvidence } from './releaseReadiness'

const decision: DecisionSummary = {
  decisionKey: 'enrollment_eligibility_v2',
  name: '가입 자격 판정',
  latestRevision: 4,
  latestStatus: 'APPROVED',
}

const approvedRevision = {
  envelope: {
    decisionKey: decision.decisionKey,
    revision: 4,
    lifecycleStatus: 'APPROVED',
    contentHash: 'a'.repeat(64),
    effectiveFrom: '2026-07-01T00:00:00Z',
    effectiveTo: null,
    createdBy: 'maker-a',
    submittedBy: 'maker-a',
    approvedBy: 'checker-b',
  },
  content: { decisionName: decision.name, rules: [] },
} as Revision

const approvedSuite: GoldenSuite = {
  id: 'suite-1',
  revision: 3,
  status: 'APPROVED',
  contentHash: 'b'.repeat(64),
  caseCount: 5,
  cases: [],
  createdBy: 'maker-a',
  createdAt: '2026-07-02T00:00:00Z',
}

function modeBProfileRecord(target: Record<string, unknown> | null = defaultTarget()): SiteProfile {
  return {
    id: 'profile-1',
    siteId: 'site-1',
    revision: 2,
    contentHash: 'c'.repeat(64),
    document: { deliveryMode: 'B', ...(target ? { target } : {}) },
    createdBy: 'admin',
    createdAt: '2026-07-03T00:00:00Z',
  }
}

function defaultTarget() {
  return {
    repository: 'targets/dummy-rules',
    baseBranch: 'main',
    buildCommand: './gradlew test',
    prProvider: 'github',
    providerRepository: 'owner/dummy-rules',
    tokenSecretRef: 'BRP_GITHUB_TOKEN',
  }
}

function evidence(overrides: Partial<ReleaseEvidence> = {}): ReleaseEvidence {
  return {
    decisionKey: decision.decisionKey,
    decision,
    approvedRevision,
    suites: [approvedSuite],
    profiles: [modeBProfileRecord()],
    evidenceUnavailable: false,
    ...overrides,
  }
}

describe('modeAGates', () => {
  it('is ready when the decision is approved and golden evidence is approved', () => {
    const gates = modeAGates(evidence())
    expect(gates.ready).toBe(true)
    expect(gates.blockers).toEqual([])
    expect(blockedReason(gates)).toBe('')
  })

  it('blocks a DRAFT decision with no approved revision', () => {
    const gates = modeAGates(
      evidence({ approvedRevision: null, decision: { ...decision, latestStatus: 'DRAFT' } }),
    )
    expect(gates.ready).toBe(false)
    const blocker = gates.blockers.find((item) => item.id === 'approved-revision')
    expect(blocker?.detail).toContain('DRAFT')
    expect(blocker?.owner).toBe('Checker')
    expect(blocker?.remediationTo).toBe('/studio')
    expect(blockedReason(gates)).toContain('Checker')
  })

  it('blocks when golden cases exist but none is approved', () => {
    const gates = modeAGates(evidence({ suites: [{ ...approvedSuite, status: 'DRAFT' }] }))
    expect(gates.ready).toBe(false)
    expect(gates.blockers.map((item) => item.id)).toContain('golden-evidence')
    expect(gates.blockers.find((item) => item.id === 'golden-evidence')?.detail).toContain('none are approved')
  })

  it('fails closed when release evidence could not be loaded', () => {
    const gates = modeAGates(evidence({ evidenceUnavailable: true }))
    expect(gates.ready).toBe(false)
    expect(gates.items.every((item) => !item.satisfied)).toBe(true)
    expect(gates.items[0].detail).toContain('cannot be proven')
  })

  it('fails closed when no governed change is selected', () => {
    const gates = modeAGates(evidence({ decisionKey: '', decision: null }))
    expect(gates.ready).toBe(false)
  })
})

describe('modeBGates', () => {
  it('is ready with an approved revision, approved golden evidence, profile, target and credentials', () => {
    const gates = modeBGates(evidence())
    expect(gates.ready).toBe(true)
    expect(gates.items.map((item) => item.id)).toEqual([
      'selection',
      'approved-revision',
      'golden-evidence',
      'site-profile',
      'target-binding',
      'credentials',
    ])
  })

  it('blocks when the site has no Mode-B profile, without hiding Mode A', () => {
    const gates = modeBGates(evidence({ profiles: [] }))
    expect(gates.ready).toBe(false)
    const blocker = gates.blockers.find((item) => item.id === 'site-profile')
    expect(blocker?.detail).toContain('Mode A stays available')
    expect(modeAGates(evidence({ profiles: [] })).ready).toBe(true)
  })

  it('blocks when a GitHub target has no credential secret reference', () => {
    const target = { ...defaultTarget(), tokenSecretRef: '' }
    const gates = modeBGates(evidence({ profiles: [modeBProfileRecord(target)] }))
    expect(gates.blockers.map((item) => item.id)).toContain('credentials')
    expect(gates.blockers.find((item) => item.id === 'credentials')?.detail).toContain('tokenSecretRef')
  })

  it('applies the same credential gate to GitLab', () => {
    const target = { ...defaultTarget(), prProvider: 'gitlab', providerRepository: '' }
    const gates = modeBGates(evidence({ profiles: [modeBProfileRecord(target)] }))
    expect(gates.ready).toBe(false)
    expect(gates.blockers.find((item) => item.id === 'credentials')?.detail).toContain('gitlab')
  })

  it('blocks when the target repository or build command is missing', () => {
    const target = { ...defaultTarget(), buildCommand: '' }
    const gates = modeBGates(evidence({ profiles: [modeBProfileRecord(target)] }))
    expect(gates.blockers.map((item) => item.id)).toContain('target-binding')
  })

  it('fails closed when evidence is unavailable', () => {
    const gates = modeBGates(evidence({ evidenceUnavailable: true }))
    expect(gates.ready).toBe(false)
    expect(gates.items).toHaveLength(6)
    expect(gates.items.every((item) => !item.satisfied)).toBe(true)
  })

  it('summarises the first blocker and its owner for a disabled action', () => {
    const gates = modeBGates(evidence({ approvedRevision: null, profiles: [] }))
    const reason = blockedReason(gates)
    expect(reason).toContain('Blocked:')
    expect(reason).toContain('more)')
  })
})
