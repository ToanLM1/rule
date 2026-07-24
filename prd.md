# Canonical Business Rules Management & Delivery Platform
## Product Requirements Description

> **Status (2026-07-23): small-first reset.** This is a separate application from the Telecom Business Knowledge Assistant. The repository already contains substantial governance, adapter, generation, and delivery plumbing proven mainly with synthetic fixtures. It has **not** yet proved useful extraction from an arbitrary small Java repository, a genuinely non-technical authoring experience, or a real repository round trip. Those gaps are now the active product priority. Do not infer production readiness, large-repository requirements, or multi-site scale from the existing infrastructure.

## 1. Product Summary

The product lets an organization manage business decisions as governed data and deliver approved changes back into software safely.

Its core value is not static analysis by itself. The core is a controlled loop in which:

1. existing rules are bootstrapped from a small source repository or database;
2. a business user can understand and edit them without editing JSON or Java;
3. reviewers approve a version with source evidence and business scenarios;
4. the platform deterministically generates Java and tests;
5. the generated change is pushed as a reviewable branch and pull request.

The first useful proof is one public, writable dummy Java repository. A small PostgreSQL rule/config table is the next vertical slice. Scale work starts only after a real input demonstrates a real scale problem.

## 2. Product Boundary

- This application does not depend on the knowledge assistant's chat, RAG ingestion, vector retrieval, Neptune schema, or citation API.
- Git repositories and databases are source systems for bootstrap and reconciliation. PostgreSQL is also the platform system of record.
- Mining is an onboarding and reconciliation assistant. It produces evidence-backed candidates; it is not the canonical model and never auto-approves changes.
- The governed canonical package is the product source of truth. Java, JDM, DMN, reports, and generated tests are derived artifacts.
- Merge and production deployment remain controlled by the target repository and its CI/CD. For the MVP, “deploy back” ends at a pushed branch and reviewable pull request with passing tests.

## 3. Users And Outcomes

### 3.1 Business author

Can read and edit vocabulary, decision-table rows, lookup references, effective dates, and business scenarios through guided forms. Raw JSON is an advanced diagnostic view, not the normal authoring surface.

### 3.2 Reviewer / approver

Can compare revisions, inspect exact source evidence and assumptions, run scenarios, and approve or reject a change. Extracted candidates are never approved automatically, and maker-checker separation remains enforced.

### 3.3 Engineer / delivery owner

Can configure the target repository seam, generate deterministic Java and JUnit artifacts, run target tests, inspect the diff, and push a branch/create a pull request. The target repository remains the merge and deployment authority.

### 3.4 Product success measure

The initial north-star metric is **elapsed time from a requested business-policy change to a mergeable, tested, auditable pull request**. Baseline and target values must be measured from the first real vertical slice; this PRD does not invent percentage savings or scale targets without evidence.

## 4. Domain Model

### 4.1 Canonical Decision Package

The user-facing governed object is a **Canonical Decision Package**, containing:

- domain vocabulary with business labels, types, and optional technical bindings;
- one or more decision tables with readable conditions and outcomes;
- lookup definitions and immutable test snapshots where needed;
- deterministic composition between decisions;
- effective dates and lifecycle/governance metadata;
- business scenarios with inputs and expected outcomes;
- source evidence, assumptions, unresolved items, and extraction confidence;
- target bindings needed to compile the package for a Java repository.

### 4.2 Executable Rule IR

The existing restricted Canonical Rule IR remains the vendor-neutral executable representation. The platform compiles a validated Decision Package into IR. Business users do not need to understand IR operands, repository envelopes, JDM, or generated Java.

The separation is intentional:

- the Decision Package optimizes for safe business authoring and review;
- the Rule IR optimizes for deterministic validation and generation;
- compilation errors are shown as actionable field/table diagnostics, not raw schema failures.

### 4.3 Evidence Bundle

Every source-derived candidate carries an immutable `EvidenceBundle` with:

- repository URL, pinned commit, configured subpath, and entry-point hypothesis;
- exact file/range and content hashes for supporting source spans;
- inferred inputs, outcomes, rule rows, and technical bindings;
- assumptions, unresolved calls/fragments, and alternative interpretations;
- relevant test locations and any observed test results;
- confidence per extracted field, not one misleading aggregate score;
- analysis tool transcript and escalation recommendation.

Unsupported or ambiguous logic is preserved as a review item. The system must never silently coerce it into an executable rule.

## 5. Functional Requirements

### 5.1 Canonical Studio — active priority

- Display business labels and decision tables as the primary editor.
- Support adding, changing, reordering, and deleting rule rows within the restricted profile.
- Provide guided editors for conditions, outcomes, vocabulary fields, lookups, dates, and scenarios.
- Validate missing values, incompatible types/operators, duplicate or conflicting rows, and unsupported composition before submission.
- Show a human-readable revision diff plus advanced raw JSON on demand.
- Preserve immutable revisions, effective dating, audit history, and maker-checker approval.
- Compile only approved packages to executable Rule IR and derived artifacts.

### 5.2 Small Java repository bootstrap — first vertical slice

The platform accepts a public HTTPS GitHub repository URL, revision, optional repository subpath, and a bounded entry-point hint. It clones without credentials, pins the immutable commit, and runs progressive evidence collection:

1. repository inventory, manifests, `git`, `rg`, and bounded source reads;
2. syntax-aware parsing/query only where text evidence is insufficient;
3. symbol/type/reference tooling only for unresolved dependencies;
4. heavyweight whole-program analysis only after a recorded lightweight failure and explicit escalation decision.

The extractor may use an LLM to form candidates from bounded evidence. LLM output is candidate-only, schema validated, and linked to the Evidence Bundle. Fixed synthetic pattern matching is not acceptable evidence of arbitrary-repository support.

### 5.3 Review and business scenarios

- Promote extracted candidates into editable draft packages without losing their source evidence.
- Let users add or correct vocabulary mappings and business scenarios.
- Run scenarios before submission and authoritative generated-Java tests before delivery.
- Require explicit disposition of unresolved or unmappable fragments.

### 5.4 Deterministic Java delivery — first vertical slice

- Compile an approved package to Rule IR and generate Java plus JUnit tests deterministically.
- Keep a stable, human-reviewed integration seam in the target repository so generated code is actually invoked.
- Run generated golden tests and configured target-repository tests from the delivery branch.
- Produce a manifest containing all behavior-affecting input and output hashes.
- Push a branch and create a pull request when writable GitHub credentials are configured.
- Never auto-merge or claim production deployment. Without a pushed branch and reviewable PR, the external repository full-flow is incomplete.

### 5.5 PostgreSQL table bootstrap — second vertical slice

After the repository flow passes, support one explicitly selected small table or bounded view from a cloud PostgreSQL source:

- use a named, read-only source connection distinct from platform persistence;
- discover and allowlist selected columns; do not accept arbitrary SQL from the model;
- map configured condition/outcome columns deterministically into a draft Decision Package;
- retain table, primary-key/row identity, snapshot/hash, and column mapping evidence;
- pass through the same authoring, approval, generation, test, and pull-request path as repository-derived rules.

Docker PostgreSQL is not required for this flow. Automated destructive tests must still use an isolated test database or schema and must never target the shared cloud database.

### 5.6 Reconciliation

After initial onboarding, a new source commit or selected DB snapshot can be compared with the evidence recorded on the approved package. Drift creates review candidates; it never overwrites authored canonical rules.

## 6. Validation And Authority

- Source extraction is probabilistic and advisory.
- Decision Package validation and Package→IR compilation are deterministic.
- Java generation is deterministic for the same recorded release inputs.
- For the active Mode-B path, compiled generated Java plus target-application tests are authoritative.
- Preview engines may assist users but cannot substitute for generated-Java and target-test evidence.
- Every claim must identify whether its evidence is synthetic, dummy-repository, or real-site evidence.

## 7. First Full-Flow Acceptance

The repository MVP is complete only when one small public Java repository that is not coupled to the checked-in synthetic miner templates can complete all of the following:

1. import by URL and pin an immutable commit;
2. produce useful candidates with exact Evidence Bundles;
3. let a non-technical user correct and edit a decision through the table/form UI;
4. submit and approve it with an audit trail;
5. edit one business rule and add/confirm expected business scenarios;
6. deterministically generate Java and JUnit artifacts;
7. compile and pass generated and configured target-repository tests;
8. prove the edited rule changes the expected target behavior;
9. push a branch and create a reviewable pull request in the writable dummy repository.

A local artifact, synthetic fixture result, advisory preview, or PR-ready diff without a remote branch/PR does not satisfy this acceptance criterion.

The PostgreSQL vertical slice repeats steps 2–9 after importing a selected small cloud table through the bounded read-only adapter.

## 8. Non-Functional Requirements For The Vertical Slice

- **Traceability:** every candidate field links to immutable source evidence.
- **Safety:** candidate-only extraction, explicit review, maker-checker approval, and authoritative tests before delivery.
- **Usability:** the normal authoring path requires no JSON, Java, JDM, or DMN knowledge.
- **Reproducibility:** pinned commits, source hashes, package/IR hashes, generator version, scenario suite, lookup snapshots, and output hashes are recorded.
- **Korean preservation:** Korean business labels and values remain UTF-8 across evidence, storage, generation, diffs, and reports.
- **Secrets:** credentials are referenced through environment or secret configuration and never persisted in profiles, logs, artifacts, or prompts.
- **Local footprint:** API, worker, UI, Git, Java 17, and cloud PostgreSQL are sufficient for MVP development. Docker and a heavyweight analysis service are optional.

## 9. Active Phasing

### Phase 0 — Truthful cloud-local baseline

Run API, worker, and UI locally against the existing cloud PostgreSQL; verify migrations, health, a fresh worker heartbeat, and isolated test safety. Document exact prerequisites and current limitations.

### Phase 1 — Canonical Studio

Deliver business vocabulary, decision-table editing, scenarios, validation, readable diff, and approval without requiring raw JSON.

### Phase 2 — Small public Java repository full-flow

Replace the fixed synthetic miner as the active path with the evidence-driven repository agent. Complete import through pushed branch and pull request, including authoritative Java and target tests and a demonstrated behavior change.

### Phase 3 — Small cloud PostgreSQL table full-flow

Add guided source-table selection and mapping, then reuse the same canonical authoring and Java delivery path.

### Phase 4 — Evidence-triggered expansion only

Consider semantic-heavy analysis, Joern/SootUp, Mode A, DMN/DRL, stored procedures, UI mining, other languages/DBMSs, multi-site controls, containers, OIDC, performance engineering, or high-availability operations only when a real use case is blocked and the smallest sufficient addition is identified.

No repository-size threshold, throughput target, customer count, or infrastructure topology is assumed in advance.

## 10. Current Implementation Truth

The repository now includes Canonical Decision Package persistence/compiler/governance, a business-facing Canonical Studio, immutable Rule IR, durable jobs, public-repository pinning and bounded evidence tools, Java generation, golden-test generation, verified Git delivery seams, guided PostgreSQL mapping, and several restricted import/export proofs.

The current limitations are product-critical:

- the lightweight Java agent is wired as the public-repository path and has completed a live Groq import, deterministic compilation and source review for an unrelated stateless discount repo; a GildedRose trial exposed that v1 cannot yet represent one concept as both current-state input and next-state output;
- Canonical Studio supports package decision-table/scenario editing and governance without raw JSON. Decision tables reuse the GoRules JDM Editor through a constrained adapter rather than adopting GoRules BRMS or JDM as canonical truth. Evidence drill-down, revision diff, nested/lookup editing and full accessibility/browser coverage remain incomplete;
- EvidenceBundle is retained inside the immutable candidate snapshot rather than as a first-class durable evidence record;
- guided cloud PostgreSQL discovery/import and package approval work, but a distinct least-privilege source credential and DB-derived Java/PR delivery have not been accepted;
- real remote branch/pull-request delivery has not been accepted end to end against the user's dummy repository;
- completed synthetic and local proofs do not establish real-site accuracy or production readiness.

These are the active gaps. Existing multi-site, engine-import, C#, stored-object, UI-validation, container, and production-hardening work is retained as historical capability but does not outrank them.

## 11. Explicitly Deferred

- automatic merge or production deployment;
- arbitrary-language or arbitrary-DBMS compatibility;
- arbitrary Java/SQL/UI execution or unrestricted expression support;
- Mode-A engine migration and production runtime;
- DMN/DRL/ODM/C# expansion;
- stored-procedure and frontend-validation mining;
- multi-site productization and enterprise tenancy;
- Docker/Kubernetes packaging as an MVP prerequisite;
- OIDC/Internet exposure, high availability, and speculative performance targets;
- heavyweight whole-repository graph analysis without a demonstrated lightweight failure.
