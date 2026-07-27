import { describe, expect, it } from 'vitest'

import { router } from './router'

describe('application routes', () => {
  it('keeps the landing page, all governed workflow screens and the docs addressable', () => {
    const names = router.getRoutes().map((route) => route.name).filter(Boolean)
    expect(names).toEqual(expect.arrayContaining(['login', 'landing', 'overview', 'guide', 'decisions', 'studio', 'imports', 'reviews', 'test-suites', 'releases', 'sites', 'operations']))
    expect(names).toHaveLength(12)
  })

  it('serves the landing page at the root with a blank layout', () => {
    const landing = router.getRoutes().find((route) => route.name === 'landing')
    expect(landing?.path).toBe('/')
    expect(landing?.meta.layout).toBe('blank')
  })

  it('serves login as the only public application route', () => {
    const routes = router.getRoutes()
    expect(routes.find((route) => route.name === 'login')?.meta.public).toBe(true)
    expect(routes.filter((route) => route.meta.public).map((route) => route.name)).toEqual(['login'])
  })
})
