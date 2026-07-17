import { createI18n } from 'vue-i18n'

const en = {
  nav: { overview: 'Overview', decisions: 'Decisions', imports: 'Imports', reviews: 'Review queue', suites: 'Test suites', releases: 'Releases', sites: 'Sites', operations: 'Operations' },
  app: { name: 'Rule Platform', environment: 'Internal RC', jobs: 'active jobs', developmentIdentity: 'Development identity' },
  page: { overview: 'Overview', decisions: 'Decisions', imports: 'Imports', reviews: 'Review queue', suites: 'Test suites', releases: 'Releases', sites: 'Sites', operations: 'Operations' },
}

const ko = {
  nav: { overview: '개요', decisions: '결정', imports: '가져오기', reviews: '검토 대기열', suites: '테스트 스위트', releases: '릴리스', sites: '사이트', operations: '운영' },
  app: { name: '규칙 플랫폼', environment: '내부 RC', jobs: '활성 작업', developmentIdentity: '개발용 ID' },
  page: { overview: '개요', decisions: '결정', imports: '가져오기', reviews: '검토 대기열', suites: '테스트 스위트', releases: '릴리스', sites: '사이트', operations: '운영' },
}

export const i18n = createI18n({ legacy: false, locale: localStorage.getItem('brp.locale') ?? 'en', fallbackLocale: 'en', messages: { en, ko } })
