import { expect, test } from '@playwright/test'

const candidate = {
  decisionId: 'eligibility', decisionName: '가입 자격', profile: 'RULE_IR_V1', schemaVersion: 1,
  programContexts: [{ programId: 'LOCAL', kind: 'SERVICE', entryPoint: 'local://test' }],
  hitPolicy: 'FIRST', inputs: [{ name: 'age', type: 'integer', required: true }],
  outputs: [{ name: 'result', type: 'string' }], defaultOutput: { result: '가입 가능' },
  rules: [{ ruleId: 'R001', when: { all: [{ left: { kind: 'INPUT', name: 'age' }, operator: 'LT', right: { kind: 'LITERAL', value: 18 } }] }, then: [{ output: 'result', value: '미성년' }], origin: 'EXTRACTED', sourceReferences: [], confidence: 1 }],
}

test('Phase 3 workbench extracts, generates, and preflights without console errors', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  await page.route('http://localhost:8100/**', async (route) => {
    const url = route.request().url()
    let json: unknown = {}
    if (url.endsWith('/orchestration/catalog')) json = {
      evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE', persistent: false,
      adapters: ['db-postgres-stored-object', 'ui-html-validation', 'engine-native', 'engine-dmn'],
      generators: ['dmn-export', 'csharp-source'],
      hostInventory: { java: true, dotnet: false, joern: true, zen: true, postgres: true, sqlite: true },
      boundaries: ['Inputs are isolated', 'Scripts are never executed'],
    }
    else if (url.endsWith('/orchestration/extract')) json = {
      evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE', persistent: false,
      batch: { adapter: 'db-postgres-stored-object', decisions: [{ decisionKey: 'eligibility', content: candidate }], unmappable: [], diagnostics: [], sourceSnapshot: { contentHash: 'a'.repeat(64), revision: 'v1' } },
    }
    else if (url.endsWith('/orchestration/generate')) json = {
      generator: 'dmn-export', evidenceLabel: 'LOCAL_PREVIEW_NON_AUTHORITATIVE', persistent: false,
      authoritative: false, path: 'preview/eligibility.dmn', content: '<decisionTable hitPolicy="FIRST"/>', contentHash: 'b'.repeat(64),
    }
    else if (url.endsWith('/orchestration/preflight')) json = {
      schemaVersion: 1, reports: [{ site: 'local-workbench', ready: true }], matrixHash: 'c'.repeat(64),
    }
    await route.fulfill({ json })
  })

  await page.goto('/orchestration')
  await expect(page.getByRole('heading', { name: 'Phase 3 workbench' })).toBeVisible()
  await page.getByRole('button', { name: 'Run restricted extraction' }).click()
  await expect(page.getByTestId('candidate-output')).toContainText('미성년')
  await page.getByRole('button', { name: 'Continue to target preview' }).click()
  await page.getByRole('button', { name: 'Generate preview' }).click()
  await expect(page.getByTestId('generated-output')).toContainText('decisionTable')
  await page.getByRole('button', { name: '3. Preflight' }).click()
  await page.getByRole('button', { name: 'Run capability preflight' }).click()
  await expect(page.getByTestId('preflight-output')).toContainText('local-workbench')
  await page.screenshot({ path: '../output/playwright/phase3-orchestration.png', fullPage: true })
  expect(errors).toEqual([])
})
