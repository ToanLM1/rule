import { describe, expect, it } from 'vitest'

import { guideContent } from './guide'

function contentShape(value: unknown): unknown {
  if (Array.isArray(value)) return { arrayItem: contentShape(value[0]) }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, contentShape(nested)]))
  }
  return typeof value
}

describe('business guide content', () => {
  it('keeps English and Korean content structurally identical', () => {
    expect(contentShape(guideContent.en)).toEqual(contentShape(guideContent.ko))
  })

  it('uses the same chapter anchors in both locales', () => {
    expect(guideContent.en.nav.chapters.map((chapter) => chapter.id)).toEqual(
      guideContent.ko.nav.chapters.map((chapter) => chapter.id),
    )
  })

  it('keeps repeatable content collections aligned', () => {
    expect([
      guideContent.en.principles.cards.length,
      guideContent.en.workflow.steps.length,
      guideContent.en.roles.items.length,
      guideContent.en.glossary.items.length,
    ]).toEqual([
      guideContent.ko.principles.cards.length,
      guideContent.ko.workflow.steps.length,
      guideContent.ko.roles.items.length,
      guideContent.ko.glossary.items.length,
    ])
  })
})
