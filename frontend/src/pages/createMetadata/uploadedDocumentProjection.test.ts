import { describe, expect, it } from 'vitest'
import { emptyDataset } from './options'
import {
  datasetTopLevelProjectionFromCroissant,
  datasetUIStateDraftFromCroissantFile,
} from './utils'

const longDescription = 'Social sentiment dataset. '.repeat(130)

const socialSentimentMetadata: Record<string, unknown> = {
  name: 'Social Media Sentiments Analysis Dataset 📊',
  description: longDescription,
  version: 3,
  license: {
    '@type': 'sc:CreativeWork',
    name: 'CC0: Public Domain',
    url: 'https://creativecommons.org/publicdomain/zero/1.0/',
  },
  url: 'https://www.kaggle.com/datasets/example/versions/3',
  datePublished: '2024-01-01T07:08:01.69',
  creator: {
    '@type': 'sc:Person',
    name: 'Kashish Parmar',
    url: '/kashishparmar02',
    image: 'https://storage.googleapis.com/kaggle-avatars/default-thumb.png',
  },
  distribution: [{
    '@id': 'archive.zip',
    name: 'archive.zip',
    contentUrl: 'https://www.kaggle.com/api/v1/datasets/download/example',
    encodingFormat: 'application/zip',
    md5: 'sTkxKpM2Ps0MuOBXXXmHFA==',
  }],
}

describe('uploaded Croissant top-level projection', () => {
  it('maps the Social Sentiment properties represented by the current form', () => {
    expect(datasetTopLevelProjectionFromCroissant(socialSentimentMetadata)).toEqual({
      citation: '',
      datePublished: '2024-01-01T07:08:01.69',
      datasetVersion: '3',
      description: longDescription,
      license: 'https://creativecommons.org/publicdomain/zero/1.0/',
      licenseLabel: 'CC0: Public Domain — https://creativecommons.org/publicdomain/zero/1.0/',
      name: 'Social Media Sentiments Analysis Dataset 📊',
      url: 'https://www.kaggle.com/datasets/example/versions/3',
    })
  })

  it('keeps the complete description instead of applying the form display limit', () => {
    const projection = datasetTopLevelProjectionFromCroissant(socialSentimentMetadata)
    expect(projection.description).toHaveLength(longDescription.length)
    expect(projection.description.length).toBeGreaterThan(500)
  })

  it('stores the projection while retaining the authoritative original document', () => {
    const draft = datasetUIStateDraftFromCroissantFile(
      socialSentimentMetadata,
      { ...emptyDataset, mode: 'upload' },
      'social-media.json',
    )

    expect(draft.datasetVersion).toBe('3')
    expect(draft.licenseLabel).toContain('CC0: Public Domain')
    expect(draft.uploadedDocument).toBe(socialSentimentMetadata)
  })

  it('maps supported creator fields while leaving unsupported properties authoritative', () => {
    const draft = datasetUIStateDraftFromCroissantFile(
      socialSentimentMetadata,
      { ...emptyDataset, mode: 'upload' },
      'social-media.json',
    )

    expect(draft.creators).toEqual([{
      affiliation: '',
      creatorType: 'Person',
      email: '',
      id: expect.stringMatching(/^uploaded-creator-/),
      name: 'Kashish Parmar',
      orcid: '',
      uploadedIndex: 0,
      url: '/kashishparmar02',
    }])
    expect((draft.uploadedDocument?.creator as Record<string, unknown>).image).toBe(
      'https://storage.googleapis.com/kaggle-avatars/default-thumb.png',
    )
  })

  it('maps creator arrays and supported organization fields', () => {
    const draft = datasetUIStateDraftFromCroissantFile(
      {
        creator: [
          {
            '@type': 'sc:Person',
            affiliation: ['Institute A', 'Institute B'],
            email: 'person@example.org',
            identifier: ['local-id', 'https://orcid.org/0000-0001-2345-6789'],
            name: 'Example Person',
          },
          {
            '@type': 'sc:Organization',
            name: 'Example Institute',
            url: 'https://example.org',
          },
        ],
      },
      { ...emptyDataset, mode: 'upload' },
    )

    expect(draft.creators).toHaveLength(2)
    expect(draft.creators[0]).toMatchObject({
      affiliation: 'Institute A, Institute B',
      creatorType: 'Person',
      email: 'person@example.org',
      name: 'Example Person',
      orcid: 'https://orcid.org/0000-0001-2345-6789',
      uploadedIndex: 0,
    })
    expect(draft.creators[1]).toMatchObject({
      creatorType: 'Organization',
      name: 'Example Institute',
      uploadedIndex: 1,
      url: 'https://example.org',
    })
  })

  it('maps a simple textual license without manufacturing a label', () => {
    expect(datasetTopLevelProjectionFromCroissant({ license: 'CC-BY-4.0' })).toMatchObject({
      license: 'CC-BY-4.0',
      licenseLabel: 'CC-BY-4.0',
    })
  })

  it('does not flatten unsupported language-tagged objects into editable text', () => {
    const projection = datasetTopLevelProjectionFromCroissant({
      description: { en: 'English description', de: 'Deutsche Beschreibung' },
    })
    expect(projection.description).toBe('')
  })
})
