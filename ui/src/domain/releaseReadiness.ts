import type { DecisionSummary, GoldenSuite, Revision, SiteProfile } from '../api'

/**
 * B-008 — authoritative, fail-closed release gates.
 *
 * Every gate is computed from evidence that was actually loaded. An unknown gate
 * (request failed, never attempted, still loading) is NOT satisfied. The UI guardrail
 * supplements the backend rejection; it never replaces it.
 *
 * Mode A and Mode B both remain first-class customer-accepted targets, as do the
 * GitHub and GitLab providers. This module changes safety, not accepted scope.
 */
export type ReadinessOwner = 'Maker' | 'Checker' | 'Delivery owner' | 'Platform admin'

export type ReadinessItem = {
  id: string
  label: string
  satisfied: boolean
  /** Why the gate is not satisfied, or what evidence satisfied it. */
  detail: string
  owner: ReadinessOwner
  remediationLabel: string
  remediationTo: string
}

export type ReleaseEvidence = {
  /** The selected governed change, or null when nothing is selected. */
  decisionKey: string
  decision: DecisionSummary | null
  /** Highest APPROVED revision for the decision, or null when none exists. */
  approvedRevision: Revision | null
  /** All golden suites known for the decision. */
  suites: GoldenSuite[]
  /** All site profile revisions known for the site. */
  profiles: SiteProfile[]
  /** Set when the supporting requests could not be trusted (error or stale). */
  evidenceUnavailable: boolean
}

export type TargetGates = {
  target: 'A' | 'B'
  items: ReadinessItem[]
  ready: boolean
  blockers: ReadinessItem[]
}

function unavailable(id: string, label: string, owner: ReadinessOwner, to: string, remediationLabel: string): ReadinessItem {
  return {
    id,
    label,
    satisfied: false,
    detail: 'Release evidence could not be loaded, so this gate cannot be proven. The action stays closed.',
    owner,
    remediationLabel,
    remediationTo: to,
  }
}

export function approvedSuite(suites: GoldenSuite[]): GoldenSuite | null {
  return suites.find((item) => item.status === 'APPROVED') ?? null
}

export function modeBProfile(profiles: SiteProfile[]): SiteProfile | null {
  return profiles.find((item) => item.document.deliveryMode === 'B') ?? null
}

function profileTarget(profile: SiteProfile | null): Record<string, unknown> | null {
  const target = profile?.document.target
  return target && typeof target === 'object' ? (target as Record<string, unknown>) : null
}

function selectionGate(evidence: ReleaseEvidence, owner: ReadinessOwner): ReadinessItem {
  return {
    id: 'selection',
    label: 'A governed change is selected',
    satisfied: Boolean(evidence.decisionKey && evidence.decision),
    detail: evidence.decisionKey && evidence.decision
      ? `Decision key ${evidence.decisionKey}`
      : 'Search for the exact decision key. Name plus revision is not unique in this site.',
    owner,
    remediationLabel: 'Find a decision',
    remediationTo: '/decisions',
  }
}

function approvedRevisionGate(evidence: ReleaseEvidence, owner: ReadinessOwner): ReadinessItem {
  const status = evidence.decision?.latestStatus ?? 'UNKNOWN'
  return {
    id: 'approved-revision',
    label: 'An independently approved decision revision exists',
    satisfied: Boolean(evidence.approvedRevision),
    detail: evidence.approvedRevision
      ? `Approved revision r${evidence.approvedRevision.envelope.revision} by ${evidence.approvedRevision.envelope.approvedBy ?? 'an independent checker'}`
      : `Latest revision is ${status}. A separate checker must approve it before release.`,
    owner,
    remediationLabel: 'Open Canonical Studio',
    remediationTo: '/studio',
  }
}

function goldenEvidenceGate(evidence: ReleaseEvidence, owner: ReadinessOwner): ReadinessItem {
  const suite = approvedSuite(evidence.suites)
  return {
    id: 'golden-evidence',
    label: 'Approved golden evidence exists',
    satisfied: Boolean(suite),
    detail: suite
      ? `Suite r${suite.revision} · ${suite.caseCount} cases · ${suite.contentHash.slice(0, 12)}`
      : evidence.suites.length
        ? 'Golden cases exist but none are approved. An independent checker must approve a suite revision.'
        : 'No golden suite revision has been captured for this decision.',
    owner,
    remediationLabel: 'Open Test suites',
    remediationTo: '/test-suites',
  }
}

export function modeAGates(evidence: ReleaseEvidence): TargetGates {
  const items = evidence.evidenceUnavailable
    ? [
        unavailable('selection', 'A governed change is selected', 'Maker', '/decisions', 'Find a decision'),
        unavailable('approved-revision', 'An independently approved decision revision exists', 'Checker', '/studio', 'Open Canonical Studio'),
        unavailable('golden-evidence', 'Approved golden evidence exists', 'Checker', '/test-suites', 'Open Test suites'),
      ]
    : [
        selectionGate(evidence, 'Maker'),
        approvedRevisionGate(evidence, 'Checker'),
        goldenEvidenceGate(evidence, 'Checker'),
      ]
  return finalize('A', items)
}

export function modeBGates(evidence: ReleaseEvidence): TargetGates {
  if (evidence.evidenceUnavailable) {
    return finalize('B', [
      unavailable('selection', 'A governed change is selected', 'Maker', '/decisions', 'Find a decision'),
      unavailable('approved-revision', 'An independently approved decision revision exists', 'Checker', '/studio', 'Open Canonical Studio'),
      unavailable('golden-evidence', 'Approved golden evidence exists', 'Checker', '/test-suites', 'Open Test suites'),
      unavailable('site-profile', 'A Mode-B site profile revision is configured', 'Platform admin', '/sites', 'Open Sites'),
      unavailable('target-binding', 'The profile pins a target repository and build command', 'Delivery owner', '/sites', 'Open Sites'),
      unavailable('credentials', 'Provider credentials resolve from a secret reference', 'Delivery owner', '/sites', 'Open Sites'),
    ])
  }

  const profile = modeBProfile(evidence.profiles)
  const target = profileTarget(profile)
  const provider = typeof target?.prProvider === 'string' ? target.prProvider : ''
  const repository = typeof target?.repository === 'string' ? target.repository : ''
  const buildCommand = typeof target?.buildCommand === 'string' ? target.buildCommand : ''
  const providerRepository = typeof target?.providerRepository === 'string' ? target.providerRepository : ''
  const tokenSecretRef = typeof target?.tokenSecretRef === 'string' ? target.tokenSecretRef : ''
  const providerNeedsCredentials = provider === 'github' || provider === 'gitlab'

  const items: ReadinessItem[] = [
    selectionGate(evidence, 'Maker'),
    approvedRevisionGate(evidence, 'Checker'),
    goldenEvidenceGate(evidence, 'Checker'),
    {
      id: 'site-profile',
      label: 'A Mode-B site profile revision is configured',
      satisfied: Boolean(profile),
      detail: profile
        ? `Profile r${profile.revision} · ${profile.contentHash.slice(0, 12)}`
        : 'No site profile revision declares Mode-B delivery. Mode A stays available for this site.',
      owner: 'Platform admin',
      remediationLabel: 'Open Sites',
      remediationTo: '/sites',
    },
    {
      id: 'target-binding',
      label: 'The profile pins a target repository and build command',
      satisfied: Boolean(target && repository && buildCommand),
      detail: target && repository && buildCommand
        ? `${repository} · ${buildCommand}`
        : 'The Mode-B profile must pin the target repository seam, generated paths and an authoritative build command.',
      owner: 'Delivery owner',
      remediationLabel: 'Open Sites',
      remediationTo: '/sites',
    },
    {
      id: 'credentials',
      label: 'Provider credentials resolve from a secret reference',
      satisfied: Boolean(target) && (!providerNeedsCredentials || Boolean(providerRepository && tokenSecretRef)),
      detail: !target
        ? 'No target delivery configuration is present on the profile.'
        : providerNeedsCredentials
          ? providerRepository && tokenSecretRef
            ? `${provider} · ${providerRepository} · credentials from ${tokenSecretRef}`
            : `${provider} delivery requires providerRepository and a tokenSecretRef. Tokens are never stored in the profile.`
          : `Provider ${provider || 'local'} does not require remote credentials.`,
      owner: 'Delivery owner',
      remediationLabel: 'Open Sites',
      remediationTo: '/sites',
    },
  ]
  return finalize('B', items)
}

function finalize(target: 'A' | 'B', items: ReadinessItem[]): TargetGates {
  const blockers = items.filter((item) => !item.satisfied)
  return { target, items, ready: blockers.length === 0, blockers }
}

/** Single-sentence reason attached to a disabled primary action. */
export function blockedReason(gates: TargetGates): string {
  if (gates.ready) return ''
  const [first, ...rest] = gates.blockers
  const suffix = rest.length ? ` (+${rest.length} more)` : ''
  return `Blocked: ${first.label.toLowerCase()} — ${first.owner} owns this${suffix}.`
}
