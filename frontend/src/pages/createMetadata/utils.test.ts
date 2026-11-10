import { describe, expect, it } from 'vitest'
import { emptyDataset } from './options'
import { datasetDraftToDocument, datasetUIStateDraftFromCroissantFile } from './utils'

describe('generated dataset metadata merge', () => {
  it('preserves the dataset license explicitly selected by the user', () => {
    const draft = {
      ...emptyDataset,
      license: 'CC-BY-4.0',
    }

    const merged = datasetUIStateDraftFromCroissantFile(
      { license: 'https://creativecommons.org/licenses/by/4.0/' },
      draft,
    )

    expect(merged.license).toBe('CC-BY-4.0')
  })

  it('uses the generated license when the user did not select one', () => {
    const merged = datasetUIStateDraftFromCroissantFile(
      { license: 'https://creativecommons.org/licenses/by/4.0/' },
      { ...emptyDataset },
    )

    expect(merged.license).toBe('https://creativecommons.org/licenses/by/4.0/')
  })

  it('preserves the mandatory download URL supplied by the user', () => {
    const merged = datasetUIStateDraftFromCroissantFile(
      { distribution: [{ contentUrl: 'people.csv' }] },
      { ...emptyDataset, contentUrl: 'https://example.org/datasets/people.csv' },
    )

    expect(merged.contentUrl).toBe('https://example.org/datasets/people.csv')
  })
})

describe('uploaded Croissant metadata', () => {
  it('submits the uploaded document unchanged', () => {
    const uploadedDocument = {
      '@context': { '@vocab': 'https://schema.org/' },
      '@type': 'sc:Dataset',
      distribution: [
        { '@id': 'archive.zip', '@type': 'cr:FileObject' },
        { '@id': 'data.csv_fileobject', '@type': 'cr:FileObject' },
      ],
      recordSet: [{
        '@id': 'data.csv',
        field: [{
          '@id': 'data.csv/value',
          dataType: ['sc:Text'],
          name: 'value',
          source: {
            extract: { column: 'value' },
            fileObject: { '@id': 'data.csv_fileobject' },
          },
        }],
      }],
    }
    const draft = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )

    const submitted = datasetDraftToDocument({
      ...draft,
      // Changes to the display projection must not rewrite an uploaded file.
      fields: [],
      filename: 'different.csv',
      name: 'Different title',
    })

    expect(submitted).not.toBe(uploadedDocument)
    expect(submitted).toEqual(uploadedDocument)
    expect(draft.fields[0]?.dataType).toBe('sc:Text')
  })

  it('applies only explicitly edited uploaded fields', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      name: 'Original title',
      version: 3,
      datePublished: '2025-02-03T14:30:00Z',
      license: { name: 'CC0', url: 'https://creativecommons.org/publicdomain/zero/1.0/' },
      creator: {
        '@type': 'sc:Person',
        image: 'https://example.org/avatar.png',
        name: 'Original creator',
      },
      thumbnailUrl: 'https://example.org/card.png',
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )
    const submitted = datasetDraftToDocument({
      ...projected,
      datasetVersion: '4',
      name: 'Edited title',
      uploadedDirtyFields: ['name', 'datasetVersion'],
    })

    expect(submitted).toEqual({
      ...uploadedDocument,
      name: 'Edited title',
      version: 4,
    })
    expect(submitted.license).toEqual(uploadedDocument.license)
    expect(submitted.datePublished).toBe(uploadedDocument.datePublished)
  })

  it('preserves unsupported creator properties while applying creator edits', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      creator: {
        '@type': 'sc:Person',
        image: 'https://example.org/avatar.png',
        name: 'Original creator',
        url: 'https://example.org/profile',
      },
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )
    const submitted = datasetDraftToDocument({
      ...projected,
      creators: [{ ...projected.creators[0]!, name: 'Edited creator', url: '' }],
      uploadedDirtyFields: ['creators'],
    })

    expect(submitted.creator).toEqual({
      '@type': 'sc:Person',
      image: 'https://example.org/avatar.png',
      name: 'Edited creator',
    })
  })

  it('does not inherit values from a previous draft when another file is uploaded', () => {
    const projected = datasetUIStateDraftFromCroissantFile(
      { '@type': 'sc:Dataset', name: 'Replacement dataset' },
      {
        ...emptyDataset,
        citation: 'Old citation',
        contentUrl: 'https://old.example/data.csv',
        creators: [{
          affiliation: '', creatorType: 'Person', email: '', id: 'old', name: 'Old creator', orcid: '', url: '',
        }],
        description: 'Old description',
        license: 'MIT',
        mode: 'upload',
        url: 'https://old.example',
      },
      'replacement.jsonld',
    )

    expect(projected.name).toBe('Replacement dataset')
    expect(projected.description).toBe('')
    expect(projected.citation).toBe('')
    expect(projected.contentUrl).toBe('')
    expect(projected.license).toBe('')
    expect(projected.url).toBe('')
    expect(projected.creators).toEqual([])
  })

  it('preserves creator values the form cannot represent when another creator field changes', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      creator: {
        '@type': 'sc:Person',
        affiliation: { '@type': 'sc:Organization', name: 'Example Institute' },
        identifier: { '@type': 'sc:PropertyValue', value: 'local-id' },
        name: 'Original creator',
      },
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )
    const submitted = datasetDraftToDocument({
      ...projected,
      creators: [{ ...projected.creators[0]!, name: 'Edited creator' }],
      uploadedDirtyFields: ['creators'],
    })

    expect(submitted.creator).toEqual({
      ...uploadedDocument.creator,
      name: 'Edited creator',
    })
  })

  it('edits uploaded fields losslessly and keeps source columns aligned', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      recordSet: [{
        '@id': 'sentimentdataset.csv',
        customProperty: 'preserve me',
        field: [{
          '@id': 'sentimentdataset.csv/',
          '@type': 'cr:Field',
          dataType: ['sc:Integer'],
          description: 'Index',
          name: '',
          source: {
            extract: { column: '' },
            fileObject: { '@id': 'sentimentdataset.csv_fileobject' },
          },
        }],
      }],
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )
    const submitted = datasetDraftToDocument({
      ...projected,
      recordSets: projected.recordSets.map((recordSet, index) => index === 0
        ? {
          ...recordSet,
          fields: [{
            ...recordSet.fields[0]!,
            description: 'Row number',
            name: 'row_id',
          }],
        }
        : recordSet),
      uploadedDirtyFields: ['fields'],
    })
    const recordSet = (submitted.recordSet as Record<string, unknown>[])[0]!
    const field = (recordSet.field as Record<string, unknown>[])[0]!

    expect(recordSet.customProperty).toBe('preserve me')
    expect(field).toMatchObject({
      '@id': 'sentimentdataset.csv/',
      dataType: ['sc:Integer'],
      description: 'Row number',
      name: 'row_id',
      source: {
        extract: { column: 'row_id' },
        fileObject: { '@id': 'sentimentdataset.csv_fileobject' },
      },
    })
  })

  it('edits one uploaded distribution without changing its container or siblings', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      distribution: [
        {
          '@id': 'archive.zip',
          '@type': 'cr:FileObject',
          contentSize: '50.925 KB',
          contentUrl: 'https://example.org/archive.zip',
          encodingFormat: 'application/zip',
          md5: 'sTkxKpM2Ps0MuOBXXXmHFA==',
          name: 'archive.zip',
        },
        {
          '@id': 'data.csv_fileobject',
          '@type': 'cr:FileObject',
          containedIn: { '@id': 'archive.zip' },
          contentUrl: 'data.csv',
          encodingFormat: 'text/csv',
          name: 'data.csv',
        },
      ],
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )

    expect(projected.distributions).toHaveLength(2)
    expect(projected.distributions[0]).toMatchObject({
      filename: 'archive.zip',
      md5: 'sTkxKpM2Ps0MuOBXXXmHFA==',
    })
    expect(projected.distributions[1]).toMatchObject({
      containedInLabel: 'archive.zip',
      contentUrl: 'data.csv',
    })

    const submitted = datasetDraftToDocument({
      ...projected,
      distributions: projected.distributions.map((distribution, index) => (
        index === 1 ? { ...distribution, sha256: 'published-checksum-value' } : distribution
      )),
      uploadedDirtyFields: ['distributions'],
    })
    const distributions = submitted.distribution as Record<string, unknown>[]

    expect(distributions[0]).toEqual(uploadedDocument.distribution[0])
    expect(distributions[1]).toEqual({
      ...uploadedDocument.distribution[1],
      sha256: 'published-checksum-value',
    })
  })

  it('projects and edits multiple record sets independently', () => {
    const uploadedDocument = {
      '@type': 'sc:Dataset',
      recordSet: [
        {
          '@id': 'first.csv',
          customProperty: 'first-value',
          field: [{ '@id': 'first.csv/id', dataType: ['sc:Integer'], name: 'id' }],
          name: 'first.csv',
        },
        {
          '@id': 'second.csv',
          customProperty: 'second-value',
          field: [{
            '@id': 'second.csv/value',
            dataType: ['sc:Text'],
            description: 'Original description',
            name: 'value',
            source: {
              extract: { column: 'value' },
              fileObject: { '@id': 'second.csv_fileobject' },
            },
          }],
          name: 'second.csv',
        },
      ],
    }
    const projected = datasetUIStateDraftFromCroissantFile(
      uploadedDocument,
      { ...emptyDataset, mode: 'upload' },
      'dataset.jsonld',
    )

    expect(projected.recordSets.map((recordSet) => recordSet.name)).toEqual([
      'first.csv',
      'second.csv',
    ])
    const submitted = datasetDraftToDocument({
      ...projected,
      recordSets: projected.recordSets.map((recordSet, index) => index === 1
        ? {
          ...recordSet,
          fields: recordSet.fields.map((field) => ({
            ...field,
            description: 'Edited description',
          })),
        }
        : recordSet),
      uploadedDirtyFields: ['fields'],
    })
    const recordSets = submitted.recordSet as Record<string, unknown>[]

    expect(recordSets[0]).toEqual(uploadedDocument.recordSet[0])
    expect(recordSets[1]).toMatchObject({
      '@id': 'second.csv',
      customProperty: 'second-value',
      field: [{
        '@id': 'second.csv/value',
        description: 'Edited description',
        source: {
          extract: { column: 'value' },
          fileObject: { '@id': 'second.csv_fileobject' },
        },
      }],
    })
  })
})

describe('generated Croissant metadata', () => {
  it('preserves additional distributions and record sets while applying form values', () => {
    const generatedDocument = {
      distribution: [
        { '@id': 'first.csv', '@type': 'cr:FileObject', name: 'first.csv' },
        { '@id': 'second.csv', '@type': 'cr:FileObject', name: 'second.csv' },
      ],
      recordSet: [
        { '@id': 'first-records', field: [], name: 'First records' },
        { '@id': 'second-records', field: [], name: 'Second records' },
      ],
    }
    const draft = datasetUIStateDraftFromCroissantFile(
      generatedDocument,
      {
        ...emptyDataset,
        contentUrl: 'https://example.org/first.csv',
        mode: 'generate',
        name: 'Edited dataset title',
      },
    )

    const submitted = datasetDraftToDocument(draft)

    expect(submitted.name).toBe('Edited dataset title')
    expect(submitted.distribution).toHaveLength(2)
    expect((submitted.distribution as Record<string, unknown>[])[1]?.['@id']).toBe('second.csv')
    expect(submitted.recordSet).toHaveLength(2)
    expect((submitted.recordSet as Record<string, unknown>[])[1]?.['@id']).toBe('second-records')
  })
})
