export type SampleDecisionInputs = {
  age: number
  resident: boolean
  riskFlag: boolean
}

export type SampleDecisionResult = {
  outcome: 'INELIGIBLE' | 'MANUAL_REVIEW' | 'ELIGIBLE'
  matchedRule: 'ELG-AGE-01' | 'ELG-RES-02' | 'ELG-RISK-03' | 'ELG-PASS-04'
  reason: 'AGE_OUT_OF_RANGE' | 'RESIDENCY_REVIEW' | 'RISK_REVIEW' | 'ELIGIBLE'
}

export function evaluateSampleDecision(inputs: SampleDecisionInputs): SampleDecisionResult {
  if (inputs.age < 18 || inputs.age > 65) {
    return { outcome: 'INELIGIBLE', matchedRule: 'ELG-AGE-01', reason: 'AGE_OUT_OF_RANGE' }
  }
  if (!inputs.resident) {
    return { outcome: 'MANUAL_REVIEW', matchedRule: 'ELG-RES-02', reason: 'RESIDENCY_REVIEW' }
  }
  if (inputs.riskFlag) {
    return { outcome: 'MANUAL_REVIEW', matchedRule: 'ELG-RISK-03', reason: 'RISK_REVIEW' }
  }
  return { outcome: 'ELIGIBLE', matchedRule: 'ELG-PASS-04', reason: 'ELIGIBLE' }
}

export function guideMotionEnabled(mediaQuery: Pick<MediaQueryList, 'matches'>): boolean {
  return !mediaQuery.matches
}
