import { describe, expect, it } from 'vitest'
import { includedSourceEntries, selectionFromFile, selectionFromFolderFiles, setSourceEntryIncluded } from './datasetSourceSelection'

describe('dataset source selection', () => {
  it('includes files by default and allows exclusion and reselection without losing paths', () => {
    const file = new File(['id\n1'], 'first.csv')
    const selection = { kind: 'folder' as const, name: 'dataset', entries: [
      { file, relativePath: 'first.csv' },
      { file, relativePath: 'nested/first.csv' },
    ] }
    expect(includedSourceEntries(selection)).toHaveLength(2)
    const excluded = setSourceEntryIncluded(selection, 1, false)
    expect(includedSourceEntries(excluded).map(entry => entry.relativePath)).toEqual(['first.csv'])
    expect(excluded.entries).toHaveLength(2)
    expect(selection.entries[1]).not.toHaveProperty('excluded')
    expect(includedSourceEntries(setSourceEntryIncluded(excluded, 1, true))).toHaveLength(2)
  })

  it('creates a single-file selection', () => {
    const file = new File(['id,name\n1,Alice\n'], 'people.csv', { type: 'text/csv' })

    expect(selectionFromFile(file)).toEqual({
      entries: [{ file, relativePath: 'people.csv' }],
      kind: 'file',
      name: 'people.csv',
    })
  })

  it('creates a folder selection from a browser directory picker', () => {
    const first = new File(['id\n1\n'], 'first.csv')
    const second = new File(['id\n2\n'], 'second.csv')
    Object.defineProperty(first, 'webkitRelativePath', { value: 'dataset/first.csv' })
    Object.defineProperty(second, 'webkitRelativePath', { value: 'dataset/nested/second.csv' })

    const selection = selectionFromFolderFiles([first, second] as unknown as FileList)

    expect(selection.kind).toBe('folder')
    expect(selection.name).toBe('dataset')
    expect(selection.entries.map((entry) => entry.relativePath)).toEqual([
      'first.csv',
      'nested/second.csv',
    ])
  })
})
