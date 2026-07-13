export type DecisionSummary = {
  decisionKey: string
  name: string
  latestRevision: number
  latestStatus: string
}

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
