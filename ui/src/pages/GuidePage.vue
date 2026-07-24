<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import {
  PhArrowRight,
  PhBookOpenText,
  PhCheckCircle,
  PhCaretLeft,
  PhCaretRight,
  PhCode,
  PhDatabase,
  PhFingerprint,
  PhGitPullRequest,
  PhShieldCheck,
  PhTestTube,
} from '@phosphor-icons/vue'
import { guideContent, type GuideLocale } from '../content/guide'
import { evaluateSampleDecision, guideMotionEnabled } from '../domain/sampleDecision'

const { locale } = useI18n()
const root = ref<HTMLElement | null>(null)
const guideVideo = ref<HTMLVideoElement | null>(null)
const activeChapter = ref('understand')
const roleIndex = ref(0)
const age = ref(34)
const resident = ref(true)
const riskFlag = ref(false)
let sectionObserver: IntersectionObserver | undefined
let disposeMotion: (() => void) | undefined

const currentLocale = computed<GuideLocale>(() => (locale.value === 'ko' ? 'ko' : 'en'))
const content = computed(() => guideContent[currentLocale.value])
const sampleResult = computed(() => evaluateSampleDecision({ age: age.value, resident: resident.value, riskFlag: riskFlag.value }))
const currentRole = computed(() => content.value.roles.items[roleIndex.value] ?? content.value.roles.items[0])
const roleImages = ['/guide/role-maker.webp', '/guide/role-checker.webp', '/guide/role-reviewer.webp', '/guide/role-deployer.webp']
const currentRoleImage = computed(() => roleImages[roleIndex.value] ?? roleImages[0])
const currentRoleAlt = computed(() => content.value.media.roleAlts[roleIndex.value] ?? content.value.media.roleAlts[0])

watch(currentLocale, async () => {
  await nextTick()
  syncCaptionTrack()
})

onMounted(async () => {
  sectionObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (visible?.target.id) activeChapter.value = visible.target.id
    },
    { rootMargin: '-18% 0px -62% 0px', threshold: [0, .2, .5] },
  )
  root.value?.querySelectorAll<HTMLElement>('[data-guide-chapter]').forEach((section) => sectionObserver?.observe(section))
  await nextTick()
  await mountMotion()
})

onBeforeUnmount(() => {
  sectionObserver?.disconnect()
  disposeMotion?.()
})

function moveRole(direction: number) {
  roleIndex.value = (roleIndex.value + direction + content.value.roles.items.length) % content.value.roles.items.length
}

function syncCaptionTrack() {
  const video = guideVideo.value
  if (!video) return
  Array.from(video.textTracks).forEach((track) => {
    track.mode = track.language === currentLocale.value ? 'showing' : 'disabled'
  })
}

async function mountMotion() {
  if (!root.value || !guideMotionEnabled(window.matchMedia('(prefers-reduced-motion: reduce)'))) return
  gsap.registerPlugin(ScrollTrigger)
  const media = gsap.matchMedia()
  const context = gsap.context(() => {
    gsap.fromTo(
      '.guide-trust-word',
      { opacity: .12 },
      {
        opacity: 1,
        stagger: .08,
        ease: 'none',
        scrollTrigger: { trigger: '.guide-trust-copy', start: 'top 78%', end: 'bottom 38%', scrub: true },
      },
    )
    media.add('(min-width: 900px)', () => {
      ScrollTrigger.create({
        trigger: '.guide-journey-grid',
        start: 'top 112px',
        end: 'bottom 72%',
        pin: '.guide-journey-intro',
        pinSpacing: false,
      })
    })
  }, root.value)
  disposeMotion = () => {
    media.revert()
    context.revert()
  }
}
</script>

<template>
  <section ref="root" class="guide-page">
    <nav class="guide-local-nav" aria-label="Guide chapters">
      <a class="guide-nav-brand" href="#understand"><PhBookOpenText :size="18" /><strong>{{ content.nav.title }}</strong></a>
      <div>
        <a v-for="chapter in content.nav.chapters" :key="chapter.id" :href="`#${chapter.id}`" :class="{ active: activeChapter === chapter.id }">{{ chapter.label }}</a>
      </div>
    </nav>

    <main class="guide-content">
      <section id="understand" class="guide-hero" data-guide-chapter>
        <div class="guide-hero-inner max-w-6xl">
          <div class="guide-hero-copy">
            <p class="guide-eyebrow">{{ content.hero.eyebrow }}</p>
            <h1>
              <span class="guide-hero-line">{{ content.hero.titleLead }}</span>
              <em>{{ content.hero.titleEmphasis }} <span class="guide-inline-visual" aria-hidden="true"><i /><i /><i /></span></em>
              <span class="guide-hero-line">{{ content.hero.titleTail }}</span>
            </h1>
            <p class="guide-hero-body">{{ content.hero.body }}</p>
            <div class="guide-actions">
              <a class="guide-button guide-button-primary" href="#workflow">{{ content.hero.primary }}<PhArrowRight :size="16" /></a>
              <RouterLink class="guide-button guide-button-secondary" to="/overview">{{ content.hero.secondary }}</RouterLink>
            </div>
          </div>
          <figure class="guide-hero-art">
            <img src="/guide/guide-hero-lineage.webp" :alt="content.media.heroAlt" width="1200" height="1500" fetchpriority="high" decoding="async" />
            <figcaption><span>{{ content.hero.visualTitle }}</span>{{ content.hero.visualCaption }}</figcaption>
          </figure>
        </div>
      </section>

      <div class="guide-marquee" aria-label="Rule Platform trust capabilities">
        <div class="guide-marquee-track">
          <div><span v-for="item in content.marquee" :key="item">{{ item }}<i>◆</i></span></div>
          <div aria-hidden="true"><span v-for="item in content.marquee" :key="item">{{ item }}<i>◆</i></span></div>
        </div>
      </div>

      <section class="guide-video-section">
        <div class="guide-video-layout max-w-6xl">
          <header>
            <h2>{{ content.media.video.title }}</h2>
            <p>{{ content.media.video.body }}</p>
          </header>
          <div class="guide-video-frame">
            <video
              ref="guideVideo"
              controls
              playsinline
              preload="metadata"
              poster="/guide/rule-platform-guide-poster.webp"
              :aria-label="content.media.video.label"
              @loadedmetadata="syncCaptionTrack"
            >
              <source src="/guide/rule-platform-guide.mp4" type="video/mp4" />
              <track kind="captions" src="/guide/rule-platform-guide.en.vtt" srclang="en" :label="content.media.video.captionsEn" />
              <track kind="captions" src="/guide/rule-platform-guide.ko.vtt" srclang="ko" :label="content.media.video.captionsKo" />
              {{ content.media.video.fallback }}
            </video>
          </div>
        </div>
      </section>

      <section class="guide-section guide-principles">
        <div class="max-w-6xl">
          <header class="guide-heading">
            <p class="guide-eyebrow">{{ content.principles.eyebrow }}</p>
            <h2>{{ content.principles.title }}</h2>
            <p>{{ content.principles.body }}</p>
          </header>
          <div class="guide-bento">
            <article v-for="(card, index) in content.principles.cards" :key="card.title" :class="['guide-bento-card', `guide-bento-${index + 1}`]">
              <span class="guide-card-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <component :is="[PhDatabase, PhFingerprint, PhShieldCheck, PhTestTube, PhGitPullRequest][index]" :size="23" />
              <div><h3>{{ card.title }}</h3><p>{{ card.body }}</p><strong>{{ card.proof }}</strong></div>
            </article>
          </div>
        </div>
      </section>

      <section id="trust" class="guide-section guide-trust" data-guide-chapter>
        <div class="max-w-6xl guide-trust-layout">
          <div>
            <p class="guide-eyebrow">{{ content.trust.eyebrow }}</p>
            <h2>{{ content.trust.title }}</h2>
          </div>
          <div>
            <p class="guide-trust-copy" :aria-label="content.trust.words.join(' ')"><span v-for="(word, index) in content.trust.words" :key="`${word}-${index}`" class="guide-trust-word" aria-hidden="true">{{ word }} </span></p>
            <aside><PhShieldCheck :size="19" /><span>{{ content.trust.note }}</span></aside>
          </div>
          <figure class="guide-trust-media">
            <img src="/guide/guide-trust-boundary.webp" :alt="content.media.trustAlt" width="1600" height="900" loading="lazy" decoding="async" />
          </figure>
        </div>
      </section>

      <section id="workflow" class="guide-section guide-journey" data-guide-chapter>
        <div class="guide-journey-grid max-w-6xl">
          <div class="guide-journey-intro">
            <p class="guide-eyebrow">{{ content.workflow.eyebrow }}</p>
            <h2>{{ content.workflow.title }}</h2>
            <p>{{ content.workflow.body }}</p>
          </div>
          <div class="guide-journey-steps">
            <figure class="guide-journey-media">
              <img src="/guide/guide-workflow.webp" :alt="content.media.workflowAlt" width="1800" height="900" loading="lazy" decoding="async" />
            </figure>
            <article v-for="(step, index) in content.workflow.steps" :key="step.title">
              <header><span>{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ step.screen }}</strong></header>
              <h3>{{ step.title }}</h3>
              <p>{{ step.body }}</p>
              <RouterLink :to="step.to">{{ step.action }}<PhArrowRight :size="15" /></RouterLink>
            </article>
          </div>
        </div>
      </section>

      <section class="guide-section guide-roles">
        <div class="guide-role-shell max-w-6xl">
          <div class="guide-role-sidebar">
            <p class="guide-eyebrow">{{ content.roles.eyebrow }}</p>
            <h2>{{ content.roles.title }}</h2>
            <div class="guide-role-portraits" :aria-label="content.media.roleSelector">
              <button
                v-for="(role, index) in content.roles.items"
                :key="role.name"
                type="button"
                :aria-label="`${role.role}: ${role.name}`"
                :aria-pressed="roleIndex === index"
                :class="{ active: roleIndex === index }"
                @click="roleIndex = index"
              >
                <img :src="roleImages[index]" :alt="content.media.roleAlts[index]" width="640" height="640" loading="lazy" decoding="async" />
              </button>
            </div>
            <div class="guide-carousel-controls">
              <button type="button" :aria-label="content.media.previousRole" @click="moveRole(-1)"><PhCaretLeft :size="17" /></button>
              <button type="button" :aria-label="content.media.nextRole" @click="moveRole(1)"><PhCaretRight :size="17" /></button>
            </div>
          </div>
          <article class="guide-role-quote" aria-live="polite">
            <figure class="guide-role-visual"><img :src="currentRoleImage" :alt="currentRoleAlt" width="640" height="640" decoding="async" /></figure>
            <div class="guide-role-copy">
              <blockquote>“{{ currentRole?.quote }}”</blockquote>
              <footer><div><strong>{{ currentRole?.name }}</strong><span>{{ currentRole?.role }}</span></div><p>{{ currentRole?.responsibility }}</p></footer>
            </div>
          </article>
        </div>
      </section>

      <section id="simulate" class="guide-section guide-simulator" data-guide-chapter>
        <div class="max-w-6xl">
          <header class="guide-heading">
            <p class="guide-eyebrow">{{ content.simulator.eyebrow }}</p>
            <h2>{{ content.simulator.title }}</h2>
            <p>{{ content.simulator.body }}</p>
          </header>
          <div class="guide-simulator-shell">
            <form class="guide-simulator-inputs" @submit.prevent>
              <div class="guide-sample-notice"><PhCode :size="16" />{{ content.simulator.notice }}</div>
              <label class="guide-range"><span>{{ content.simulator.age }}</span><strong>{{ age }}</strong><input v-model.number="age" type="range" min="16" max="72" aria-label="Applicant age" /></label>
              <fieldset><legend>{{ content.simulator.resident }}</legend><div class="guide-toggle"><button type="button" :aria-pressed="resident" @click="resident = true">{{ content.simulator.yes }}</button><button type="button" :aria-pressed="!resident" @click="resident = false">{{ content.simulator.no }}</button></div></fieldset>
              <fieldset><legend>{{ content.simulator.risk }}</legend><div class="guide-toggle"><button type="button" :aria-pressed="riskFlag" @click="riskFlag = true">{{ content.simulator.yes }}</button><button type="button" :aria-pressed="!riskFlag" @click="riskFlag = false">{{ content.simulator.no }}</button></div></fieldset>
            </form>
            <output :class="['guide-simulator-result', sampleResult.outcome.toLowerCase()]" aria-live="polite">
              <span class="guide-result-icon"><PhCheckCircle :size="23" /></span>
              <small>{{ content.simulator.outcome }}</small>
              <strong>{{ content.simulator.outcomes[sampleResult.outcome] }}</strong>
              <p>{{ content.simulator.reasons[sampleResult.reason] }}</p>
              <div><span>{{ content.simulator.matched }}</span><code>{{ sampleResult.matchedRule }}</code></div>
            </output>
          </div>
        </div>
      </section>

      <section id="delivery" class="guide-section guide-delivery" data-guide-chapter>
        <div class="max-w-6xl">
          <header class="guide-heading">
            <p class="guide-eyebrow">{{ content.modes.eyebrow }}</p>
            <h2>{{ content.modes.title }}</h2>
            <p>{{ content.modes.body }}</p>
          </header>
          <figure class="guide-delivery-media">
            <img src="/guide/guide-delivery-modes.webp" :alt="content.media.deliveryAlt" width="1600" height="900" loading="lazy" decoding="async" />
          </figure>
          <div class="guide-mode-grid">
            <article><span><PhDatabase :size="21" /></span><h3>{{ content.modes.modeA.title }}</h3><p>{{ content.modes.modeA.body }}</p><strong>{{ content.modes.modeA.authority }}</strong></article>
            <article><span><PhCode :size="21" /></span><h3>{{ content.modes.modeB.title }}</h3><p>{{ content.modes.modeB.body }}</p><strong>{{ content.modes.modeB.authority }}</strong></article>
          </div>
        </div>
      </section>

      <section class="guide-section guide-glossary">
        <div class="max-w-6xl guide-glossary-layout">
          <header><p class="guide-eyebrow">{{ content.glossary.eyebrow }}</p><h2>{{ content.glossary.title }}</h2></header>
          <dl><div v-for="item in content.glossary.items" :key="item.term"><dt>{{ item.term }}</dt><dd>{{ item.definition }}</dd></div></dl>
        </div>
      </section>

      <section class="guide-cta">
        <div class="max-w-6xl">
          <h2>{{ content.cta.title }}</h2>
          <p>{{ content.cta.body }}</p>
          <div class="guide-actions"><RouterLink class="guide-button guide-button-primary" to="/imports">{{ content.cta.primary }}<PhArrowRight :size="16" /></RouterLink><RouterLink class="guide-button guide-button-dark" to="/overview">{{ content.cta.secondary }}</RouterLink></div>
          <footer><span>Rule Platform</span><span>Canonical IR · Governed evidence · Deterministic delivery</span></footer>
        </div>
      </section>
    </main>
  </section>
</template>
