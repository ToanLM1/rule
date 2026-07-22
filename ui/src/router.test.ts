import { describe, expect, it } from 'vitest'

import { router } from './router'

describe('application routes', () => {
  it('keeps all eight governed workflow screens addressable', () => {
    const names = router.getRoutes().map((route) => route.name).filter(Boolean)
    expect(names).toEqual(expect.arrayContaining(['overview', 'decisions', 'imports', 'reviews', 'test-suites', 'releases', 'sites', 'operations']))
    expect(names).toHaveLength(8)
  })
})
