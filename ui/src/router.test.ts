import { describe, expect, it } from 'vitest'

import { router } from './router'

describe('application routes', () => {
  it('keeps all governed workflow screens and the business guide addressable', () => {
    const names = router.getRoutes().map((route) => route.name).filter(Boolean)
    expect(names).toEqual(expect.arrayContaining(['overview', 'guide', 'decisions', 'studio', 'imports', 'reviews', 'test-suites', 'releases', 'sites', 'operations']))
    expect(names).toHaveLength(10)
  })
})
