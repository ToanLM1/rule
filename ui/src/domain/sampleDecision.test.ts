import { describe, expect, it } from 'vitest'

import { evaluateSampleDecision, guideMotionEnabled } from './sampleDecision'

describe('illustrative guide decision', () => {
  it('accepts the inclusive age boundaries', () => {
    expect(evaluateSampleDecision({ age: 18, resident: true, riskFlag: false }).outcome).toBe('ELIGIBLE')
    expect(evaluateSampleDecision({ age: 65, resident: true, riskFlag: false }).outcome).toBe('ELIGIBLE')
  })

  it('rejects ages outside the illustrative range', () => {
    expect(evaluateSampleDecision({ age: 17, resident: true, riskFlag: false })).toMatchObject({ outcome: 'INELIGIBLE', matchedRule: 'ELG-AGE-01' })
    expect(evaluateSampleDecision({ age: 66, resident: true, riskFlag: false })).toMatchObject({ outcome: 'INELIGIBLE', matchedRule: 'ELG-AGE-01' })
  })

  it('routes residency and risk flags to distinct manual reviews', () => {
    expect(evaluateSampleDecision({ age: 34, resident: false, riskFlag: false }).matchedRule).toBe('ELG-RES-02')
    expect(evaluateSampleDecision({ age: 34, resident: true, riskFlag: true }).matchedRule).toBe('ELG-RISK-03')
  })

  it('disables motion when reduced motion is requested', () => {
    expect(guideMotionEnabled({ matches: true })).toBe(false)
    expect(guideMotionEnabled({ matches: false })).toBe(true)
  })
})
