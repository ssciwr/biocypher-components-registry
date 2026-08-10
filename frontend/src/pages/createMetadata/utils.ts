import type {
  AdapterCreatorGenerateRequest,
  AdapterEmbeddedDatasetGenerateRequest,
} from '../../api/client'
import type { CreatorDraft, DatasetDraft } from './types'

let draftIdCounter = 0
const jsonIndentSpaces = 2

// For moving between the last/next draft as user continues to edit
export function nextDraftId(prefix: string) {
  draftIdCounter += 1
  return `${prefix}-${draftIdCounter}`
}

// Simple form to avoid overcomplicated regexes etc. We do not verify or link to ORCID etc externally.
export function normaliseOrcid(value: string) {
  return value.replaceAll('-', '').replace('https://orcid.org/', '').slice(0, 16)
}

/*
 * AI-Generated.
 */
export function creatorToApiValue(creator: CreatorDraft): AdapterCreatorGenerateRequest {
  const orcid = optionalValue(creator.orcid)
  const identifier = orcid
    ? `https://orcid.org/${orcid.match(/.{1,4}/g)?.join('-') ?? orcid}`
    : undefined

  return {
    affiliation: optionalValue(creator.affiliation),
    creator_type: creator.creatorType,
    email: optionalValue(creator.email),
    identifier,
    name: creator.name.trim(),
    url: optionalValue(creator.url),
  }
}

export function keywordsToApiValues(value: string) {
  return value
    .split(',')
    .map((keyword) => keyword.trim())
    .filter(Boolean)
}

/*
 * Helper to force empty strings into undefiend, because the API expects that for "empty" values (e.g. form entries the user has not touched)
 */
export function optionalValue(value: string) {
  const trimmed = value.trim()
  return trimmed || undefined
}

/*
Convert UI shape into the API shape, e.g.:
{ mode: 'croissant', path: '/x/croissant.jsonld', ... }

  into the API shape:

  dataset_paths: ['/x/croissant.jsonld']
  } // (UI has 'mode' for flow control.
 */
export function datasetPathsToApiValues(datasets: DatasetDraft[]) {
  return datasets
    .filter((dataset) => dataset.mode === 'croissant')
    .map((dataset) => dataset.path.trim())
}

// Force into API format (undefined for empty paths or real values
export function generatedDatasetsToApiValues(
  datasets: DatasetDraft[],
) {
  return datasets
    .filter((dataset) => dataset.mode === 'manual')
    .map((dataset): AdapterEmbeddedDatasetGenerateRequest => ({
      citation: optionalValue(dataset.citation),
      date_published: optionalValue(dataset.datePublished),
      dataset_version: optionalValue(dataset.datasetVersion),
      description: optionalValue(dataset.description),
      extra_args: [], // provide required param by API (extra_args)
      input: dataset.input.trim(),
      license: optionalValue(dataset.license),
      name: optionalValue(dataset.name),
      url: optionalValue(dataset.url),
    }))
}

export function errorText(error: unknown, fallback: string) {
  if (typeof error === 'string' && error) {
    return error
  }

  const details = error as { detail?: string; details?: string } | undefined
  return details?.details || details?.detail || fallback
}


export function downloadMetadata(metadata: Record<string, unknown>, adapterName: string) {
  const metadataJson = JSON.stringify(metadata, undefined, jsonIndentSpaces)
  const blob = new Blob([metadataJson], {
    type: 'application/ld+json',
  })
  const url = globalThis.URL.createObjectURL(blob)
  const anchor = globalThis.document.createElement('a')
  anchor.href = url
  anchor.download = `${adapterName.trim() || 'adapter'}-croissant.jsonld`
  anchor.click()
  globalThis.URL.revokeObjectURL(url)
}
