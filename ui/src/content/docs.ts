export type DocLocale = 'en' | 'ko'

export type DocLink = { to: string; label: string }

export type DocVisual = {
  src: string
  alt: string
  caption: string
  width: number
  height: number
  variant: 'hero' | 'section-slide' | 'wide-diagram'
}

export type DocSection = {
  id: string
  title: string
  lead?: string
  body?: string[]
  steps?: string[]
  note?: string
  links?: DocLink[]
  visual?: DocVisual
}

export type DocContent = {
  title: string
  subtitle: string
  updated: string
  tocTitle: string
  onThisPage: string
  relatedLabel: string
  heroVisual: DocVisual
  sections: DocSection[]
}

export const docsContent = {
  en: {
    title: 'Rule Platform documentation',
    subtitle: 'A task-oriented guide to moving a business rule from source to a reviewable pull request.',
    updated: 'Getting started',
    tocTitle: 'Contents',
    onThisPage: 'On this page',
    relatedLabel: 'Go to screen',
    heroVisual: {
      src: '/guide/slides/governed-decision-hero.webp',
      alt: 'Five-stage explanatory flow from source and candidate through governed rule and golden tests to a pull request.',
      caption: 'Evidence stays attached, approval stays human, and delivery stays deterministic.',
      width: 1672,
      height: 941,
      variant: 'hero',
    },
    sections: [
      {
        id: 'overview',
        title: 'What Rule Platform does',
        lead: 'Manage business decisions as governed data, then deliver approved changes back into software safely.',
        body: [
          'Rule Platform bootstraps existing rules from a small source repository or database, lets a business user edit them without touching JSON or Java, routes the change through independent review, proves it with golden tests, and generates deterministic Java delivered as a reviewable branch and pull request.',
          'The console is organized around one path — the governed change — that every rule follows regardless of where it came from.',
        ],
        links: [{ to: '/overview', label: 'Open the Overview dashboard' }],
      },
      {
        id: 'before-you-start',
        title: 'Before you start',
        lead: 'Three controls at the top of the console frame everything you do.',
        steps: [
          'Pick your Workspace and Site in the top bar. Every screen scopes its data to the selected site.',
          'Choose a Development identity (maker-a, checker-b, reviewer-c, deployer-d). This is who your actions are attributed to — authentication is intentionally deferred in this build.',
          'Note the environment badge (Internal RC) in the sidebar: it marks the protected governance boundary you are working inside.',
        ],
        note: 'Maker-checker separation is enforced: the identity that submits a change cannot be the one that approves it. Switch identity when you move between authoring and approving.',
      },
      {
        id: 'journey',
        title: 'The five-step journey',
        lead: 'Import → Review → Author → Test → Release. The middle group of the sidebar is numbered in this order.',
        body: [
          'Every change follows the same controlled sequence. You can always see which step you are on from the sidebar numbers and the "· step N" label in each page header, and each screen links you to the next step.',
        ],
        note: 'The same path applies whether the original logic came from a Java repository, a PostgreSQL table, or another rule source.',
        visual: {
          src: '/guide/slides/rule-platform-architecture.svg',
          alt: 'Rule Platform architecture from Java and PostgreSQL inputs through evidence acquisition, governance, deterministic proof, and the Mode A and Mode B delivery boundaries.',
          caption: 'The Canonical Decision Package is the governance hub. Mode B stops at a reviewable pull request; Mode A remains a deferred capability.',
          width: 1522,
          height: 592,
          variant: 'wide-diagram',
        },
      },
      {
        id: 'import',
        title: '1 · Import a source',
        lead: 'Pin an immutable source and extract candidate rules. Imports is the single entry point for every source.',
        steps: [
          'Open Imports and choose a mode. "Source extraction" runs the wizard for a pinned Java repository or a stored object; "Guided table import" maps a bounded PostgreSQL table directly into a package.',
          'For a Java repo: paste a public GitHub URL (or select a governed site profile), set the entry class and method, then run Preflight. Preflight fails closed until a live LLM provider is configured.',
          'For a PostgreSQL table: enter the connection reference and schema, Discover tables, then pick the primary-key, condition, and outcome columns.',
          'Queue the extraction and watch the run. When candidates appear, Promote the ones you want into editable drafts — packages open in Canonical Studio, decisions open in Decisions.',
        ],
        note: 'Extraction is advisory. A candidate carries source evidence and confidence, and never becomes production logic on its own.',
        links: [{ to: '/imports', label: 'Open Imports' }],
      },
      {
        id: 'review',
        title: '2 · Review candidates',
        lead: 'Dispose of fragments the extractor could not map safely before anything is promoted.',
        steps: [
          'Open the Review queue. Each row is an unmapped fragment or diagnostic with its reason code, adapter, and raw source.',
          'Select items and Accept, Defer, or Reject them (a reason is required to defer or reject).',
          'Clear the queue so no ambiguous logic is silently carried into an authored rule.',
        ],
        links: [{ to: '/reviews', label: 'Open Review queue' }],
      },
      {
        id: 'author',
        title: '3 · Author & approve',
        lead: 'Edit the business rule in Canonical Studio, then govern the immutable revision in Decisions.',
        visual: {
          src: '/guide/slides/maker-checker-review.webp',
          alt: 'Maker and Checker swimlanes showing draft, evidence attachment, submission, independent review, and approval or rejection.',
          caption: 'The maker submits the revision. A different checker verifies meaning and evidence before approval.',
          width: 1672,
          height: 941,
          variant: 'section-slide',
        },
        steps: [
          'In Canonical Studio, open the promoted package. Edit business vocabulary labels, the decision-table rows, and add at least one business scenario (required before submit).',
          'Save creates a new immutable revision. Submit it as the maker.',
          'Switch to the checker identity and Approve (or Reject) — the maker cannot approve their own revision.',
          'Use Decisions to search the governed portfolio, compare revisions, and run the same submit/approve lifecycle for decision-shaped rules.',
        ],
        note: 'Raw JSON is available as an advanced view, but the normal authoring path never requires JSON, Java, JDM, or DMN knowledge.',
        links: [
          { to: '/studio', label: 'Open Canonical Studio' },
          { to: '/decisions', label: 'Open Decisions' },
        ],
      },
      {
        id: 'test',
        title: '4 · Prove with golden tests',
        lead: 'Capture golden cases and approved lookup snapshots, then run them against the pinned revision.',
        steps: [
          'Open Test suites and select the governed decision.',
          'Create a golden-suite revision from JSON cases (exact input, expected output, provenance) and attach every lookup snapshot needed for deterministic execution.',
          'Submit the suite, approve it independently, then Run it — execution is queued as a durable job.',
        ],
        note: 'Golden cases are the release evidence: they prove expected behavior against immutable rule and lookup revisions.',
        links: [{ to: '/test-suites', label: 'Open Test suites' }],
      },
      {
        id: 'release',
        title: '5 · Release',
        lead: 'Deliver the approved decision. One governed rule, two delivery paths.',
        visual: {
          src: '/guide/slides/golden-test-delivery.webp',
          alt: 'Deterministic Mode B pipeline from an approved rule and golden suite through generated Java, compilation, target tests, branch push, and pull request.',
          caption: 'Mode B ends at an opened pull request. Merge and production deployment remain outside the platform boundary.',
          width: 1672,
          height: 941,
          variant: 'section-slide',
        },
        steps: [
          'Open Releases and select the decision.',
          'Mode A · Managed runtime: publish an approved revision plus an approved golden suite to the Zen runtime, with append-only publication history and rollback.',
          'Mode B · Generated source: generate deterministic Java from a pinned baseline, pass the compile and regression gates, and open a reviewable GitHub PR or GitLab MR.',
          'Follow the queued job to completion from the success notice or the Operations screen.',
        ],
        note: 'The platform never auto-merges or claims production deployment. Delivery ends at a pushed branch and reviewable pull request.',
        links: [{ to: '/releases', label: 'Open Releases' }],
      },
      {
        id: 'operate',
        title: 'Operate & configure',
        lead: 'Two supporting screens sit outside the numbered journey.',
        steps: [
          'Operations is the runtime job monitor: watch durable jobs (import, tests, releases), their progress and attempts, and cancel queued or running work.',
          'Sites governs configuration: the active site profile, delivery mode, adapters, and an immutable profile-revision history. Secrets are referenced, never stored in the profile.',
        ],
        links: [
          { to: '/operations', label: 'Open Operations' },
          { to: '/sites', label: 'Open Sites' },
        ],
      },
      {
        id: 'concepts',
        title: 'Key concepts',
        lead: 'Terms you will meet across the console.',
        body: [
          'Canonical Rule IR — the vendor-neutral, reviewed decision model stored as the platform source of truth.',
          'Candidate — a proposed rule extracted from legacy material; it has no production authority.',
          'Revision — an immutable version of a decision or golden suite with its own lifecycle and evidence.',
          'Golden case — a governed input and expected output used to prove behavior before release.',
          'Provenance — the exact source revision and location supporting an extracted rule.',
          'Publication — an append-only Mode A record that makes an approved rule available to the runtime.',
        ],
      },
    ],
  },
  ko: {
    title: 'Rule Platform 문서',
    subtitle: '비즈니스 규칙을 소스에서 검토 가능한 풀 리퀘스트까지 옮기는 실무 중심 가이드입니다.',
    updated: '시작하기',
    tocTitle: '목차',
    onThisPage: '이 페이지에서',
    relatedLabel: '화면 열기',
    heroVisual: {
      src: '/guide/slides/governed-decision-hero.webp',
      alt: '소스와 후보에서 관리된 규칙과 골든 테스트를 거쳐 풀 리퀘스트에 이르는 5단계 설명 흐름입니다.',
      caption: '증거는 계속 연결되고, 승인은 사람이 담당하며, 전달은 결정론적으로 수행됩니다.',
      width: 1672,
      height: 941,
      variant: 'hero',
    },
    sections: [
      {
        id: 'overview',
        title: 'Rule Platform의 역할',
        lead: '비즈니스 의사결정을 관리되는 데이터로 다루고, 승인된 변경을 소프트웨어에 안전하게 반영합니다.',
        body: [
          'Rule Platform은 소규모 소스 저장소나 데이터베이스에서 기존 규칙을 가져오고, 비즈니스 사용자가 JSON이나 Java를 건드리지 않고 편집하게 하며, 독립 검토를 거쳐 골든 테스트로 검증한 뒤, 결정론적 Java를 생성해 검토 가능한 브랜치와 풀 리퀘스트로 전달합니다.',
          '콘솔은 하나의 경로, 즉 관리되는 변경을 중심으로 구성되며 모든 규칙이 출처와 무관하게 이 경로를 따릅니다.',
        ],
        links: [{ to: '/overview', label: '개요 대시보드 열기' }],
      },
      {
        id: 'before-you-start',
        title: '시작하기 전에',
        lead: '콘솔 상단의 세 가지 컨트롤이 모든 작업의 틀을 잡습니다.',
        steps: [
          '상단 바에서 워크스페이스와 사이트를 선택합니다. 모든 화면은 선택된 사이트로 데이터를 한정합니다.',
          '개발용 ID(maker-a, checker-b, reviewer-c, deployer-d)를 선택합니다. 이 값으로 작업이 기록되며, 이 빌드에서 인증은 의도적으로 보류되어 있습니다.',
          '사이드바의 환경 배지(Internal RC)는 작업 중인 보호된 거버넌스 경계를 표시합니다.',
        ],
        note: 'Maker-checker 분리가 강제됩니다. 변경을 제출한 ID는 같은 변경을 승인할 수 없으므로, 작성과 승인 사이에서 ID를 전환하세요.',
      },
      {
        id: 'journey',
        title: '5단계 여정',
        lead: '가져오기 → 검토 → 작성 → 테스트 → 배포. 사이드바 가운데 그룹이 이 순서로 번호가 매겨집니다.',
        body: [
          '모든 변경은 동일한 통제된 순서를 따릅니다. 사이드바 번호와 각 페이지 머리말의 "· step N" 표시로 현재 단계를 알 수 있으며, 각 화면은 다음 단계로 연결됩니다.',
        ],
        note: '원본 로직이 Java 저장소, PostgreSQL 테이블, 다른 규칙 소스 어디에서 왔든 동일한 경로가 적용됩니다.',
        visual: {
          src: '/guide/slides/rule-platform-architecture.svg',
          alt: 'Java와 PostgreSQL 입력에서 증거 수집, 거버넌스, 결정론적 검증, Mode A와 Mode B 전달 경계까지 이어지는 Rule Platform 아키텍처입니다.',
          caption: 'Canonical Decision Package가 거버넌스 허브입니다. Mode B는 검토 가능한 풀 리퀘스트에서 끝나며 Mode A는 보류된 기능으로 유지됩니다.',
          width: 1522,
          height: 592,
          variant: 'wide-diagram',
        },
      },
      {
        id: 'import',
        title: '1 · 소스 가져오기',
        lead: '불변 소스를 고정하고 후보 규칙을 추출합니다. 가져오기는 모든 소스의 단일 진입점입니다.',
        steps: [
          '가져오기를 열고 모드를 선택합니다. "소스 추출"은 고정된 Java 저장소나 저장 객체용 마법사를 실행하고, "가이드 테이블 가져오기"는 제한된 PostgreSQL 테이블을 패키지로 바로 매핑합니다.',
          'Java 저장소: 공개 GitHub URL을 붙여넣거나(또는 거버넌스 사이트 프로필 선택) 진입 클래스와 메서드를 설정한 뒤 사전 점검을 실행합니다. 활성 LLM 공급자가 구성되기 전까지 사전 점검은 실패로 닫힙니다.',
          'PostgreSQL 테이블: 연결 참조와 스키마를 입력하고 테이블을 탐색한 뒤 기본 키·조건·결과 컬럼을 선택합니다.',
          '추출을 큐에 넣고 실행을 지켜봅니다. 후보가 나타나면 원하는 항목을 편집 가능한 초안으로 승격합니다. 패키지는 Canonical 스튜디오에서, 결정은 의사결정에서 열립니다.',
        ],
        note: '추출은 참고용입니다. 후보는 소스 증거와 신뢰도를 가지며 그 자체로 운영 로직이 되지 않습니다.',
        links: [{ to: '/imports', label: '가져오기 열기' }],
      },
      {
        id: 'review',
        title: '2 · 후보 검토',
        lead: '승격 전에 추출기가 안전하게 매핑하지 못한 조각을 처리합니다.',
        steps: [
          '검토 대기열을 엽니다. 각 행은 사유 코드, 어댑터, 원본 소스가 있는 매핑 불가 조각 또는 진단입니다.',
          '항목을 선택해 수락, 보류, 반려합니다(보류·반려에는 사유가 필요합니다).',
          '모호한 로직이 작성된 규칙으로 조용히 넘어가지 않도록 대기열을 비웁니다.',
        ],
        links: [{ to: '/reviews', label: '검토 대기열 열기' }],
      },
      {
        id: 'author',
        title: '3 · 작성 및 승인',
        lead: 'Canonical 스튜디오에서 비즈니스 규칙을 편집하고, 의사결정에서 불변 리비전을 관리합니다.',
        visual: {
          src: '/guide/slides/maker-checker-review.webp',
          alt: '초안 작성, 증거 첨부, 제출, 독립 검토, 승인 또는 반려를 보여 주는 Maker와 Checker 스윔레인입니다.',
          caption: 'Maker가 리비전을 제출하고 다른 Checker가 의미와 증거를 확인한 뒤 승인합니다.',
          width: 1672,
          height: 941,
          variant: 'section-slide',
        },
        steps: [
          'Canonical 스튜디오에서 승격된 패키지를 엽니다. 비즈니스 용어 레이블과 결정 테이블 행을 편집하고, 제출 전에 최소 하나의 비즈니스 시나리오를 추가합니다.',
          '저장하면 새 불변 리비전이 생성됩니다. Maker로 제출합니다.',
          'Checker ID로 전환해 승인(또는 반려)합니다. Maker는 자신의 리비전을 승인할 수 없습니다.',
          '의사결정에서 관리 포트폴리오를 검색하고 리비전을 비교하며 결정형 규칙에 동일한 제출/승인 생명주기를 실행합니다.',
        ],
        note: '고급 보기로 원시 JSON을 제공하지만, 일반 작성 경로에는 JSON·Java·JDM·DMN 지식이 필요하지 않습니다.',
        links: [
          { to: '/studio', label: 'Canonical 스튜디오 열기' },
          { to: '/decisions', label: '의사결정 열기' },
        ],
      },
      {
        id: 'test',
        title: '4 · 골든 테스트로 검증',
        lead: '골든 케이스와 승인된 조회 스냅샷을 만들어 고정된 리비전에 대해 실행합니다.',
        steps: [
          '테스트 스위트를 열고 관리 대상 결정을 선택합니다.',
          'JSON 케이스(정확한 입력, 기대 출력, 출처)로 골든 스위트 리비전을 만들고 결정론적 실행에 필요한 조회 스냅샷을 모두 첨부합니다.',
          '스위트를 제출하고 독립적으로 승인한 뒤 실행합니다. 실행은 내구성 작업으로 큐에 등록됩니다.',
        ],
        note: '골든 케이스는 배포 증거입니다. 불변 규칙과 조회 리비전에 대해 기대 동작을 증명합니다.',
        links: [{ to: '/test-suites', label: '테스트 스위트 열기' }],
      },
      {
        id: 'release',
        title: '5 · 배포',
        lead: '승인된 결정을 전달합니다. 하나의 관리 규칙, 두 개의 배포 경로.',
        visual: {
          src: '/guide/slides/golden-test-delivery.webp',
          alt: '승인된 규칙과 골든 스위트에서 Java 생성, 컴파일, 대상 테스트, 브랜치 푸시, 풀 리퀘스트까지 이어지는 결정론적 Mode B 파이프라인입니다.',
          caption: 'Mode B는 풀 리퀘스트를 여는 지점에서 끝납니다. 병합과 운영 배포는 플랫폼 경계 밖에 있습니다.',
          width: 1672,
          height: 941,
          variant: 'section-slide',
        },
        steps: [
          '릴리스를 열고 결정을 선택합니다.',
          'Mode A · 관리형 런타임: 승인된 리비전과 승인된 골든 스위트를 Zen 런타임에 게시하며, 추가 전용 게시 이력과 롤백을 제공합니다.',
          'Mode B · 생성 소스: 고정 기준선에서 결정론적 Java를 생성하고 컴파일 및 회귀 게이트를 통과한 뒤 검토 가능한 GitHub PR 또는 GitLab MR을 엽니다.',
          '성공 알림이나 운영 화면에서 큐에 등록된 작업이 완료될 때까지 추적합니다.',
        ],
        note: '플랫폼은 자동 병합하거나 운영 배포를 주장하지 않습니다. 배포는 푸시된 브랜치와 검토 가능한 풀 리퀘스트에서 끝납니다.',
        links: [{ to: '/releases', label: '릴리스 열기' }],
      },
      {
        id: 'operate',
        title: '운영 및 설정',
        lead: '번호가 매겨진 여정 밖에 두 개의 보조 화면이 있습니다.',
        steps: [
          '운영은 런타임 작업 모니터입니다. 내구성 작업(가져오기, 테스트, 릴리스)의 진행과 시도를 확인하고 큐 또는 실행 중 작업을 취소합니다.',
          '사이트는 구성을 관리합니다. 활성 사이트 프로필, 배포 모드, 어댑터, 불변 프로필 리비전 이력을 보여줍니다. 비밀 값은 프로필에 저장되지 않고 참조됩니다.',
        ],
        links: [
          { to: '/operations', label: '운영 열기' },
          { to: '/sites', label: '사이트 열기' },
        ],
      },
      {
        id: 'concepts',
        title: '핵심 개념',
        lead: '콘솔 전반에서 만나게 될 용어입니다.',
        body: [
          'Canonical Rule IR — 플랫폼의 단일 진실 공급원으로 저장되는 벤더 중립적 의사결정 모델입니다.',
          '후보 — 레거시 자료에서 추출한 제안 규칙이며 운영 권한이 없습니다.',
          '리비전 — 자체 생명주기와 증거를 가진 의사결정 또는 골든 스위트의 불변 버전입니다.',
          '골든 케이스 — 배포 전 동작을 증명하기 위한 관리된 입력과 기대 출력입니다.',
          '출처 추적 — 추출된 규칙을 뒷받침하는 정확한 소스 리비전과 위치입니다.',
          '게시 — 승인된 규칙을 런타임에서 사용할 수 있게 하는 추가 전용 Mode A 기록입니다.',
        ],
      },
    ],
  },
} satisfies Record<DocLocale, DocContent>
