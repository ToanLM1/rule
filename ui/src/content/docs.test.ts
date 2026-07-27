import { describe, expect, it } from 'vitest'

import { docsContent } from './docs'

describe('docs content', () => {
  it('keeps the same guide structure and visual placement across locales', () => {
    const english = docsContent.en
    const korean = docsContent.ko

    expect(korean.sections.map((section) => section.id)).toEqual(
      english.sections.map((section) => section.id),
    )
    expect(korean.heroVisual.src).toBe(english.heroVisual.src)

    const englishVisuals = english.sections
      .filter((section) => section.visual)
      .map((section) => ({ id: section.id, src: section.visual?.src }))
    const koreanVisuals = korean.sections
      .filter((section) => section.visual)
      .map((section) => ({ id: section.id, src: section.visual?.src }))

    expect(koreanVisuals).toEqual(englishVisuals)
    expect(englishVisuals.map((visual) => visual.id)).toEqual(['journey', 'author', 'release'])
  })

  it.each(['en', 'ko'] as const)('provides accessible, dimensioned visuals for %s', (locale) => {
    const content = docsContent[locale]
    const visuals = [
      content.heroVisual,
      ...content.sections.flatMap((section) => (section.visual ? [section.visual] : [])),
    ]

    expect(visuals).toHaveLength(4)
    for (const visual of visuals) {
      expect(visual.src).toMatch(/^\/guide\/slides\/.+\.(webp|svg)$/)
      expect(visual.alt.trim()).not.toBe('')
      expect(visual.caption.trim()).not.toBe('')
      expect(visual.width).toBeGreaterThan(0)
      expect(visual.height).toBeGreaterThan(0)
    }
  })
})
