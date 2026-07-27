<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhArrowRight, PhBookOpenText, PhInfo } from '@phosphor-icons/vue'
import { docsContent, type DocLocale } from '../content/docs'

const { locale } = useI18n()
const root = ref<HTMLElement | null>(null)
const activeSection = ref('')
let observer: IntersectionObserver | undefined

const currentLocale = computed<DocLocale>(() => (locale.value === 'ko' ? 'ko' : 'en'))
const content = computed(() => docsContent[currentLocale.value])

onMounted(() => {
  activeSection.value = content.value.sections[0]?.id ?? ''
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (visible?.target.id) activeSection.value = visible.target.id
    },
    { rootMargin: '-96px 0px -64% 0px', threshold: [0, 0.4, 1] },
  )
  root.value?.querySelectorAll<HTMLElement>('[data-doc-section]').forEach((section) => observer?.observe(section))
})

onBeforeUnmount(() => observer?.disconnect())

function goto(id: string) {
  activeSection.value = id
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <div ref="root" class="doc-page">
    <header class="page-header doc-header">
      <div class="doc-header-copy">
        <p class="page-kicker">{{ content.updated }}</p>
        <h1>{{ content.title }}</h1>
        <p>{{ content.subtitle }}</p>
      </div>
      <figure class="doc-hero-visual">
        <img
          :src="content.heroVisual.src"
          :alt="content.heroVisual.alt"
          :width="content.heroVisual.width"
          :height="content.heroVisual.height"
          fetchpriority="high"
          decoding="async"
        />
        <figcaption>{{ content.heroVisual.caption }}</figcaption>
      </figure>
    </header>

    <div class="doc-layout">
      <nav class="doc-toc" :aria-label="content.tocTitle">
        <p class="doc-toc-title"><PhBookOpenText :size="16" />{{ content.onThisPage }}</p>
        <a
          v-for="section in content.sections"
          :key="section.id"
          :href="`#${section.id}`"
          :class="{ active: activeSection === section.id }"
          @click.prevent="goto(section.id)"
        >{{ section.title }}</a>
      </nav>

      <div class="doc-content">
        <section
          v-for="section in content.sections"
          :id="section.id"
          :key="section.id"
          class="doc-section"
          data-doc-section
        >
          <h2>{{ section.title }}</h2>
          <p v-if="section.lead" class="doc-lead">{{ section.lead }}</p>

          <figure
            v-if="section.visual"
            :class="['doc-visual', `doc-visual--${section.visual.variant}`]"
          >
            <img
              :src="section.visual.src"
              :alt="section.visual.alt"
              :width="section.visual.width"
              :height="section.visual.height"
              loading="lazy"
              decoding="async"
            />
            <figcaption>{{ section.visual.caption }}</figcaption>
          </figure>

          <p v-for="(paragraph, index) in section.body ?? []" :key="`p-${index}`" class="doc-paragraph">
            {{ paragraph }}
          </p>

          <ol v-if="section.steps?.length" class="doc-steps">
            <li v-for="(stepText, index) in section.steps" :key="`s-${index}`">{{ stepText }}</li>
          </ol>

          <aside v-if="section.note" class="doc-note">
            <PhInfo :size="18" /><span>{{ section.note }}</span>
          </aside>

          <div v-if="section.links?.length" class="doc-links">
            <RouterLink v-for="link in section.links" :key="link.to" :to="link.to" class="doc-link">
              {{ link.label }}<PhArrowRight :size="15" />
            </RouterLink>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
