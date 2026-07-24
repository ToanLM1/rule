export type GuideLocale = 'en' | 'ko'

export type GuideContent = {
  nav: { title: string; chapters: Array<{ id: string; label: string }> }
  media: {
    heroAlt: string
    trustAlt: string
    workflowAlt: string
    deliveryAlt: string
    roleAlts: string[]
    previousRole: string
    nextRole: string
    roleSelector: string
    video: { title: string; body: string; label: string; fallback: string; captionsEn: string; captionsKo: string }
  }
  hero: { eyebrow: string; titleLead: string; titleEmphasis: string; titleTail: string; body: string; primary: string; secondary: string; visualTitle: string; visualCaption: string }
  marquee: string[]
  principles: { eyebrow: string; title: string; body: string; cards: Array<{ title: string; body: string; proof: string }> }
  trust: { eyebrow: string; title: string; words: string[]; note: string }
  workflow: { eyebrow: string; title: string; body: string; steps: Array<{ title: string; screen: string; body: string; action: string; to: string }> }
  roles: { eyebrow: string; title: string; items: Array<{ name: string; role: string; quote: string; responsibility: string }> }
  simulator: {
    eyebrow: string
    title: string
    body: string
    notice: string
    age: string
    resident: string
    risk: string
    yes: string
    no: string
    outcome: string
    matched: string
    reasons: Record<'AGE_OUT_OF_RANGE' | 'RESIDENCY_REVIEW' | 'RISK_REVIEW' | 'ELIGIBLE', string>
    outcomes: Record<'INELIGIBLE' | 'MANUAL_REVIEW' | 'ELIGIBLE', string>
  }
  modes: { eyebrow: string; title: string; body: string; modeA: { title: string; body: string; authority: string }; modeB: { title: string; body: string; authority: string } }
  glossary: { eyebrow: string; title: string; items: Array<{ term: string; definition: string }> }
  cta: { title: string; body: string; primary: string; secondary: string }
}

export const guideContent = {
  en: {
    nav: {
      title: 'Rule Platform guide',
      chapters: [
        { id: 'understand', label: 'Understand' },
        { id: 'trust', label: 'Trust model' },
        { id: 'workflow', label: 'Workflow' },
        { id: 'simulate', label: 'Try a rule' },
        { id: 'delivery', label: 'Delivery' },
      ],
    },
    media: {
      heroAlt: 'A Maker and Checker turn source documents and database logic into reviewed rule cards, golden evidence and an approved release.',
      trustAlt: 'A Maker and Checker compare a proposed rule with highlighted source evidence before approval and release.',
      workflowAlt: 'Five-stage workflow from code and database import through normalized rules, Maker editing, Checker approval and tested release.',
      deliveryAlt: 'Approved rules branch to a managed runtime on the left and deterministic generated source on the right.',
      roleAlts: [
        'Maker editing structured business-rule cards on a tablet.',
        'Checker comparing source evidence with a proposed rule and review checklist.',
        'Reviewer comparing golden test cases with an expected decision.',
        'Deployer holding an approved release package beside a server rack.',
      ],
      previousRole: 'Previous role',
      nextRole: 'Next role',
      roleSelector: 'Choose a role',
      video: {
        title: 'See how the governed flow works.',
        body: 'A 45-second technical explainer of source adapters, Canonical Rule IR, maker-checker review, golden execution and both delivery paths.',
        label: 'Rule Platform overview video',
        fallback: 'Your browser does not support embedded video.',
        captionsEn: 'English captions',
        captionsKo: 'Korean captions',
      },
    },
    hero: {
      eyebrow: 'A business guide to governed decisions',
      titleLead: 'Business rules you can',
      titleEmphasis: 'see, prove,',
      titleTail: 'and change.',
      body: 'Understand how legacy logic becomes a governed decision, then move a change safely from source evidence to production delivery.',
      primary: 'Explore the workflow',
      secondary: 'Open the console',
      visualTitle: 'One rule. One evidence chain.',
      visualCaption: 'Source, decision, test and release stay connected.',
    },
    marquee: ['Canonical Rule IR', 'Source fidelity', 'Maker-checker', 'Golden evidence', 'Immutable revisions', 'Deterministic delivery'],
    principles: {
      eyebrow: 'What makes a rule trustworthy',
      title: 'Business-readable on the surface. Strictly governed underneath.',
      body: 'The platform separates the decision people review from the technical formats systems execute.',
      cards: [
        { title: 'One source of truth', body: 'Canonical Rule IR stores the reviewed decision independently of any vendor engine or programming language.', proof: 'Vendor-neutral and versioned' },
        { title: 'Exact provenance', body: 'Every candidate points back to the pinned source revision and location it came from.', proof: 'Nothing is silently guessed' },
        { title: 'Independent approval', body: 'The person who makes a change cannot approve the same revision.', proof: 'Maker-checker enforced' },
        { title: 'Evidence before release', body: 'Golden cases prove expected behavior against immutable rule and lookup revisions.', proof: 'Reproducible test record' },
        { title: 'Two delivery modes', body: 'A site can publish to the managed runtime or deliver generated source without changing the governed rule model.', proof: 'One IR, two target paths' },
      ],
    },
    trust: {
      eyebrow: 'The safety boundary',
      title: 'A candidate is never production logic.',
      words: ['Extraction', 'finds', 'possible', 'rules.', 'People', 'review', 'the', 'evidence.', 'Golden', 'tests', 'prove', 'the', 'behavior.', 'Only', 'then', 'can', 'an', 'approved', 'revision', 'be', 'released.'],
      note: 'AI may assist mining. It never approves a decision or generates free-form production behavior.',
    },
    workflow: {
      eyebrow: 'From source to release',
      title: 'One controlled path for every change.',
      body: 'Follow the same sequence whether the original logic came from code, a database table, a manual or another rule engine.',
      steps: [
        { title: 'Pin and preflight the source', screen: 'Imports', body: 'Choose an approved source profile, select an immutable revision and confirm the adapter can process it safely.', action: 'Open Imports', to: '/imports' },
        { title: 'Review the candidate and provenance', screen: 'Review queue', body: 'Compare the proposed condition and outcome with the exact source evidence. Unsupported fragments stay in review.', action: 'Open Review queue', to: '/reviews' },
        { title: 'Create and approve a revision', screen: 'Decisions', body: 'Edit as a new immutable revision. The maker submits it and a different checker approves or rejects it.', action: 'Open Decisions', to: '/decisions' },
        { title: 'Prove expected behavior', screen: 'Test suites', body: 'Create golden cases, approve lookup snapshots and run the suite against the pinned decision revision.', action: 'Open Test suites', to: '/test-suites' },
        { title: 'Release and observe', screen: 'Releases · Operations', body: 'Publish Mode A or deliver Mode B, then follow the durable job and retained evidence through completion.', action: 'Open Releases', to: '/releases' },
      ],
    },
    roles: {
      eyebrow: 'People in the control loop',
      title: 'Clear responsibility at every handoff.',
      items: [
        { name: 'Min Park', role: 'Maker', quote: 'I turn a reviewed business change into a new revision without altering approved history.', responsibility: 'Creates and submits rule or golden-suite revisions.' },
        { name: 'Jisoo Han', role: 'Checker', quote: 'I verify the rule meaning, source evidence and effective dates before approval.', responsibility: 'Approves or rejects independently from the maker.' },
        { name: 'Alex Morgan', role: 'Reviewer', quote: 'I resolve fragments the adapter could not map safely instead of letting the platform guess.', responsibility: 'Reviews provenance, diagnostics and unmappable source.' },
        { name: 'Sora Kim', role: 'Deployer', quote: 'I release only the exact approved decision and evidence bundle selected for the target site.', responsibility: 'Publishes Mode A or delivers Mode B artifacts.' },
      ],
    },
    simulator: {
      eyebrow: 'Illustrative decision',
      title: 'See how a simple eligibility rule resolves.',
      body: 'Change the inputs to reveal the matched rule and the explanation a business reviewer would inspect.',
      notice: 'Illustrative sample — not production data',
      age: 'Applicant age', resident: 'Resident in supported market', risk: 'Risk flag present', yes: 'Yes', no: 'No', outcome: 'Outcome', matched: 'Matched rule',
      reasons: {
        AGE_OUT_OF_RANGE: 'The applicant is outside the illustrative 18–65 age range.',
        RESIDENCY_REVIEW: 'Residency needs a manual policy review before a decision can be made.',
        RISK_REVIEW: 'A risk flag routes this case to a human reviewer.',
        ELIGIBLE: 'All illustrative eligibility conditions are satisfied.',
      },
      outcomes: { INELIGIBLE: 'Ineligible', MANUAL_REVIEW: 'Manual review', ELIGIBLE: 'Eligible' },
    },
    modes: {
      eyebrow: 'How approved rules reach production',
      title: 'One governed decision. Two delivery paths.',
      body: 'The site profile chooses the target path; governance and evidence remain the same.',
      modeA: { title: 'Mode A · Managed runtime', body: 'Approved IR is exported to JDM and published to the embedded Zen runtime with append-only publication history and rollback.', authority: 'Authoritative evidence: engine-run golden tests.' },
      modeB: { title: 'Mode B · Generated source', body: 'Approved IR generates deterministic source and tests, then opens a reviewable Git change after compile and regression gates pass.', authority: 'Authoritative evidence: generated-source execution.' },
    },
    glossary: {
      eyebrow: 'Plain-language reference',
      title: 'Terms worth knowing.',
      items: [
        { term: 'Canonical Rule IR', definition: 'The vendor-neutral, reviewed decision model stored as the platform source of truth.' },
        { term: 'Candidate', definition: 'A proposed rule extracted from legacy material. It has no production authority.' },
        { term: 'Revision', definition: 'An immutable version of a decision or golden suite with its own lifecycle and evidence.' },
        { term: 'Golden case', definition: 'A governed input and expected output used to prove behavior before release.' },
        { term: 'Provenance', definition: 'The exact source revision and location supporting an extracted rule.' },
        { term: 'Publication', definition: 'An append-only Mode A record that makes an approved rule available to the runtime.' },
      ],
    },
    cta: { title: 'Ready to follow a rule from source to release?', body: 'Start with a pinned source, keep the evidence visible and let every approval leave a durable record.', primary: 'Start an import', secondary: 'Return to Overview' },
  },
  ko: {
    nav: {
      title: 'Rule Platform 가이드',
      chapters: [
        { id: 'understand', label: '이해하기' },
        { id: 'trust', label: '신뢰 모델' },
        { id: 'workflow', label: '업무 흐름' },
        { id: 'simulate', label: '규칙 체험' },
        { id: 'delivery', label: '배포 방식' },
      ],
    },
    media: {
      heroAlt: 'Maker와 Checker가 소스 문서와 데이터베이스 로직을 검토 가능한 규칙, 골든 증거와 승인된 릴리스로 전환합니다.',
      trustAlt: 'Maker와 Checker가 승인 및 릴리스 전에 제안된 규칙을 강조된 소스 증거와 비교합니다.',
      workflowAlt: '코드와 데이터베이스 가져오기부터 규칙 정규화, Maker 편집, Checker 승인과 테스트된 릴리스까지의 5단계 흐름입니다.',
      deliveryAlt: '승인된 규칙이 왼쪽의 관리형 런타임과 오른쪽의 결정론적 생성 소스로 나뉩니다.',
      roleAlts: [
        'Maker가 태블릿에서 구조화된 비즈니스 규칙 카드를 편집합니다.',
        'Checker가 소스 증거와 제안 규칙 및 검토 체크리스트를 비교합니다.',
        'Reviewer가 골든 테스트 케이스와 기대 의사결정을 비교합니다.',
        'Deployer가 서버 랙 옆에서 승인된 릴리스 패키지를 들고 있습니다.',
      ],
      previousRole: '이전 역할',
      nextRole: '다음 역할',
      roleSelector: '역할 선택',
      video: {
        title: '관리된 흐름의 작동 방식을 확인하세요.',
        body: '소스 어댑터, Canonical Rule IR, 메이커-체커 검토, 골든 실행과 두 배포 경로를 설명하는 45초 기술 영상입니다.',
        label: 'Rule Platform 소개 영상',
        fallback: '이 브라우저는 내장 영상을 지원하지 않습니다.',
        captionsEn: '영어 자막',
        captionsKo: '한국어 자막',
      },
    },
    hero: {
      eyebrow: '비즈니스 사용자를 위한 거버넌스 가이드',
      titleLead: '보고, 검증하고,',
      titleEmphasis: '안전하게 변경하는',
      titleTail: '비즈니스 규칙.',
      body: '레거시 로직이 관리되는 의사결정으로 전환되는 과정을 이해하고, 소스 증거부터 운영 배포까지 안전하게 변경하세요.',
      primary: '업무 흐름 살펴보기',
      secondary: '콘솔 열기',
      visualTitle: '하나의 규칙, 하나의 증거 체인.',
      visualCaption: '소스, 의사결정, 테스트와 배포가 계속 연결됩니다.',
    },
    marquee: ['Canonical Rule IR', '소스 원문 보존', 'Maker-checker', '골든 증거', '불변 리비전', '결정론적 배포'],
    principles: {
      eyebrow: '신뢰할 수 있는 규칙의 조건',
      title: '비즈니스에는 읽기 쉽게, 내부 통제는 엄격하게.',
      body: '플랫폼은 사람이 검토하는 의사결정과 시스템이 실행하는 기술 형식을 분리합니다.',
      cards: [
        { title: '단일 진실 공급원', body: 'Canonical Rule IR은 특정 엔진이나 프로그래밍 언어와 독립적으로 검토된 의사결정을 저장합니다.', proof: '벤더 중립적이며 버전 관리됨' },
        { title: '정확한 출처 추적', body: '모든 후보 규칙은 고정된 소스 리비전과 원래 위치로 연결됩니다.', proof: '추측하거나 누락하지 않음' },
        { title: '독립 승인', body: '변경을 만든 사람은 같은 리비전을 승인할 수 없습니다.', proof: 'Maker-checker 강제' },
        { title: '배포 전 증거', body: '골든 케이스는 불변 규칙과 조회 데이터 리비전에 대해 기대 동작을 증명합니다.', proof: '재현 가능한 테스트 기록' },
        { title: '두 가지 배포 모드', body: '동일한 관리 규칙 모델에서 런타임 게시 또는 생성 소스 배포를 선택할 수 있습니다.', proof: '하나의 IR, 두 개의 대상 경로' },
      ],
    },
    trust: {
      eyebrow: '안전 경계',
      title: '후보 규칙은 운영 로직이 아닙니다.',
      words: ['추출은', '가능한', '규칙을', '찾습니다.', '사람은', '소스', '증거를', '검토합니다.', '골든', '테스트는', '동작을', '증명합니다.', '그', '이후에만', '승인된', '리비전을', '배포할', '수', '있습니다.'],
      note: 'AI는 마이닝을 보조할 수 있지만, 의사결정을 승인하거나 운영 동작을 자유 형식으로 생성하지 않습니다.',
    },
    workflow: {
      eyebrow: '소스에서 배포까지',
      title: '모든 변경은 하나의 통제된 경로를 따릅니다.',
      body: '원본 로직이 코드, DB 테이블, 매뉴얼 또는 다른 규칙 엔진에서 왔더라도 같은 순서로 진행합니다.',
      steps: [
        { title: '소스를 고정하고 사전 점검', screen: '가져오기', body: '승인된 소스 프로필과 불변 리비전을 선택하고 어댑터가 안전하게 처리할 수 있는지 확인합니다.', action: '가져오기 열기', to: '/imports' },
        { title: '후보 규칙과 출처 검토', screen: '검토 대기열', body: '제안된 조건과 결과를 정확한 소스 증거와 비교합니다. 지원되지 않는 조각은 검토 상태로 남습니다.', action: '검토 대기열 열기', to: '/reviews' },
        { title: '리비전 생성 및 승인', screen: '의사결정', body: '새 불변 리비전으로 편집합니다. Maker가 제출하고 다른 Checker가 승인하거나 반려합니다.', action: '의사결정 열기', to: '/decisions' },
        { title: '기대 동작 증명', screen: '테스트 스위트', body: '골든 케이스와 조회 스냅샷을 승인하고 고정된 의사결정 리비전에 대해 실행합니다.', action: '테스트 스위트 열기', to: '/test-suites' },
        { title: '배포 및 관찰', screen: '릴리스 · 운영', body: 'Mode A 게시 또는 Mode B 전달을 실행하고 내구성 작업과 증거가 완료될 때까지 추적합니다.', action: '릴리스 열기', to: '/releases' },
      ],
    },
    roles: {
      eyebrow: '통제 과정의 사람들',
      title: '모든 인계 지점의 책임을 명확하게.',
      items: [
        { name: '박민준', role: 'Maker', quote: '승인된 이력을 변경하지 않고 검토된 비즈니스 변경을 새 리비전으로 만듭니다.', responsibility: '규칙 또는 골든 스위트 리비전을 생성하고 제출합니다.' },
        { name: '한지수', role: 'Checker', quote: '승인 전에 규칙의 의미, 소스 증거와 적용 기간을 확인합니다.', responsibility: 'Maker와 독립적으로 승인하거나 반려합니다.' },
        { name: 'Alex Morgan', role: 'Reviewer', quote: '플랫폼이 추측하지 않도록 어댑터가 안전하게 매핑하지 못한 조각을 해결합니다.', responsibility: '출처, 진단 정보와 매핑 불가 소스를 검토합니다.' },
        { name: '김소라', role: 'Deployer', quote: '대상 사이트에 선택된 정확한 승인 의사결정과 증거 묶음만 배포합니다.', responsibility: 'Mode A를 게시하거나 Mode B 산출물을 전달합니다.' },
      ],
    },
    simulator: {
      eyebrow: '예시 의사결정',
      title: '간단한 가입 자격 규칙의 판정 과정을 확인하세요.',
      body: '입력값을 바꾸어 일치한 규칙과 비즈니스 검토자가 확인할 설명을 살펴보세요.',
      notice: '설명용 예시이며 운영 데이터가 아닙니다',
      age: '신청자 나이', resident: '지원 대상 시장 거주', risk: '위험 플래그 존재', yes: '예', no: '아니요', outcome: '결과', matched: '일치 규칙',
      reasons: {
        AGE_OUT_OF_RANGE: '신청자가 예시 기준인 만 18–65세 범위를 벗어났습니다.',
        RESIDENCY_REVIEW: '판정 전에 거주 요건에 대한 수동 정책 검토가 필요합니다.',
        RISK_REVIEW: '위험 플래그로 인해 담당자 검토가 필요합니다.',
        ELIGIBLE: '예시 가입 자격 조건을 모두 충족합니다.',
      },
      outcomes: { INELIGIBLE: '가입 불가', MANUAL_REVIEW: '수동 검토', ELIGIBLE: '가입 가능' },
    },
    modes: {
      eyebrow: '승인된 규칙이 운영에 반영되는 방식',
      title: '하나의 관리 의사결정, 두 가지 배포 경로.',
      body: '사이트 프로필이 대상 경로를 선택하며 거버넌스와 증거는 동일하게 유지됩니다.',
      modeA: { title: 'Mode A · 관리형 런타임', body: '승인된 IR을 JDM으로 내보내 Zen 런타임에 게시하며, 추가 전용 게시 이력과 롤백을 제공합니다.', authority: '권위 있는 증거: 엔진에서 실행한 골든 테스트.' },
      modeB: { title: 'Mode B · 생성 소스', body: '승인된 IR로 결정론적 소스와 테스트를 생성하고 컴파일 및 회귀 게이트 통과 후 검토 가능한 Git 변경을 만듭니다.', authority: '권위 있는 증거: 생성 소스 실행 결과.' },
    },
    glossary: {
      eyebrow: '쉬운 용어 설명',
      title: '알아두면 좋은 용어.',
      items: [
        { term: 'Canonical Rule IR', definition: '플랫폼의 단일 진실 공급원으로 저장되는 벤더 중립적 의사결정 모델입니다.' },
        { term: '후보 규칙', definition: '레거시 자료에서 추출한 제안 규칙이며 운영 권한은 없습니다.' },
        { term: '리비전', definition: '자체 생명주기와 증거를 가진 의사결정 또는 골든 스위트의 불변 버전입니다.' },
        { term: '골든 케이스', definition: '배포 전 동작을 증명하기 위한 관리된 입력과 기대 결과입니다.' },
        { term: '출처 추적', definition: '추출된 규칙을 뒷받침하는 정확한 소스 리비전과 위치입니다.' },
        { term: '게시', definition: '승인된 규칙을 런타임에서 사용할 수 있게 하는 추가 전용 Mode A 기록입니다.' },
      ],
    },
    cta: { title: '소스에서 배포까지 규칙을 직접 추적해 보세요.', body: '고정된 소스에서 시작하여 증거를 계속 확인하고 모든 승인 기록을 내구성 있게 남기세요.', primary: '가져오기 시작', secondary: '개요로 돌아가기' },
  },
} satisfies Record<GuideLocale, GuideContent>
