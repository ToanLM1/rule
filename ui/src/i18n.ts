import { createI18n } from 'vue-i18n'

const en = {
  nav: {
    overview: 'Overview',
    decisions: 'Decisions',
    imports: 'Imports',
    reviews: 'Review queue',
    suites: 'Test suites',
    releases: 'Releases',
    sites: 'Sites',
    operations: 'Operations',
  },
  app: {
    name: 'Rule Platform',
    console: 'Governance studio',
    environment: 'Internal RC',
    jobs: 'active jobs',
    developmentIdentity: 'Development identity',
    search: 'Search decisions, jobs and workspaces',
    commandTitle: 'Go anywhere',
    commandHint: 'Navigate a workspace or search the decision portfolio.',
  },
  overview: {
    eyebrow: 'Governed logic, visible end to end',
    title: 'Turn buried business logic into governed decisions.',
    description:
      'Trace every rule to its source, move it through independent review, prove it with golden evidence, and release with confidence.',
    primaryAction: 'Import a source',
    secondaryAction: 'Open review queue',
    pulseTitle: 'Operational pulse',
    pulseBody: 'A live view of governed decisions and the work moving through the control plane.',
    journeyTitle: 'A rule never jumps the line.',
    journeyBody:
      'Every change follows the same evidence-backed path from extraction to production delivery.',
    actionTitle: 'Start a governed change.',
    actionBody: 'Bring in a pinned source and let the platform preserve the evidence trail from day one.',
  },
}

const ko = {
  nav: {
    overview: '개요',
    decisions: '결정',
    imports: '가져오기',
    reviews: '검토 대기열',
    suites: '테스트 스위트',
    releases: '릴리스',
    sites: '사이트',
    operations: '운영',
  },
  app: {
    name: '규칙 플랫폼',
    console: '거버넌스 스튜디오',
    environment: '내부 RC',
    jobs: '활성 작업',
    developmentIdentity: '개발용 ID',
    search: '결정, 작업 및 워크스페이스 검색',
    commandTitle: '빠른 이동',
    commandHint: '워크스페이스로 이동하거나 결정 포트폴리오를 검색합니다.',
  },
  overview: {
    eyebrow: '처음부터 끝까지 보이는 규칙 거버넌스',
    title: '코드 속 비즈니스 로직을 관리 가능한 결정으로 전환하세요.',
    description:
      '모든 규칙의 출처를 추적하고, 독립 검토와 골든 테스트를 거쳐 신뢰할 수 있게 배포합니다.',
    primaryAction: '소스 가져오기',
    secondaryAction: '검토 대기열 열기',
    pulseTitle: '운영 현황',
    pulseBody: '관리 중인 결정과 제어 흐름을 통과하는 작업을 실시간으로 확인합니다.',
    journeyTitle: '어떤 규칙도 절차를 건너뛰지 않습니다.',
    journeyBody: '모든 변경은 추출부터 운영 배포까지 동일한 증거 기반 경로를 따릅니다.',
    actionTitle: '관리되는 변경을 시작하세요.',
    actionBody: '고정된 소스를 가져오고 첫 단계부터 증거 추적을 보존하세요.',
  },
}

export const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('brp.locale') ?? 'en',
  fallbackLocale: 'en',
  messages: { en, ko },
})
