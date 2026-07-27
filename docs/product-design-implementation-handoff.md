# Product Design Implementation Handoff

> Date: 2026-07-26  
> Intended implementer: Claude or another coding agent  
> Source material: `prd.md`, the active `F-*` roadmap at the top of
> `IMPLEMENTATION_PLAN.md`, `architecture.md`, and `backlog.md`

## 1. Objective

Improve the current Rule Platform experience without shrinking customer-accepted
product scope.

The UI should make one governed change easy to resume and complete while preserving
the accepted breadth of:

- Mode A and Mode B;
- GitHub and GitLab;
- restricted DMN/DRL;
- stored-object and HTML validation sources;
- the existing restricted source/target adapters.

Do not remove, disable, or move these capabilities into a “rejected,” “legacy,” or
“historical only” area solely because the active implementation milestone uses the
Java → GitHub PR flow.

## 2. Product context that governs implementation

Customer acceptance, implementation, verification, and current priority are
different facts:

| Dimension | Meaning | Example |
|---|---|---|
| Customer accepted | The capability belongs in the agreed product surface | Mode A, GitLab, restricted DMN/DRL |
| Implemented | A working code path exists | Restricted adapter or provider seam |
| Verified | Evidence proves a specific contract at a named tier | Synthetic, local, dummy-repository, cloud-DB, or real-site |
| Current milestone | The path currently selected to prove end-to-end value | Small Java repository → GitHub PR |

Never turn “not the current milestone” into “not accepted.” Never turn “accepted”
or “implemented” into “production ready.”

The Canonical Decision Package is the governed product source of truth. Restricted
Rule IR is compiled from it for deterministic execution and generation. JDM, DMN,
Java, reports, and generated tests are derived artifacts.

## 3. North star

### Product-level north star

Elapsed time from a requested business-policy change to an independently approved,
tested, auditable delivery unit at the selected target boundary:

- Mode A: an authoritative, validated publication record;
- Mode B: a pushed, reviewable pull/merge request with authoritative generated and
  target-test evidence.

### Current proving milestone

Elapsed time from a requested Java rule change to a mergeable, tested, auditable
GitHub pull request through one unrelated small public repository.

This milestone is a measurable proxy and implementation focus, not the boundary of
the accepted product.

### Timestamps to retain

Use real workflow events rather than client-only analytics:

1. change requested;
2. source pinned;
3. first useful candidate ready;
4. evidence review completed;
5. first business edit saved;
6. scenarios ready;
7. submitted;
8. independently approved;
9. authoritative tests passed;
10. publication or remote PR/MR verified.

Also record time spent blocked and the role/configuration responsible. Establish
baseline values from the first real rehearsal; do not invent percentage-improvement
or latency targets.

## 4. Valuable findings to implement

### P0 — Unique governed-change selection and fail-closed release actions

On the live site, Overview reports 260 decisions. Test suites and Releases load only
the first 100 and label many distinct records with the same decision name and
revision. Users cannot reliably select the intended artifact, and 160 decisions are
not reachable from those controls.

Replace native mega-selects with a searchable, paginated picker keyed by stable
decision identity. Show name, short key, status, revision, source/product/flow, and
current evidence readiness. Carry that selection through deep links across the
workflow.

Releases currently enables `Create publication` and `Start delivery` whenever a
decision key exists, even when the selected decision is DRAFT and its readiness
chips are red. Disable each action from authoritative target-specific prerequisites
and show the missing gate, owner, and remediation link. Keep backend rejection in
place as defense in depth.

Backlog: `B-008`.

### P0 — Truthful request states

Current behavior can show `0`, “No imports,” or “Review queue is clear” while the
request failed. Introduce explicit `idle | loading | ready | empty | error | stale`
states. Empty and zero are valid only after a successful response. Consolidate
duplicate errors and make workspace/site unavailability explicit.

Backlog: `B-007`.

### P0 — Capability hierarchy without capability removal

Keep every accepted source and target available. Add enough context to distinguish:

- recommended next action for the active change;
- customer-accepted capability;
- implementation/configuration availability;
- verification tier and latest evidence;
- current milestone.

Avoid a flat adapter catalog where all choices appear equally ready, equally proven,
and equally relevant. Avoid hiding accepted paths merely to simplify the screen.

Backlog: `B-006`.

### P0 — URL-first Java onboarding

The normal Java flow should start with a GitHub URL. Repository alias, revision,
subpath, class, and method should be derived, optional advanced constraints, or
selected from an evidence-backed shortlist. Fix the 1280 px form/history overlap
and explain why the primary action is blocked.

Backlog: `B-001`.

### P1 — Evidence-centered review

Review one candidate/decision with three concepts visible together:

1. business-readable proposal;
2. exact source/test evidence with hashes;
3. assumptions, unresolved fragments, and alternative interpretations.

Preserve place when opening evidence and require a disposition for unresolved
fragments before promotion.

For Import history, add pinned commit/scope, evidence hash, candidate and unresolved
counts, failure class, and the valid next action. Default Review queue to actionable
OPEN work for the active change; keep historical dispositions filterable.

Backlog: `B-102`, `B-103`.

### P1 — Clear maker/checker responsibility

The global development identity and the Studio’s editable Maker/Checker fields
currently create two actor models. Use one active identity and show:

- what this actor may do now;
- which actor/role owns the next action;
- why the current actor cannot approve their own change;
- package/revision/lifecycle status, blockers, and unsaved state.

Do not weaken backend maker-checker enforcement.

Backlog: `B-105`.

### P1 — Action-oriented Overview

Make “Active changes” the primary Overview object. For each change show source,
current stage, owner/required actor, blocker, elapsed time, last meaningful event,
verification tier, and one valid next action. Keep infrastructure/job counters
secondary and never mix failed requests with real product counts.

Backlog: `B-108`.

### P1 — Release readiness instead of ambiguous disabled buttons

For the selected target path, show a readiness checklist with each prerequisite,
its evidence, owner, and remediation link. Preserve Mode A and Mode B selection
where allowed by the site profile. A disabled action must explain the missing gate.

Relevant backlog: `B-003`, `B-004`, `B-108`.

### P1 — Actionable failed-job diagnostics

The live Overview reports 10 failed jobs, but Operations exposes no detail or
recovery path. Add a job detail surface with stage timeline, full IDs, affected
governed change, attempt history, redacted terminal reason, retry classification,
and a safe next action. Link failed imports back to their preserved configuration.

Backlog: `B-109`.

### P1 — Responsive and accessibility acceptance

Fix:

- the 1280 px Java-import form overlap;
- horizontally truncated mobile landing navigation;
- blank/chevron-only workspace and site context on mobile;
- stepper labels disappearing on mobile.

Test keyboard/focus order, GoRules interaction, state-change announcements, high
contrast, screen reader behavior, 200% zoom, and populated/error/empty states.

Backlog: `B-107`.

### P2 — Editor loading cost

The current production build includes an approximately 4.2 MB minified editor
chunk and 1.7 MB WASM asset. Measure time-to-edit before optimizing. Defer editor
and WASM initialization until required if measurements prove value; do not replace
the accepted GoRules editing experience without equivalent UX and regression proof.

Backlog: `B-301`.

## 5. Suggested implementation order

1. Make governed-change selection unique and release actions fail closed.
2. Introduce truthful request-state primitives and tests.
3. Add accepted/implemented/verified/current-milestone hierarchy without removing
   capabilities.
4. Make the Java import path URL-first and repair desktop/mobile layout.
5. Add Active changes and next-action logic to Overview.
6. Unify actor responsibility and evidence review around one governed change.
7. Add target-specific release readiness and failed-job diagnostics.
8. Complete responsive, keyboard, screen-reader, zoom, and error-state acceptance.
9. Measure and then optimize editor load.

Keep each pass narrow enough to verify. Do not mix a product-state refactor with
backend governance changes unless the UI cannot represent an existing authoritative
state.

## 6. Likely UI touchpoints

- `ui/src/components/AppShell.vue`
- `ui/src/pages/OverviewPage.vue`
- `ui/src/pages/ImportsPage.vue`
- `ui/src/pages/ReviewQueuePage.vue`
- `ui/src/pages/CanonicalStudioPage.vue`
- `ui/src/pages/TestSuitesPage.vue`
- `ui/src/pages/ReleasesPage.vue`
- `ui/src/content/guide.ts`
- `ui/src/content/docs.ts`
- `ui/src/pages/LandingPage.vue`
- `ui/src/styles/polish.css`
- `ui/src/styles/guide.css`
- `ui/e2e/*.spec.ts`

Inspect the existing dirty worktree before editing and preserve unrelated user
changes. Do not reset, clean, stash, or broadly rewrite the current UI.

## 7. Evidence and current limits

Audit screenshots:

`output/product-audit-2026-07-26/01-landing.png` through
`output/product-audit-2026-07-26/10-imports-mobile.png`.

The audit covered landing, Overview, Imports, Review queue, Canonical Studio, Test
suites, Releases, and mobile states. Cloud PostgreSQL timed out during the audit, so
the screenshots prove real degraded-state behavior and layout, not a populated
candidate → approval → publication/PR journey.

Populated live-audit screenshots:

`output/product-audit-2026-07-26-live/01-overview-desktop.jpg` through
`output/product-audit-2026-07-26-live/12-imports-mobile-390.jpg`.

For the live run, the scheduled RDS instance was started, PostgreSQL 17.9 responded,
and Alembic `0009_candidate_package_promotion` matched head. API and UI ran without
a worker, migration, or write action. The populated audit covered Overview, latest
Import evidence, Review queue, Canonical Studio, Decisions, Test suites, Releases,
Operations, and the mobile Imports entry state.

Live data exposed 260 decisions, 13 items awaiting review, and 10 failed jobs. The
most important new evidence is:

- decision identity becomes ambiguous at real corpus size;
- Test suites and Releases silently stop at 100 decisions;
- release CTAs remain active when readiness checks fail;
- failed jobs have no diagnostic/recovery affordance;
- evidence and next action are fragmented rather than attached to one governed
  change.

Current verification signal at handoff:

- Vitest: 20 passed;
- production UI build: passed;
- Playwright: 5 of 8 passed;
- two Overview tests still expected four stages while the UI renders five;
- the Korean mobile workflow test timed out locating Imports.

## 8. Required verification

From the repository root:

```powershell
pnpm.cmd --dir ui test --run
pnpm.cmd --dir ui build
pnpm.cmd --dir ui test:e2e
git diff --check
```

Add deterministic mocked coverage for populated, loading, empty, error, partial,
and stale states. Browser acceptance should cover the real five-step workflow at
390, 768, 1024, 1280, and 1440 px, plus 200% zoom.

Do not run destructive database tests against the shared cloud `brp` database.
Keep the existing `*_test`/isolated-schema safety fuse intact.

## 9. Completion boundary

This handoff is complete when:

- accepted capabilities remain discoverable and functional;
- the current next action is obvious for maker, checker, and delivery owner;
- capability/evidence status is truthful;
- backend errors never become false zero/empty claims;
- the Java → GitHub PR milestone is easier to complete and measure;
- all affected unit/build/e2e checks pass;
- claims remain labelled by evidence tier.
