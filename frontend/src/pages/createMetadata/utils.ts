import type {
  AdapterCreatorGenerateRequest,
  BodyGenerateDatasetMetadataApiV1MetadataDatasetsGeneratePost,
} from '../../api/client'
import type { CreatorDraft, DatasetDraft, DatasetDatasetManualField } from './types'

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
 * AI-Generated. Manually modified to work for both dataset creators and adapter creators as a unified JSON type
 * (rather than an array of '|' joined strings)
 */
export function creatorToApiValue(creator: CreatorDraft): AdapterCreatorGenerateRequest {
  const orcid = optionalValue(creator.orcid)

  return {
    affiliation: optionalValue(creator.affiliation),
    creator_type: creator.creatorType,
    email: optionalValue(creator.email),
    identifier: orcid,
    name: creator.name.trim(),
    url: optionalValue(creator.url),
  }
}

// Save creatro correction
function creatorToCroissantValue(creator: CreatorDraft): Record<string, unknown> {
  const creatorType = creator.creatorType === 'Organization' ? 'Organization' : 'Person'
  const document: Record<string, unknown> = {
    '@type': `sc:${creatorType}`,
    name: creator.name.trim(),
  }
  setOptional(document, 'affiliation', creator.affiliation)
  setOptional(document, 'email', creator.email)
  setOptional(document, 'identifier', creator.orcid)
  setOptional(document, 'url', creator.url)
  return document
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
 * Build multi part form body data for API
 */
export function datasetDraftToCroissantGenerateUploadForm(
  dataset: DatasetDraft,
): BodyGenerateDatasetMetadataApiV1MetadataDatasetsGeneratePost {
  if (!dataset.sourceFile) {
    throw new Error('Upload a source dataset file first.')
  }

  return {
    citation: optionalValue(dataset.citation),
    creators_json: JSON.stringify(dataset.creators.map(creatorToApiValue)),
    content_url: optionalValue(dataset.contentUrl),
    date_published: optionalValue(dataset.datePublished),
    dataset_version: optionalValue(dataset.datasetVersion),
    description: optionalValue(dataset.description),
    encoding_format: optionalValue(dataset.encodingFormat),
    file: dataset.sourceFile,
    filename: optionalValue(dataset.filename),
    generator: 'auto',
    license: optionalValue(dataset.license),
    name: optionalValue(dataset.name),
    sha256: optionalValue(dataset.sha256),
    url: optionalValue(dataset.url),
  }
}

export function datasetDraftToDocument(dataset: DatasetDraft): Record<string, unknown> {
  const document: Record<string, unknown> = isRecord(dataset.uploadedDocument)
    ? { ...dataset.uploadedDocument }
    : { '@type': 'sc:Dataset' }
  setOptional(document, 'name', dataset.name) // setOtpional is just a pattern so empty values are allowed but sent as backend expects.
  setOptional(document, 'description', dataset.description)
  setOptional(document, 'version', dataset.datasetVersion)
  setOptional(document, 'license', dataset.license)
  setOptional(document, 'url', dataset.url)
  setOptional(document, 'citeAs', dataset.citation)
  setOptional(document, 'datePublished', dataset.datePublished)
  const creators = dataset.creators
    .filter((creator) => creator.name.trim())
    .map(creatorToCroissantValue)
  if (creators.length) {
    document.creator = creators
  }

  const distribution = buildDistribution(dataset, firstRecord(document.distribution))
  if (distribution) {
    document.distribution = [distribution]
  }

  const fields = [...dataset.fields, ...dataset.manualFields]
    .filter((field) => field.name.trim())
    .map((field) => datasetManualFieldToCroissantField(field, dataset))
  if (fields.length) {
    const existingRecordSet = firstRecord(document.recordSet) ?? {}
    const recordSetName = dataset.recordSetName.trim() || `${dataset.name || 'Dataset'} records`
    document.recordSet = [
      {
        ...existingRecordSet,
        '@type': existingRecordSet['@type'] ?? 'cr:RecordSet',
        '@id': existingRecordSet['@id'] ?? localId(recordSetName),
        field: fields,
        name: recordSetName,
      },
    ]
  }

  return document
}

// Convert uploaded or generated Croissant dataset JSON into the editable frontend DatasetDraft shape, more on this soon.
export function datasetUIStateDraftFromCroissantFile(
  document: Record<string, unknown>,
  dataset: DatasetDraft,
  uploadedFileName = '',
): DatasetDraft {
  const distribution = firstRecord(document.distribution)
  const recordSet = firstRecord(document.recordSet)

  return {
    ...dataset,
    citation: textValue(document.citeAs) || dataset.citation,
    contentUrl: textValue(distribution?.contentUrl) || dataset.contentUrl,
    datePublished: textValue(document.datePublished) || dataset.datePublished,
    datasetVersion: textValue(document.version) || dataset.datasetVersion,
    description: textValue(document.description) || dataset.description,
    encodingFormat: textValue(distribution?.encodingFormat) || dataset.encodingFormat,
    fields: fieldsFromRecordSet(recordSet),
    filename: textValue(distribution?.name) || uploadedFileName || dataset.filename,
    license: textValue(document.license) || dataset.license,
    name: textValue(document.name) || uploadedFileName || dataset.name,
    recordSetName: textValue(recordSet?.name) || dataset.recordSetName,
    sha256: textValue(distribution?.sha256) || dataset.sha256,
    uploadedDocument: document,
    uploadedFileName,
    url: textValue(document.url) || dataset.url,
  }
}

// default
export function emptyDatasetManualField(): DatasetDatasetManualField {
  return {
    id: nextDraftId('field'),
    dataType: '',
    description: '',
    example: '',
    fieldId: '',
    name: '',
  }
}

// Collect code execution and API errors together
export function errorText(error: unknown, fallback: string) {
  if (typeof error === 'string' && error) {
    return error
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  const details = error as { detail?: unknown; details?: unknown } | undefined
  const detail = details?.details ?? details?.detail
  if (typeof detail === 'string' && detail) {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (typeof item === 'object' && item !== null && 'msg' in item) {
          return String(item.msg)
        }
        return ''
      })
      .filter(Boolean)
    if (messages.some((message) => message.includes('valid dictionary'))) {
      return 'The backend is still using the old JSON dataset route. Restart the backend so it accepts dataset file uploads.'
    }
    return messages.join(' ') || fallback
  }
  if (typeof detail === 'object' && detail !== null) {
    return JSON.stringify(detail)
  }
  return fallback
}


export function downloadMetadata(metadata: Record<string, unknown>) {
  const metadataJson = JSON.stringify(metadata, undefined, jsonIndentSpaces)
  const blob = new Blob([metadataJson], {
    type: 'application/ld+json',
  })
  const url = globalThis.URL.createObjectURL(blob)
  const anchor = globalThis.document.createElement('a')
  anchor.href = url
  anchor.download = 'croissant.jsonld'
  anchor.click()
  globalThis.URL.revokeObjectURL(url)
}

function buildDistribution(dataset: DatasetDraft, existing?: Record<string, unknown>) {
  const contentUrl = dataset.contentUrl.trim()
  const name = dataset.filename.trim() || contentUrl
  const encodingFormat = dataset.encodingFormat.trim()
  const sha256 = dataset.sha256.trim()
  if (!contentUrl && !name && !encodingFormat && !sha256) {
    return undefined
  }

  const distribution = {
    ...(existing ?? {}),
    '@type': existing?.['@type'] ?? 'cr:FileObject',
  }
  setOptional(distribution, '@id', textValue(existing?.['@id']) || name)
  setOptional(distribution, 'contentUrl', contentUrl)
  setOptional(distribution, 'name', name)
  setOptional(distribution, 'encodingFormat', encodingFormat)
  setOptional(distribution, 'sha256', sha256)
  return distribution
}

function datasetManualFieldToCroissantField(
  field: DatasetDatasetManualField,
  dataset: DatasetDraft,
): Record<string, unknown> {
  const fieldDocument: Record<string, unknown> = {
    '@type': 'cr:Field',
    name: field.name.trim(),
  }
  setOptional(fieldDocument, '@id', field.fieldId || `${localId(dataset.recordSetName || dataset.name)}/${field.name.trim()}`)
  setOptional(fieldDocument, 'dataType', field.dataType)
  setOptional(fieldDocument, 'description', field.description)
  if (field.example.trim()) {
    fieldDocument.examples = [field.example.trim()]
  }
  if (field.source !== undefined) {
    fieldDocument.source = field.source
  } else {
    const fileObjectId = datasetFileObjectId(dataset)
    if (!fileObjectId) {
      return fieldDocument
    }
    fieldDocument.source = {
      extract: { column: field.name.trim() },
      fileObject: { '@id': fileObjectId },
    }
  }
  return fieldDocument
}

function datasetFileObjectId(dataset: DatasetDraft) {
  // to get a source field which croissant requires.
  const distribution = firstRecord(dataset.uploadedDocument?.distribution)
  return textValue(distribution?.['@id']) || dataset.filename.trim()
}

function fieldsFromRecordSet(recordSet?: Record<string, unknown>) {
  const rawFields = recordSet?.field
  let fields: Record<string, unknown>[] = []
  if (Array.isArray(rawFields)) {
    fields = rawFields.filter(isRecord)
  } else if (isRecord(rawFields)) {
    fields = [rawFields]
  }

  // Keep Croissant IDs/source mappings so edit -> export does not drop links we do not edit in the UI.
  return fields.map((field) => ({
    id: nextDraftId('field'),
    dataType: textValue(field.dataType),
    description: textValue(field.description),
    example: exampleText(field.examples),
    fieldId: textValue(field['@id']),
    name: textValue(field.name),
    source: field.source,
  }))
}

function firstRecord(value: unknown): Record<string, unknown> | undefined {
  if (Array.isArray(value)) {
    return value.find(isRecord)
  }
  if (isRecord(value)) {
    return value
  }
  return undefined
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

// manage params which are empty values, convert them into a format the API eventually wants.
function setOptional(
  document: Record<string, unknown>,
  key: string,
  value: string | undefined,
) {
  const trimmed = value?.trim() ?? ''
  if (trimmed) {
    document[key] = trimmed
  }
}

function exampleText(value: unknown) {
  const example = Array.isArray(value) ? value[0] : value
  if (example === undefined || example === null) {
    return ''
  }
  if (typeof example === 'string') {
    return example
  }
  return JSON.stringify(example) ?? String(example)
}

function localId(value: string) {
  const trimmed = value.trim().toLowerCase()
  return trimmed ? trimmed.replaceAll(' ', '-') : 'records'
}
