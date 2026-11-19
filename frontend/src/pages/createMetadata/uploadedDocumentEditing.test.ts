import { describe, expect, it } from 'vitest'
import { applyCroissantDocumentEdits } from './uploadedDocumentEditing'

function socialSentimentDocument() {
  return {
    '@type': 'sc:Dataset',
    name: 'Social Media Sentiments Analysis Dataset 📊',
    version: 3,
    license: {
      '@type': 'sc:CreativeWork',
      name: 'CC0: Public Domain',
      url: 'https://creativecommons.org/publicdomain/zero/1.0/',
    },
    creator: {
      '@type': 'sc:Person',
      name: 'Kashish Parmar',
      url: '/kashishparmar02',
      image: 'https://storage.googleapis.com/kaggle-avatars/default-thumb.png',
    },
    publisher: {
      '@type': 'sc:Organization',
      name: 'Kaggle',
    },
    distribution: [
      {
        '@id': 'archive.zip',
        name: 'archive.zip',
        contentUrl: 'https://www.kaggle.com/api/v1/datasets/download/example',
        encodingFormat: 'application/zip',
        md5: 'sTkxKpM2Ps0MuOBXXXmHFA==',
      },
      {
        '@id': 'sentimentdataset.csv_fileobject',
        name: 'sentimentdataset.csv',
        contentUrl: 'sentimentdataset.csv',
        containedIn: { '@id': 'archive.zip' },
        encodingFormat: 'text/csv',
      },
    ],
    recordSet: [{
      '@id': 'sentimentdataset.csv',
      name: 'sentimentdataset.csv',
      field: [{
        '@id': 'sentimentdataset.csv/',
        name: '',
        source: {
          fileObject: { '@id': 'sentimentdataset.csv_fileobject' },
          extract: { column: '' },
        },
      }],
    }],
    thumbnailUrl: 'https://example.org/dataset-card.png',
  }
}

describe('lossless uploaded Croissant document editing', () => {
  it('returns a structurally identical copy when there are no edits', () => {
    const original = socialSentimentDocument()
    const result = applyCroissantDocumentEdits(original, [])

    expect(result).toEqual(original)
    expect(result).not.toBe(original)
  })

  it('changes only the explicitly edited top-level property', () => {
    const original = socialSentimentDocument()
    const result = applyCroissantDocumentEdits(original, [{
      path: ['name'],
      value: 'Social Media Sentiment Dataset',
    }])

    expect(result).toEqual({ ...original, name: 'Social Media Sentiment Dataset' })
    expect(original.name).toBe('Social Media Sentiments Analysis Dataset 📊')
  })

  it('preserves unsupported creator properties during a supported nested edit', () => {
    const original = socialSentimentDocument()
    const result = applyCroissantDocumentEdits(original, [{
      path: ['creator', 'name'],
      value: 'Kashish A. Parmar',
    }])

    expect(result.creator).toEqual({
      ...original.creator,
      name: 'Kashish A. Parmar',
    })
    expect((result.creator as Record<string, unknown>).image).toBe(original.creator.image)
  })

  it('edits one distribution without reconstructing its siblings or relationships', () => {
    const original = socialSentimentDocument()
    const replacementUrl = 'https://example.org/releases/archive.zip'
    const result = applyCroissantDocumentEdits(original, [{
      path: ['distribution', 0, 'contentUrl'],
      value: replacementUrl,
    }])

    expect(result.distribution).toEqual([
      { ...original.distribution[0], contentUrl: replacementUrl },
      original.distribution[1],
    ])
  })

  it('removes only an explicitly targeted property', () => {
    const original = socialSentimentDocument()
    const result = applyCroissantDocumentEdits(original, [{
      operation: 'remove',
      path: ['creator', 'url'],
    }])

    expect(result.creator).toEqual({
      '@type': 'sc:Person',
      name: 'Kashish Parmar',
      image: original.creator.image,
    })
  })

  it('rejects edits outside the existing document structure', () => {
    expect(() => applyCroissantDocumentEdits(socialSentimentDocument(), [{
      path: ['distribution', 4, 'name'],
      value: 'missing.csv',
    }])).toThrow('path does not exist')
  })
})
