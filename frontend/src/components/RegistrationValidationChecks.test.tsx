import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ValidationCheckResponse } from '../api/client'
import { RegistrationValidationChecks } from './RegistrationValidationChecks'

const extractError = 'Extract should have one of the following properties http://mlcommons.org/croissant/column or http://mlcommons.org/croissant/fileProperty or http://mlcommons.org/croissant/jsonPath.'

function check(values: Partial<ValidationCheckResponse> & Pick<ValidationCheckResponse, 'id' | 'name' | 'status'>): ValidationCheckResponse {
  return { errors: [], warnings: [], validation_details: [], ...values }
}

describe('shared validation result presentation', () => {
  it('uses a stacked hierarchy and opens the failed dataset by default', () => {
    const checks = [
      check({ id: 'croissant', name: 'Complete-file compatibility', status: 'PASSED', validator_name: 'mlcroissant', validator_version: '1.1.1' }),
      check({ id: 'datasets', name: 'Embedded datasets', status: 'FAILED' }),
      check({ id: 'dataset:0', name: 'OmniPath', status: 'PASSED', parent_id: 'datasets', dataset_index: 0 }),
      check({ id: 'dataset:1', name: 'Social Media Sentiments', status: 'FAILED', parent_id: 'datasets', dataset_index: 1, errors: [extractError] }),
    ]

    const html = renderToStaticMarkup(<RegistrationValidationChecks checks={checks} />)

    expect(html).not.toContain('<table')
    expect(html).toContain('Embedded datasets')
    expect(html).toContain('Dataset 2')
    expect(html).toContain('aria-expanded="true"')
    expect(html).toContain('http://mlcommons.org/croissant/column')
    expect(html).toContain('http://mlcommons.org/croissant/fileProperty')
    expect(html).toContain('http://mlcommons.org/croissant/jsonPath')
  })

  it('keeps a passed expandable check collapsed by default', () => {
    const html = renderToStaticMarkup(<RegistrationValidationChecks checks={[
      check({ id: 'schema', name: 'Adapter schema', status: 'PASSED', profile_version: 'v1' }),
    ]} />)

    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('Passed')
  })

  it('shows exact non-blocking validator warnings and expands them by default', () => {
    const warning = '[Metadata(Example)] Property "http://mlcommons.org/croissant/citeAs" is recommended, but does not exist.'
    const html = renderToStaticMarkup(<RegistrationValidationChecks checks={[
      check({ id: 'datasets', name: 'Embedded datasets', status: 'PASSED' }),
      check({ id: 'dataset:0', name: 'Example', status: 'PASSED', parent_id: 'datasets', warnings: [warning] }),
    ]} />)

    expect(html).toContain('Passed with warnings')
    expect(html).toContain('aria-expanded="true"')
    expect(html).toContain(warning.replace(/"/g, '&quot;'))
    expect(html).toContain('Validation warnings (1)')
  })
})
