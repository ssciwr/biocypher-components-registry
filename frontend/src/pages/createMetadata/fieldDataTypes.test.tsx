import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DatasetDetailsEditor } from './MetadataGeneratorFields'
import { emptyDataset } from './options'
import { dataTypeSelectionValue, fieldDataTypeOptions } from './fieldDataTypes'
import type { DatasetDraft, DatasetDatasetManualField, DatasetMode } from './types'
import { datasetDraftToDocument, datasetUIStateDraftFromCroissantFile } from './utils'

function project(dataType: unknown, mode: DatasetMode) {
  const document = {
    '@type': 'sc:Dataset', name: 'Example',
    distribution: [{ '@id': 'data', contentUrl: 'data.tsv' }],
    recordSet: [{ '@id': 'records', name: 'records', field: [{
      '@id': 'records/value', name: 'value', description: 'Original', dataType,
      source: { fileObject: { '@id': 'data' }, extract: { column: 'value' } },
    }] }],
  }
  return { document, draft: datasetUIStateDraftFromCroissantFile(document, { ...emptyDataset, mode }) }
}

function editField(draft: DatasetDraft, edit: Partial<DatasetDatasetManualField>): DatasetDraft {
  return {
    ...draft,
    fields: draft.fields.map(field => ({ ...field, ...edit })),
    recordSets: draft.recordSets.map(recordSet => ({ ...recordSet, fields: recordSet.fields.map(field => ({ ...field, ...edit })) })),
    uploadedDirtyFields: ['fields'],
  }
}

function exportedType(draft: DatasetDraft) {
  const result = datasetDraftToDocument(draft)
  const recordSets = result.recordSet as Array<{ field: Array<{ dataType: unknown }> }>
  return recordSets[0]!.field[0]!.dataType
}

function renderEditor(dataset: DatasetDraft) {
  return renderToStaticMarkup(<DatasetDetailsEditor
    dataset={dataset}
    datasetManualField={{ id: 'manual', fieldId: '', name: '', dataType: '', description: '', example: '' }}
    licenseOptions={[]}
    onAddManualField={() => {}}
    onChange={() => {}}
    onDistributionChange={() => {}}
    onFieldChange={() => {}}
    onManualFieldChange={() => {}}
    onRemoveField={() => {}}
    onRecordSetNameChange={() => {}}
  />)
}

describe.each(['generate', 'upload'] as const)('%s dataset datatypes', (mode) => {
  it.each([
    'cr:Int64', 'cr:UInt32', 'cr:Float32', 'sc:DateTime',
    'https://example.org/types/Custom',
    ['sc:Integer'], ['cr:Int64', 'https://example.org/types/Identifier'],
    { '@type': 'sc:DefinedTerm', name: 'Custom type', termCode: 'custom' },
  ])('displays and preserves %j through unrelated edits', (dataType) => {
    const { document, draft } = project(dataType, mode)
    const label = dataTypeSelectionValue(dataType)
    const markup = renderEditor(draft)
    const encodedLabel = renderToStaticMarkup(<>{label}</>)
    expect(markup).toContain(`selected="">${encodedLabel}</option>`)
    expect(exportedType(draft)).toEqual(dataType)
    expect(exportedType(editField(draft, { description: 'Edited description' }))).toEqual(dataType)
    expect(document.recordSet[0]!.field[0]!.dataType).toEqual(dataType)
  })

  it('changes the datatype only when a replacement is selected', () => {
    const { draft } = project(['cr:Int64', 'https://example.org/types/Identifier'], mode)
    expect(exportedType(editField(draft, { dataType: 'sc:Float' }))).toEqual(['sc:Float'])
    const scalar = project('cr:Int64', mode).draft
    expect(exportedType(editField(scalar, { dataType: 'sc:Float' }))).toBe('sc:Float')
  })
})

describe('datatype compatibility', () => {
  it('includes Baker numeric widths and existing Native types', () => {
    const values = fieldDataTypeOptions('').map(option => option.value)
    expect(values).toEqual(expect.arrayContaining([
      'sc:Text', 'sc:Integer', 'sc:Float', 'sc:Boolean',
      'cr:Int8', 'cr:Int16', 'cr:Int32', 'cr:Int64',
      'cr:UInt8', 'cr:UInt16', 'cr:UInt32', 'cr:UInt64',
      'cr:Float16', 'cr:Float32', 'cr:Float64',
    ]))
  })

  it('preserves a datatype array from an older generated draft', () => {
    const original = ['sc:Text', 'https://example.org/types/Identifier']
    const { draft } = project(original, 'generate')
    const oldDraft = editField(draft, { originalDataType: undefined, dataType: original.join(', ') })
    expect(exportedType(oldDraft)).toEqual(original)
  })
})
