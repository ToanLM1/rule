import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DecisionsPage from './DecisionsPage.vue'

describe('DecisionsPage', () => {
  it('renders the governance entry point', () => {
    const wrapper = mount(DecisionsPage, {
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.get('h1').text()).toBe('Decisions')
    expect(wrapper.text()).toContain('http://localhost:8100')
  })
})
