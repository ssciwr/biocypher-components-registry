import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DatasetSourceInput } from './MetadataGeneratorFields'
import type { DatasetSourceSelection } from './types'

function renderSelection(selection: DatasetSourceSelection) {
  return renderToStaticMarkup(<DatasetSourceInput selection={selection} onChange={() => {}} />)
}

describe('source file checklist', () => {
  it('shows paths, checked state and the included count for folder selections', () => {
    const file = new File(['id\n1'], 'actions.tsv')
    const markup = renderSelection({ kind: 'folder', name: 'STITCH', entries: [
      { file, relativePath: 'actions.tsv' },
      { file, relativePath: 'nested/links.tsv', excluded: true },
    ] })
    expect(markup).toContain('actions.tsv</span>')
    expect(markup).toContain('nested/links.tsv</span>')
    expect(markup).toContain('1 of 2 files included.')
    expect(markup.match(/type="checkbox"/g)).toHaveLength(2)
    expect(markup.match(/checked=""/g)).toHaveLength(1)
  })

  it('keeps an excluded single file visible with an actionable empty-selection message', () => {
    const markup = renderSelection({ kind: 'file', name: 'actions.tsv', entries: [
      { file: new File(['id\n1'], 'actions.tsv'), relativePath: 'actions.tsv', excluded: true },
    ] })
    expect(markup).toContain('actions.tsv</span>')
    expect(markup).not.toContain('checked=""')
    expect(markup).toContain('Select at least one source file to include.')
  })
})
