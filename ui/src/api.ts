export type DecisionSummary = {
  id?: string
  siteId?: string
  decisionKey: string
  name: string
  productKey?: string | null
  flowKey?: string | null
  latestRevision: number
  latestStatus: string
  owner?: string
  updatedAt?: string
}

export type PlatformContext = {
  workspaces: Array<{ id: string; key: string; name: string }>
  sites: Array<{ id: string; workspaceId: string; key: string; name: string; status: string; defaultLocale: string; timezone: string }>
  authentication: string
  productionBlocked: boolean
}

export type Page<T> = { items: T[]; page: number; pageSize: number; total: number; pages: number }
export type JobRecord = { id: string; siteId: string; type: string; status: string; progress: number; attempts: number; maxAttempts: number; cancelRequested: boolean; errorCode?: string; errorDetail?: string; result?: Record<string, unknown>; correlationId: string; createdBy: string; createdAt: string; startedAt?: string; finishedAt?: string }
export type ImportRun = { id: string; siteId: string; jobId: string; adapter: string; sourceName: string; sourceRevision: string; status: string; progress: number; candidateCount?: number; reviewCount?: number; createdBy: string; createdAt: string; candidates?: Candidate[] }
export type Candidate = { id: string; decisionKey: string; name: string; status: string; content: Record<string, unknown>; sourceSnapshot: Record<string, unknown>; diagnostics: Array<Record<string, unknown>>; promotedRevisionId?: string; promotedPackageRevisionId?: string }
export type GoldenSuite = { id: string; revision: number; status: string; contentHash: string; caseCount: number; cases: Array<{ id: string; caseKey: string; input: Record<string, unknown>; expected: unknown; provenance: Record<string, unknown> }>; createdBy: string; createdAt: string }
export type SiteProfile = { id: string; siteId: string; revision: number; contentHash: string; document: Record<string, unknown>; createdBy: string; createdAt: string }
export type LookupSnapshot = { id: string; name: string; contentHash: string; rowCount: number; source: Record<string, unknown>; approved: boolean; createdAt: string }
export type ModeAPublication = { id: number; action: string; channel: string; decisionRevision: number; suiteRevision: number; artifactHash: string; previousPublicationId?: number; sourcePublicationId?: number; createdAt: string }
export type ModeBDelivery = { id: string; jobId: string; decisionKey: string; decisionRevision: number; provider: string; status: string; branch: string; externalUrl?: string; evidence: Record<string, unknown>; createdAt: string }
export type CanonicalPackageSummary = { id: string; siteId: string; packageKey: string; name: string; latestRevision: number; latestStatus: string; contentHash: string; updatedAt: string }
export type CanonicalPackageRevision = {
  id: string
  packageKey: string
  revision: number
  status: string
  contentHash: string
  effectiveFrom: string
  effectiveTo?: string | null
  createdBy: string
  submittedBy?: string | null
  approvedBy?: string | null
  package: Record<string, unknown> & {
    packageId: string
    packageName: string
    vocabulary: Array<{ key: string; label: string; type: string; role: 'INPUT' | 'OUTPUT'; sourcePath?: string }>
    decisions: Array<{
      decisionId: string
      name: string
      hitPolicy: 'FIRST' | 'UNIQUE' | 'COLLECT'
      inputFields: string[]
      outputFields: string[]
      rows: Array<{ rowId: string; conditions: Array<{ field: string; operator: string; value?: unknown }>; outcomes: Record<string, unknown>; evidenceIds?: string[]; confidence?: number; notes?: string }>
      defaultOutcome?: Record<string, unknown>
    }>
    businessScenarios: Array<{ scenarioId: string; name: string; inputs: Record<string, unknown>; expected: Record<string, unknown>; evidenceIds?: string[] }>
    evidence: Array<{ evidenceId: string; summary: string; sourceReference: Record<string, unknown> }>
  }
  compiledDecisions: Array<Record<string, unknown>>
}
export type DiscoveredTable = { schemaName: string; table: string; kind: string; columns: Array<{ name: string; databaseType: string; nullable: boolean; ordinal: number }> }

export type Revision = {
  envelope: {
    decisionKey: string
    revision: number
    lifecycleStatus: string
    contentHash: string
    effectiveFrom: string
    effectiveTo: string | null
    createdBy: string
    submittedBy: string | null
    approvedBy: string | null
  }
  content: Record<string, unknown> & {
    decisionName: string
    inputs?: Array<{ name: string; type: 'boolean' | 'integer' | 'decimal' | 'string' | 'date'; sourcePath?: string; required?: boolean }>
    outputs?: Array<{ name: string; type: 'boolean' | 'integer' | 'decimal' | 'string' | 'date' }>
    rules: Array<Record<string, unknown>>
  }
}

export type AuditEvent = {
  id: number
  actor: string
  action: string
  fromStatus: string
  toStatus: string
  at: string
}

export type OrchestrationCatalog = {
  evidenceLabel: string
  persistent: boolean
  adapters: string[]
  generators: string[]
  hostInventory: Record<string, boolean>
  boundaries: string[]
}

export type ExtractionResponse = {
  evidenceLabel: string
  persistent: boolean
  batch: {
    adapter: string
    decisions: Array<{
      decisionKey: string
      content: Record<string, unknown> & { decisionName?: string }
    }>
    unmappable: Array<{
      reasonCode: string
      rawFragment: string
      provenance: Record<string, unknown>
    }>
    diagnostics: Array<{ level: string; code: string; message: string }>
    sourceSnapshot: { contentHash: string; revision: string }
  }
}

export type GenerationResponse = {
  generator: string
  evidenceLabel: string
  persistent: boolean
  authoritative: boolean
  path: string
  content: string
  contentHash: string
  compileEvidence?: { status: string; detail: string; sdkVersion?: string }
}

export class BrpApi {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init)
    if (!response.ok) {
      const problem = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(problem.detail ?? `Request failed: ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  context() { return this.request<PlatformContext>('/api/v1/context') }
  overview(siteId: string) { return this.request<{ decisions: number; openReviews: number; activeJobs: number; failedJobs: number }>(`/api/v1/overview?site_id=${encodeURIComponent(siteId)}`) }
  decisionPage(siteId: string, options: { q?: string; status?: string; product?: string; flow?: string; page?: number; pageSize?: number } = {}) {
    const query = new URLSearchParams({ site_id: siteId, page: String(options.page ?? 1), page_size: String(options.pageSize ?? 25) })
    for (const key of ['q', 'status', 'product', 'flow'] as const) if (options[key]) query.set(key, options[key]!)
    return this.request<Page<DecisionSummary>>(`/api/v1/decisions?${query}`)
  }
  decisionV1(siteId: string, key: string, revision?: number) {
    const query = new URLSearchParams({ site_id: siteId })
    if (revision) query.set('revision', String(revision))
    return this.request<Revision>(`/api/v1/decisions/${encodeURIComponent(key)}?${query}`)
  }
  decisionRevisions(siteId: string, key: string) { return this.request<Revision[]>(`/api/v1/decisions/${encodeURIComponent(key)}/revisions?site_id=${encodeURIComponent(siteId)}`) }
  createDecisionRevision(siteId: string, key: string, content: Record<string, unknown>, baseRevision: number, effectiveFrom: string, actor: string) {
    return this.request<Revision>(`/api/v1/decisions/${encodeURIComponent(key)}/revisions?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor, 'If-Match': `"${baseRevision}"` }, body: JSON.stringify({ content, baseRevision, effectiveFrom }) })
  }
  transitionDecision(siteId: string, key: string, revision: number, action: 'submit' | 'approve' | 'reject' | 'retire', actor: string, reason?: string) { return this.request<Revision>(`/api/v1/decisions/${encodeURIComponent(key)}/revisions/${revision}/${action}?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ reason }) }) }
  jobs(siteId: string) { return this.request<JobRecord[]>(`/api/v1/jobs?site_id=${encodeURIComponent(siteId)}`) }
  cancelJob(siteId: string, jobId: string, actor: string) { return this.request<JobRecord>(`/api/v1/jobs/${jobId}/cancel?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'X-BRP-Actor': actor } }) }
  importRuns(siteId: string) { return this.request<ImportRun[]>(`/api/v1/import-runs?site_id=${encodeURIComponent(siteId)}`) }
  importRun(siteId: string, runId: string) { return this.request<ImportRun>(`/api/v1/import-runs/${runId}?site_id=${encodeURIComponent(siteId)}`) }
  createImport(payload: Record<string, unknown>, actor: string) { return this.request<ImportRun>('/api/v1/import-runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify(payload) }) }
  preflightImport(payload: Record<string, unknown>) { return this.request<Record<string, unknown>>('/api/v1/import-runs/preflight', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }) }
  promoteCandidate(candidateId: string, payload: Record<string, unknown>, actor: string) { return this.request<Revision>(`/api/v1/candidates/${candidateId}/promote`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify(payload) }) }
  promoteCanonicalCandidate(candidateId: string, payload: Record<string, unknown>, actor: string) { return this.request<CanonicalPackageRevision>(`/api/v1/candidates/${candidateId}/promote-package`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor, 'X-BRP-Roles': 'maker' }, body: JSON.stringify(payload) }) }
  reviewItems(siteId: string) { return this.request<Array<Record<string, unknown>>>(`/api/v1/review-items?site_id=${encodeURIComponent(siteId)}`) }
  disposeReviews(siteId: string, dispositions: Array<{ itemId: string; status: string; reason?: string }>, actor: string) { return this.request<Array<Record<string, unknown>>>(`/api/v1/review-items/dispositions?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ dispositions }) }) }
  siteProfiles(siteId: string) { return this.request<SiteProfile[]>(`/api/v1/sites/${siteId}/profiles`) }
  createSiteProfile(siteId: string, document: Record<string, unknown>, actor: string) { return this.request<SiteProfile>(`/api/v1/sites/${siteId}/profiles`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ document }) }) }
  goldenSuites(siteId: string, key: string) { return this.request<GoldenSuite[]>(`/api/v1/golden-suites/${encodeURIComponent(key)}?site_id=${encodeURIComponent(siteId)}`) }
  createGoldenSuite(siteId: string, key: string, cases: Array<Record<string, unknown>>, lookupSnapshotHashes: string[], actor: string) { return this.request<GoldenSuite>(`/api/v1/golden-suites/${encodeURIComponent(key)}/revisions?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ cases, lookupSnapshotHashes }) }) }
  lookupSnapshots(siteId: string) { return this.request<LookupSnapshot[]>(`/api/v1/lookup-snapshots?site_id=${encodeURIComponent(siteId)}`) }
  createLookupSnapshot(siteId: string, payload: Record<string, unknown>, actor: string) { return this.request<LookupSnapshot>(`/api/v1/lookup-snapshots?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify(payload) }) }
  transitionGoldenSuite(siteId: string, key: string, revision: number, action: 'submit' | 'approve', actor: string) { return this.request<GoldenSuite>(`/api/v1/golden-suites/${encodeURIComponent(key)}/revisions/${revision}/${action}?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'X-BRP-Actor': actor } }) }
  runGoldenSuite(siteId: string, key: string, decisionRevision: number, suiteRevision: number, actor: string) { return this.request<JobRecord>(`/api/v1/golden-runs?decision_key=${encodeURIComponent(key)}&site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ decisionRevision, suiteRevision }) }) }
  modeAHistory(siteId: string, key: string) { return this.request<ModeAPublication[]>(`/api/v1/releases/mode-a/${encodeURIComponent(key)}?site_id=${encodeURIComponent(siteId)}`) }
  publishModeA(siteId: string, key: string, revision: number, suiteRevision: number, actor: string) { return this.request<JobRecord>(`/api/v1/releases/mode-a/${encodeURIComponent(key)}/publish?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ revision, suiteRevision, channel: 'production' }) }) }
  rollbackModeA(siteId: string, key: string, targetPublicationId: number, actor: string) { return this.request<JobRecord>(`/api/v1/releases/mode-a/${encodeURIComponent(key)}/rollback?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ targetPublicationId, channel: 'production' }) }) }
  modeBHistory(siteId: string) { return this.request<ModeBDelivery[]>(`/api/v1/releases/mode-b?site_id=${encodeURIComponent(siteId)}`) }
  deliverModeB(siteId: string, key: string, revision: number, profileRevision: number, actor: string) { return this.request<JobRecord>(`/api/v1/releases/mode-b/${encodeURIComponent(key)}/deliver?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor }, body: JSON.stringify({ revision, profileRevision }) }) }
  canonicalPackages(siteId: string) { return this.request<CanonicalPackageSummary[]>(`/api/v1/canonical-packages?site_id=${encodeURIComponent(siteId)}`) }
  canonicalPackage(siteId: string, key: string, revision?: number) {
    const query = new URLSearchParams({ site_id: siteId })
    if (revision) query.set('revision', String(revision))
    return this.request<CanonicalPackageRevision>(`/api/v1/canonical-packages/${encodeURIComponent(key)}?${query}`)
  }
  reviseCanonicalPackage(siteId: string, key: string, revision: number, document: Record<string, unknown>, actor: string, reason: string) {
    const at = new Date().toISOString()
    return this.request<CanonicalPackageRevision>(`/api/v1/canonical-packages/${encodeURIComponent(key)}/revisions?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor, 'X-BRP-Roles': 'maker', 'If-Match': `"${revision}"` }, body: JSON.stringify({ package: document, baseRevision: revision, effectiveFrom: at, authoredAt: at, reason }) })
  }
  transitionCanonicalPackage(siteId: string, key: string, revision: number, action: 'submit' | 'approve' | 'reject', actor: string, reason?: string) {
    const role = action === 'submit' ? 'maker' : 'checker'
    return this.request<CanonicalPackageRevision>(`/api/v1/canonical-packages/${encodeURIComponent(key)}/${revision}/${action}?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor, 'X-BRP-Roles': role }, body: JSON.stringify({ reason }) })
  }
  canonicalPackageDiff(siteId: string, key: string, from: number, to: number) { return this.request<Record<string, unknown>>(`/api/v1/canonical-packages/${encodeURIComponent(key)}/diff?site_id=${encodeURIComponent(siteId)}&fromRevision=${from}&toRevision=${to}`) }
  discoverDbTables(connectionAlias: string, schemaName: string, actor: string) {
    const query = new URLSearchParams({ connection_alias: connectionAlias, schema_name: schemaName })
    return this.request<DiscoveredTable[]>(`/api/v1/db-sources/tables?${query}`, { headers: { 'X-BRP-Actor': actor, 'X-BRP-Roles': 'maker' } })
  }
  importDbTable(siteId: string, mapping: Record<string, unknown>, actor: string) {
    const at = new Date().toISOString()
    return this.request<CanonicalPackageRevision>(`/api/v1/db-sources/import?site_id=${encodeURIComponent(siteId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor, 'X-BRP-Roles': 'maker' }, body: JSON.stringify({ mapping, effectiveFrom: at, authoredAt: at, reason: 'Guided PostgreSQL table import' }) })
  }

  decisions() {
    return this.request<DecisionSummary[]>('/decisions')
  }

  decision(key: string, revision?: number) {
    return this.request<Revision>(`/decisions/${key}${revision ? `?revision=${revision}` : ''}`)
  }

  audit(key: string) {
    return this.request<AuditEvent[]>(`/decisions/${key}/audit`)
  }

  diff(key: string, from: number, to: number) {
    return this.request<Record<string, unknown>>(`/decisions/${key}/diff?from=${from}&to=${to}`)
  }

  reviewQueue() {
    return this.request<Array<Record<string, unknown>>>('/review-queue')
  }

  goldenStatus(key: string) {
    return this.request<Array<Record<string, unknown>>>(`/golden-suites/${key}`)
  }

  transition(key: string, revision: number, action: string, actor: string, reason?: string) {
    return this.request<Revision>(`/decisions/${key}/revisions/${revision}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor },
      body: action === 'reject' || action === 'retire' ? JSON.stringify({ reason }) : undefined,
    })
  }

  addRevision(key: string, content: Record<string, unknown>, actor: string, effectiveFrom: string) {
    return this.request<Revision>(`/decisions/${key}/revisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor },
      body: JSON.stringify({ content, effectiveFrom }),
    })
  }

  preview(key: string, revision: number, input: Record<string, unknown>) {
    return this.request<Record<string, unknown>>(`/preview/${key}?revision=${revision}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input, lookupSnapshots: {} }),
    })
  }

  orchestrationCatalog() {
    return this.request<OrchestrationCatalog>('/orchestration/catalog')
  }

  orchestrationExtract(payload: Record<string, unknown>, actor: string) {
    return this.request<ExtractionResponse>('/orchestration/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor },
      body: JSON.stringify(payload),
    })
  }

  orchestrationGenerate(
    generator: string,
    content: Record<string, unknown>,
    actor: string,
    csharpNamespace: string,
  ) {
    return this.request<GenerationResponse>('/orchestration/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BRP-Actor': actor },
      body: JSON.stringify({ generator, content, csharpNamespace }),
    })
  }

  orchestrationPreflight(
    profiles: Array<Record<string, unknown>>,
    inventory: Record<string, boolean>,
  ) {
    return this.request<Record<string, unknown>>('/orchestration/preflight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profiles, inventory }),
    })
  }
}
