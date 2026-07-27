# Product Backlog — Small-First Business Rules Platform

> **Status snapshot: 2026-07-26.** This file is the single reader-facing list of
> unfinished work and demonstrated product gaps. It does not replace the detailed
> acceptance history in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Priorities
> follow the small-first rule: finish one useful repository flow and one small
> PostgreSQL-table flow before scale, enterprise, or heavy-analysis work.
>
> **Customer scope clarification (2026-07-26).** Mode A, Mode B, GitHub/GitLab,
> DMN/DRL, stored-object/HTML and the existing restricted adapters are accepted
> product capabilities. Their presence in the UI is not itself a product gap and
> they must not be removed, disabled, or relabelled as rejected/historical solely
> because the current acceptance milestone prioritizes the Java → GitHub PR flow.
> In this backlog, “not the current vertical-slice priority” means scheduling and
> evidence status, not customer rejection. See
> [docs/product-design-implementation-handoff.md](docs/product-design-implementation-handoff.md)
> for the implementation handoff.

### Product north star and current proving milestone

- **Product north star:** elapsed time from a requested business-policy change to
  an independently approved, tested, auditable delivery unit at the selected
  target boundary. That boundary may be a Mode-A publication or a Mode-B pull/merge
  request, according to the accepted site configuration.
- **Current measurable proving milestone:** elapsed time from a requested Java rule
  change to a mergeable, tested, auditable GitHub pull request through the active
  small-repository vertical slice.
- Measure both from real workflow timestamps. Do not invent improvement percentages,
  latency targets, or production-readiness claims before the first accepted
  rehearsal establishes a baseline.
- Capability breadth, implementation status, customer acceptance, current priority,
  and verification evidence are separate dimensions. The UI must not collapse them
  into one ambiguous “supported” claim.

## 1. What is already real

- Native API, worker, and UI run against cloud PostgreSQL without Docker or Joern.
- A public GitHub repository can be cloned credential-free, pinned to an immutable
  commit, and processed by the lightweight evidence agent.
- Groq GPT-OSS 120B successfully extracted a compiling candidate from the small
  `novoda/dojos` Harry Potter example with exact Java/test evidence.
- Canonical Decision Packages can be stored, edited, submitted, separately approved,
  compiled deterministically to Rule IR, and audited.
- Canonical Studio uses the mature GoRules JDM decision-table editor through a
  constrained adapter; GoRules/JDM is not the platform source of truth.
- Java generation, compile/test gates, deterministic delivery worktrees, remote push,
  and GitHub PR publishing seams have automated coverage.
- A small PostgreSQL table has completed discovery, mapping, package creation,
  submit, and approval on cloud PostgreSQL.

These proofs are useful, but they do **not** yet prove arbitrary-repository
compatibility, a completed remote pull request, or production readiness.

## 2. P0 — Complete the useful repository full flow

### B-001 — URL-only public repository discovery

**Problem.** The UI says “Public GitHub URL”, but the current flow also requires the
user to know a repository alias, revision, optional subpath, Java class, and method.
This is guided entry-point import, not URL-only onboarding.

**Current technical cause.**

- `ui/src/pages/ImportsPage.vue` disables preflight until URL, alias, revision,
  class, and method are all supplied.
- `ImportRunRequest` in `platform/src/brp/api/v1.py` rejects `code-java` requests
  without alias, class, and method.
- Preflight searches for the supplied `class <name>` and `<method>(` and fails when
  neither exact hint is found.
- `LightweightJavaAgent` starts from those matches and reads at most 12 bounded
  source spans plus a small set of related tests. It does not currently discover
  likely business-rule entry points across a repository.

**Implement.**

1. Accept a public GitHub URL plus branch/tag/commit; default revision discovery may
   use the repository's advertised default branch, then pin it to a commit.
2. Run a separate bounded reconnaissance job:
   - inventory manifests and Java source/test roots;
   - identify Maven/Gradle modules;
   - use `rg` and lightweight AST queries to find candidate decision classes,
     condition-heavy methods, enums/constants, tables/maps, and matching tests;
   - return ranked entry-point hypotheses with exact evidence and uncertainty.
3. Show the shortlist in the UI using business-readable summaries. Let the user
   select one or more scopes or refine the subpath; do not require class/method
   knowledge in the normal path.
4. Run the existing evidence extraction separately for each approved scope.
5. Stop with an explicit “no bounded candidate found” result instead of passing the
   whole repository blindly to an LLM.

**Acceptance.**

- Pasting only a small public `github.com/<owner>/<repo>` URL can reach a shortlist
  without hard-coded fixture names.
- URL is the only required field in the normal first step. Repository alias,
  subpath, class, and method are either derived, optional advanced constraints, or
  selected from the returned evidence-backed shortlist.
- The result shows pinned commit, module/subpath, candidate class/method, source/test
  spans, confidence, reason for ranking, and unresolved dependencies.
- A false-positive candidate can be rejected without starting extraction.
- Repository/file/span/token/time limits are enforced and visible.
- Test against at least three unrelated small Java repositories: one stateless
  decision, one state transition, and one repo where no useful rule is found.
- The configure screen does not overlap the import-history panel at 1280 px,
  1024 px, or 200% zoom, and the primary action explains the one missing
  requirement instead of remaining silently disabled.

**Non-goal.** “Accept a URL” must not be advertised as “understands arbitrary Java”.
Repositories without Java, without identifiable rules, with generated/obfuscated
code, or beyond the bounded budget may return an unsupported/review outcome.

### B-002 — Create/configure the writable dummy Java target repository

**Problem.** The public source repository is read-only to this application. A distinct
user-owned repository with a stable integration seam is still missing, so the
platform cannot demonstrate its final push/PR boundary.

**Implement.**

- Use a small public repository owned by the configured GitHub account.
- Add a stable Java façade, baseline business tests, allowlisted generated/test
  paths, Java package, base branch, and pinned Maven or Gradle commands.
- Store credentials only through a secret reference scoped to that repository.

**Acceptance.** A clean pinned clone compiles and its baseline tests exercise the
same façade that generated rules will plug into.

### B-003 — Connect approved packages to authoritative target gates

**Problem.** Compilation, generation, and delivery components exist, but the approved
Canonical Package has not yet been proven against a real target repository seam.

**Implement.**

- Generate Rule IR, Java, JUnit, and a manifest only from an approved package,
  approved scenarios/golden evidence, target configuration, and generator version.
- Compile generated code and run both generated tests and the target repository's
  configured tests inside an isolated delivery worktree.
- Block remote delivery when any authoritative command is unavailable or fails.

**Acceptance.**

- Two reruns produce byte-identical generated artifacts.
- A planted failing business expectation blocks push.
- A business edit changes the expected outcome through the target façade.

### B-004 — Execute a real remote branch and GitHub PR

**Problem.** Remote push/PR publishing is implemented and tested with mocks/local
repositories, but has not run against a writable user-owned remote.

**Acceptance.**

- The branch exists on the configured remote.
- One reviewable PR is created or idempotently reused.
- Independently fetched remote head, PR head/base, commit OID, generated hashes, and
  test evidence all match the release record.
- No token appears in logs; no force-push, auto-merge, or production deployment occurs.

### B-005 — Record the end-to-end repository acceptance rehearsal

Run and record:

```text
public URL → immutable commit → evidence-backed scope/candidate
→ business edit → submit → separate approval
→ deterministic Java/JUnit → generated + target tests
→ remotely pushed branch → reviewable GitHub PR
```

The acceptance record must demonstrate that one business edit changes an expected
outcome. Synthetic fixtures and local-only branches remain regression evidence, not
full-flow acceptance.

### B-006 — Give accepted capabilities a clear product hierarchy

**Customer context.** Mode A, GitLab, DMN/DRL, stored objects, HTML validation, and
the existing restricted adapters have been accepted by the customer. Preserve
their discoverability and working behavior.

**Demonstrated gap.** The landing page, Imports, docs, and Releases do not clearly
separate four different truths:

1. capability accepted by the customer;
2. capability implemented in the product;
3. capability verified with synthetic/local or real-site evidence;
4. capability selected as the current end-to-end proving milestone.

As a result, a first-time user cannot tell which route is the recommended next
action, while an operator cannot tell how strong the evidence is for each accepted
capability. The authority language is also inconsistent: the Canonical Decision
Package is the governed product source of truth, while Rule IR is its deterministic
executable representation.

**Implement.**

- Keep the broad accepted product story and all accepted source/target choices.
- Give the current task one recommended path and primary CTA:
  `public Java URL → evidence → business edit → scenario proof → approval →
  tested GitHub PR`, without presenting other accepted paths as rejected.
- Describe the Canonical Decision Package as the governed source of truth and Rule
  IR as its generated deterministic executable representation.
- Add compact capability status metadata where it changes a decision, such as
  `accepted`, `implemented`, `verified locally`, `verified on customer input`,
  `current milestone`, or `blocked by configuration`. Do not use one “supported”
  badge to imply all of these.
- Let users choose Mode A/Mode B and GitHub/GitLab when the selected site profile
  allows them, while visually emphasizing the next valid action for the active
  change.
- Keep claims bounded: Mode-B Git delivery ends at a pushed reviewable PR/MR; merge
  and downstream deployment remain external. Mode-A publication claims require
  their own authoritative validation evidence.
- Preserve PostgreSQL and other accepted import modes, but use progressive
  disclosure so the default Java task is not buried in a flat adapter catalog.

**Acceptance.** A first-time business author, reviewer, and engineer can each
describe the same active path and authority boundary after viewing the landing,
Overview, Imports, Studio, and Releases screens. They can also find every
customer-accepted capability and distinguish its current verification level without
interpreting “not this milestone” as “not supported.”

### B-007 — Make loading, empty, error, and stale states truthful

**Demonstrated gap.** With the platform database unreachable, Overview showed zero
decisions/jobs and “No imports yet”; Review queue simultaneously showed “Failed to
fetch” and “Review queue is clear”; Studio and Test suites combined request errors
with normal empty-state guidance. These states can turn “unknown” into “none,” which
is especially damaging in a governance product.

**Implement.**

- Model request state explicitly as `idle | loading | ready | empty | error |
  stale`; never derive empty from an array initialized before a successful response.
- Render counts as unavailable rather than `0` when the source request failed.
- Suppress normal empty-state copy and primary workflow actions when their required
  workspace/site context is unavailable.
- Consolidate duplicate connection/page alerts into one scoped message that names
  what is unavailable, preserves any last-known timestamp, and offers a safe retry.
- Give workspace and site selectors an explicit unavailable state instead of
  collapsing to blank controls.

**Acceptance.** Automated route tests cover timeout, offline, 5xx, partial response,
empty success, and stale cached data. No failed request produces a “clear,” “none,”
or numeric-zero claim unless that value came from a successful response.

### B-008 — Make governed artifacts uniquely selectable and gate release actions

**Demonstrated gap on populated cloud data.** The site contains 260 decisions, many
with the same Korean display name and revision. Test suites and Releases currently
load only the first 100 decisions and render each option as `name · revision`.
This makes different decision keys indistinguishable and leaves the other 160
decisions unreachable from those screens. On Releases, a selected DRAFT decision
with no golden evidence still renders active `Create publication` and `Start
delivery` buttons. The click handlers reject missing prerequisites later, but the
UI invites an invalid or unsafe action.

**Implement.**

- Replace native mega-selects with a searchable, paginated governed-change picker.
  Identify each option with business name, lifecycle status, revision, product/flow
  or source, and a short stable decision key. Never rely on name plus revision as a
  unique human label.
- Carry the selected governed change through Overview, Imports, Review, Studio,
  Decisions, Test suites, and Releases using a deep-linkable stable key. Preserve
  selection and context when following `Next` actions.
- Load or search the full site corpus rather than silently truncating to one
  100-item page. State the result scope when a query is partial.
- Compute Mode-A and Mode-B readiness from authoritative prerequisites. Disable
  the action until the selected revision, evidence/suite, site profile, credentials,
  and target-specific gates are valid.
- Render each missing prerequisite as a failed readiness item with its owner and a
  direct remediation link. A red requirement badge must not coexist with an active
  primary action.
- Keep the existing customer-accepted Mode A/Mode B and GitHub/GitLab choices.
  This item changes selection and safety behavior, not accepted scope.

**Acceptance.**

- Any of the 260 current decisions can be found and uniquely identified from Test
  suites and Releases without memorizing an opaque key.
- Two decisions with the same name and revision cannot be confused in display,
  keyboard navigation, URL state, or submitted API payload.
- A DRAFT decision, missing approved golden evidence, missing Mode-B profile, or
  unresolved credential reference cannot start the corresponding release action.
- Unit and browser tests assert both disabled-state reasons and backend rejection;
  the UI guardrail supplements rather than replaces server-side enforcement.

## 3. P1 — Correctness and product usefulness

### B-101 — Represent state transitions without inventing field names

**Demonstrated gap.** GildedRose uses `quality` as both current-state input and
next-state output. Vocabulary v1 gives each key one role, so extraction cannot
faithfully represent the rule without renaming or dropping a condition. The agent
correctly failed closed.

**Implement.**

- Separate business concept identity from value role/binding, for example
  `quality.current` and `quality.next` under one displayed concept, or explicit
  state-versioned bindings.
- Define deterministic compiler, Java generator, scenario, diff, evidence, and
  decision-table behavior for state transitions.
- Do not solve this by model-prompt conventions alone.

**Acceptance.** The GildedRose case compiles and tests with the same business concept
visible to the author, while source evidence distinguishes current and next values.
Existing stateless packages remain byte-stable or migrate explicitly.

### B-102 — Persist EvidenceBundle as a first-class governed record

**Current state.** Complete evidence is embedded inside candidate source snapshots.
This preserves data, but makes evidence lifecycle, querying, reuse, and reconciliation
awkward.

**Acceptance.** Evidence bundles, spans, hashes, field links, assumptions, unresolved
calls, test evidence, tool transcript, and escalation decisions are immutable,
queryable records linked to candidates and canonical revisions.

### B-103 — Finish import recovery and evidence review UX

- Prove retry/cancel/recovery and idempotent promotion against cloud-local jobs.
- Add dedicated evidence drill-down with source span, hash, confidence, assumptions,
  unresolved calls, alternative interpretations, and review disposition.
- Distinguish “provider/quota failure”, “no candidate”, “unsupported semantics”, and
  “user rejected candidate” instead of presenting one generic failure.
- Organize review around one candidate and one decision at a time: business-readable
  proposal, exact source/test evidence, and unresolved/alternative interpretations
  remain visible together while the reviewer accepts, corrects, rejects, or defers.
- Preserve the reviewer’s place when opening a source span, and require a disposition
  for every unresolved fragment before promotion.
- In Import history, show the pinned repository/revision, extraction scope,
  candidate/unresolved counts, evidence hash, failure class, and the valid next
  action. A successful job must be more than a percentage plus a `Promote` button.
- Default Review queue to actionable OPEN work for the active governed change.
  Keep accepted/deferred/rejected history discoverable through filters instead of
  intermixing it with the current queue.

### B-104 — Add targeted lightweight semantic escalation

Add Tree-sitter/AST queries first. Add JavaParser/SymbolSolver, OpenRewrite, or JDT
only for a concrete unresolved question that text search and bounded reads cannot
answer. Record the failed question, selected tier, evidence gained, and uncertainty.
Joern/SootUp remains deferred until a real small case proves lighter tiers insufficient.

### B-105 — Complete Canonical Studio acceptance

Still missing:

- validation-failure UI with cell-addressed diagnostics;
- source evidence drill-down;
- readable revision/semantic diff;
- guided nested-decision and lookup editing;
- component and browser coverage for row/scenario edits, submit, separate approval,
  responsive layouts, keyboard use, and accessibility.
- one consistent actor model: the global development identity and the Studio’s
  editable Maker/Checker fields must not imply that one person can choose both sides
  of maker-checker;
- an explicit task header showing package/revision, current lifecycle state, actor
  responsibility, unsaved state, blockers, and the single next action;
- business-scenario language shared between Studio and Test suites so authors do not
  have to understand two overlapping proof concepts.

Raw IR/JSON remains advanced/read-only and must not enter the standard authoring path.

### B-106 — Establish explicit safe test tiers

Document and automate separate commands for:

1. pure/unit tests with no database;
2. destructive tests against an isolated `*_test` database only;
3. read-only cloud integration smoke;
4. live LLM tests;
5. external writable-GitHub acceptance.

The shared application database must continue to fail closed for destructive pytest.

### B-107 — Pass responsive and accessibility acceptance on the real workflow

**Demonstrated gaps.**

- At 1280×720 the Java-import configure form overlaps and clips fields beneath the
  import-history panel.
- At 390×844 the landing navigation is horizontally truncated; console
  workspace/site controls reduce to unexplained chevrons; the import stepper loses
  its labels.
- At 1280×720 the Decision editor can open wider than the usable content area,
  clipping its left edge and requiring horizontal scrolling to inspect one rule.
- Existing automated accessibility checks cover selected mocked routes and filter
  only critical Axe findings. They do not cover the complete populated workflow,
  error states, evidence inspection, table editing, validation recovery, or
  maker/checker handoff.

**Acceptance.**

- Core screens reflow without clipping or overlapping at 390, 768, 1024, 1280, and
  1440 px, plus browser zoom at 200% and text-only zoom where supported.
- Mobile navigation uses a deliberate menu/overflow pattern; current workspace,
  site, lifecycle step, and active actor remain understandable without relying on
  icon shape or position.
- Every interactive control is reachable and operable by keyboard with visible
  focus, logical order, and no keyboard trap, including the GoRules table and
  evidence/revision panels.
- Loading, validation, save, submit, approval, test, and delivery state changes are
  announced to assistive technology; labels and errors identify the affected field
  or cell.
- Axe checks run across populated, empty, loading, and failed states for all five
  workflow steps, with no critical or serious violations; manual screen-reader and
  high-contrast checks record remaining limits.

### B-108 — Center Overview on “resume this governed change”

**Problem.** The north-star metric is elapsed time from a requested policy change to
a mergeable tested pull request, but Overview is primarily a collection of global
counts and route links. It does not tell a user which change to resume, who owns the
next action, what is blocking it, or how long it has spent in each stage.

**Implement.**

- Add an “Active changes” list keyed by one governed change/package, showing source,
  current stage, lifecycle state, owner/required actor, last meaningful event,
  blocker, elapsed time, and one context-aware next action.
- Derive the five-stage progress indicator from real state rather than static route
  numbers.
- Keep system/job health as a secondary operational surface; do not mix a backend
  failure with valid product counts.
- Record request, first-candidate, first-business-edit, submission, approval,
  authoritative-test, remote-branch, and PR timestamps. Establish the baseline from
  the first real rehearsal instead of inventing a target.

**Acceptance.** A maker, checker, or delivery owner landing on Overview can resume
the highest-priority valid action in one click, while blocked actions explain the
missing prerequisite and responsible role.

### B-109 — Turn failed jobs into actionable operational records

**Demonstrated gap.** Overview reports 10 failed jobs requiring investigation, but
Operations shows only job type, actor, progress, attempts, a shortened correlation
ID, and time. Failed rows have no detail affordance, error class/message, failed
stage, source/change link, retry eligibility, or remediation. The screen therefore
reports a problem without supporting investigation.

**Implement and accept.**

- Open a job detail view with stable job ID, full correlation ID, governed-change
  link, stage timeline, attempt history, bounded/redacted error detail, timestamps,
  produced evidence, and terminal reason.
- Distinguish retryable provider/quota/network failures from invalid input,
  unsupported semantics, governance rejection, cancellation, and exhausted retries.
- Offer retry only when the backend marks it safe and idempotent; explain when a
  new import or configuration change is required instead.
- Link failed import jobs back to the exact Import history record and preserved
  configuration. A user can answer “what failed, what was affected, and what can I
  safely do next?” without copying a correlation ID into an external system.

## 4. P1 — Complete the small PostgreSQL-table flow

### B-201 — Use a genuinely least-privilege source credential

The mapping UI and bounded table import work, but the current source connection is a
separately named reference to the same cloud database credentials used by platform
state.

**Acceptance.** A distinct read-only user can access only the allowlisted source
schema/table/view, cannot write source data or platform tables, and passes identifier,
bounds, redaction, Korean UTF-8, and deterministic snapshot tests.

### B-202 — Deliver a DB-derived rule through the same Java/PR path

Promote mapped rows to a draft package, make a business correction, approve it, then
reuse B-003/B-004. The source DB must remain unchanged, while evidence/diff and target
behavior reflect the selected row change.

## 5. P2 — Performance and polish after the vertical slice

### B-301 — Reduce GoRules editor load cost

**Measured gap.** The GoRules integration is route-lazy, but opening Canonical Studio
currently loads an approximately 4.2 MB minified JS chunk and 1.7 MB WASM asset.
That is disproportionate for a small decision table.

**Investigate and implement only with measurements.**

- Split the editor island from the rest of Canonical Studio and load it only after a
  package/decision is selected.
- Determine whether Zen WASM initialization can be deferred until expression
  validation/preview is actually needed.
- Audit accidental Monaco/language-worker imports from the editor package.
- Consider a business-table-only entry point or upstream contribution if the package
  cannot tree-shake unused graph/function editors.
- Add loading skeleton, failure/retry state, and cached-load measurement.

**Acceptance.** Record cold/warm transfer size, parse/execute time, and time-to-edit
before and after on a normal laptop. Set the final budget from measured UX rather
than inventing a scale requirement.

### B-302 — Remove third-party editor console deprecations

Track GoRules/Ant Design upgrades that remove the current deprecated initialization,
Zustand, and modal-style warnings. Do not fork the editor solely to silence harmless
warnings; upgrade when compatibility and regression tests pass.

## 6. Accepted breadth versus current execution priority

The customer has accepted the existing Mode-A/Mode-B, GitHub/GitLab, DMN/DRL,
stored-object/HTML, and restricted adapter breadth. Preserve it. These capabilities
do not all need to be the primary CTA or the next implementation task at the same
time, and customer acceptance must not be presented as real-site verification or
production readiness.

The following remain outside the current execution queue unless a concrete
dependency activates them:

- Joern/SootUp or a graph database;
- large-repository/distributed mining;
- Docker/Compose production hardening;
- RDS cutover, HA, OIDC, enterprise multi-site controls;
- 10k-row performance targets;
- private-repository and additional SCM-provider expansion beyond the accepted
  GitHub/GitLab surface;
- C#, second DBMS, unrestricted stored procedures, and arbitrary UI-code mining;
- full FEEL, arbitrary expressions, or unrestricted engine compatibility beyond
  the accepted restricted DMN/DRL profiles;
- automatic merge or production deployment.

To activate one, record the real failed input/outcome, evidence from the current
lightweight path, the smallest sufficient addition, operational cost, rollback
boundary, and an acceptance test.

## 7. Recommended execution order

1. B-008 make artifact selection unambiguous and release actions fail closed.
2. B-006/B-007 clarify accepted-capability hierarchy and make degraded states
   trustworthy.
3. B-001 URL-only discovery, including the focused responsive configure flow.
4. B-002 writable dummy target repository.
5. B-003 authoritative target compile/test gates.
6. B-004 real remote branch and PR.
7. B-005 full repository rehearsal and capture the first B-108 elapsed-time baseline.
8. B-101 state-transition model extension.
9. B-102/B-103/B-105 evidence, review, and authoring completion.
10. B-108/B-109 resume active changes and make failures actionable.
11. B-107 complete responsive/accessibility acceptance across the real five-step flow.
12. B-201/B-202 PostgreSQL least-privilege and delivery flow.
13. B-301 bundle optimization using measurements.
14. Re-evaluate deferred work only from demonstrated failures.

## 8. Product-design audit record — 2026-07-26

**Audit scope.** Current local implementation at desktop 1280×720 and mobile
390×844 across landing, Overview, Imports source selection/configuration, Review
queue, Canonical Studio, Test suites, and Releases.

**Customer clarification applied.** Mode A, GitLab, DMN/DRL, stored-object/HTML,
and the existing restricted adapters are accepted capabilities. The audit finding
is therefore about hierarchy, evidence labelling, and the recommended next action;
it is not a recommendation to remove or hide those capabilities.

**Overall verdict.** The visual system is coherent and the five-stage shell gives
the product a useful backbone. The highest-impact gaps are trust and task clarity,
not cosmetic polish: accepted capability breadth lacks evidence/priority hierarchy,
and failed requests are allowed to look like valid zero/empty states.

**Strengths worth preserving.**

- Consistent dark-theme surfaces, typography, status color language, and page rhythm.
- A visible five-stage governed-change model and direct next-step links.
- Maker-checker, immutable revision, evidence, and deterministic delivery language
  are prominent.
- Raw JSON is separated from the normal business-facing table path.
- Mobile console navigation has an explicit open/close control and reduced-motion
  handling exists.

**Captured evidence.** Accepted screenshots are in
`output/product-audit-2026-07-26/` as `01-landing.png` through
`10-imports-mobile.png`. The cloud PostgreSQL connection timed out during this run,
so the audit could verify real loading/error/empty behavior and static interaction
structure, but not complete a populated candidate → approval → PR journey.
Screenshot review also cannot establish full keyboard, screen-reader, contrast, or
zoom compliance; B-107 names the required interactive checks.

**Current test signal.** On this checkout, 20 Vitest tests and the production UI
build passed. Playwright passed 5 of 8 tests; two Overview tests still expected four
workflow stages while the UI now renders five, and the Korean mobile workflow test
timed out locating the Imports link. The current green unit/build signal therefore
does not cover the product gaps above.

### Populated live audit addendum

The scheduled PostgreSQL RDS instance was started and reached `available`.
Read-only checks confirmed PostgreSQL 17.9 and Alembic
`0009_candidate_package_promotion` at head. API and UI were then audited without a
worker, migration, or write action.

The populated site showed 260 decisions, 13 items awaiting review, and 10 failed
jobs. Live evidence is in `output/product-audit-2026-07-26-live/`.

The live run adds these high-value findings:

- Test suites and Releases make different decisions indistinguishable and expose
  only the first 100 of 260; B-008 is the top safety/usability gap.
- Releases presents active publication/delivery actions for a selected DRAFT
  decision with missing readiness checks; click-time error handling is not a
  sufficient affordance or guardrail.
- Decisions is dominated by duplicate names, opaque generated keys, and
  `Unassigned flow`, so users cannot recognize the governed change they intend to
  test or release.
- Import detail and Review queue expose useful real records, but evidence,
  provenance, unresolved work, and disposition history are fragmented across
  surfaces rather than organized around one governed change.
- Operations lists repeated failed jobs without a diagnostic or recovery path;
  B-109 makes those failures actionable.
- The Studio’s package editor is real and populated, but the global development
  identity and editable Maker/Checker fields remain competing actor models.
- The mobile import stepper still drops its labels, and the desktop Decision editor
  can clip horizontally.

These findings reinforce the same two-tier north star. They do not reverse the
customer clarification: Mode A/B, GitHub/GitLab, DMN/DRL, stored-object/HTML, and
the accepted adapters remain in scope.
