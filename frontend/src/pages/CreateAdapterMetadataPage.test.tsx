import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { MetadataValidationResponse, ValidationCheckResponse } from '../api/client'
import { CapacityWaitPanel, MetadataReadyPanel } from './CreateAdapterMetadataPage'

function validation(isValid: boolean, warnings: string[] = []): MetadataValidationResponse {
  return {
    kind: 'adapter',
    is_valid: isValid,
    profile_version: 'v1',
    errors: isValid ? [] : ['Blocking validation error'],
    warnings,
    checks: [],
    validation_details: [],
    validation_checks: [],
  }
}

function failedDatasetCheck(index: number): ValidationCheckResponse {
  return {
    id: `dataset:${index}`,
    name: `Dataset ${index + 1}`,
    status: 'FAILED',
    parent_id: 'datasets',
    dataset_index: index,
    errors: ['Blocking dataset error'],
    warnings: [],
    validation_details: [],
  }
}

function render(
  result: MetadataValidationResponse | null,
  metadata: Record<string, unknown> = { hasPart: [] },
): string {
  return renderToStaticMarkup(
    <MetadataReadyPanel
      adapterName="Example adapter"
      metadata={metadata}
      metadataJson="{}"
      onBack={() => undefined}
      validation={result}
    />,
  )
}

describe('finished Croissant download', () => {
  it('is disabled when the adapter or an embedded dataset has a blocking error', () => {
    const html = render(validation(false))

    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*Download finished Croissant file/s)
    expect(html).toContain('Download unavailable because the adapter or one of its datasets has validation errors.')
  })

  it('remains enabled when validation passes with advisory warnings', () => {
    const html = render(validation(true, ['citeAs is recommended.']))
    const downloadButton = html.match(/<button[^>]*>.*?Download finished Croissant file.*?<\/button>/s)?.[0]

    expect(downloadButton).toBeDefined()
    expect(downloadButton).not.toContain('disabled=""')
    expect(html).not.toContain('croissant-download-unavailable')
  })

  it('is disabled until a validation result is available', () => {
    const html = render(null)

    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*Download finished Croissant file/s)
    expect(html).toContain('Download unavailable until validation is complete.')
  })

  it('describes an adapter-only validation failure without claiming a dataset failed', () => {
    const html = render(validation(false), { hasPart: [{ name: 'Dataset' }] })

    expect(html).toContain('The adapter needs attention.')
    expect(html).not.toContain('dataset needs attention')
  })

  it('uses singular grammar when the only embedded dataset fails validation', () => {
    const result = validation(false)
    result.validation_checks = [failedDatasetCheck(0)]

    const html = render(result, { hasPart: [{ name: 'Dataset' }] })

    expect(html).toContain('1 of 1 dataset needs attention.')
  })

  it('reports multiple failed datasets while preserving the total dataset count', () => {
    const result = validation(false)
    result.validation_checks = [failedDatasetCheck(0), failedDatasetCheck(2)]

    const html = render(result, {
      hasPart: [{ name: 'First' }, { name: 'Second' }, { name: 'Third' }],
    })

    expect(html).toContain('2 of 3 datasets need attention.')
  })
})

describe('dataset generation capacity status', () => {
  it('announces the wait with output while keeping controls outside the status', () => {
    const html = renderToStaticMarkup(<CapacityWaitPanel wait={{
      attempt: 2,
      cancel: () => undefined,
      isRetrying: false,
      retryAfterSeconds: 15,
      retryNow: () => undefined,
    }} />)

    expect(html).toContain('<output')
    expect(html).not.toContain('role="status"')
    expect(html).toContain('Capacity was still full after attempt 2.')
    expect(html.indexOf('</output>')).toBeLessThan(html.indexOf('Retry now'))
    expect(html).toContain('Cancel')
  })

  it('disables both controls while an admission retry is in progress', () => {
    const html = renderToStaticMarkup(<CapacityWaitPanel wait={{
      attempt: 1,
      cancel: () => undefined,
      isRetrying: true,
      retryAfterSeconds: 15,
      retryNow: () => undefined,
    }} />)

    expect(html).toContain('Retrying admission now. Your prepared dataset remains unchanged.')
    expect(html.match(/disabled=""/g)).toHaveLength(2)
  })
})
