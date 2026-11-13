import type {
  AdapterCreatorGenerateRequest,
} from '../../api/client'
import type { CreatorDraft, DatasetDraft, DatasetDatasetManualField, DatasetRecordSetDraft } from './types'
import type { CroissantDocumentEdit } from './uploadedDocumentEditing'
import { applyCroissantDocumentEdits } from './uploadedDocumentEditing'

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


function dateAtUtcMidnight(value: string) {
  const dateMatch = /^\d{4}-\d{2}-\d{2}/.exec(value.trim())
  if (!dateMatch) {
    return undefined
  }
  return `${dateMatch[0]}T00:00:00Z`
}


/*
 * Build multi part form body data for API
 */
export function datasetDraftToDocument(dataset: DatasetDraft): Record<string, unknown> {
  if (dataset.mode === 'upload' && isRecord(dataset.uploadedDocument)) {
    return uploadedDatasetDraftToDocument(dataset, dataset.uploadedDocument)
  }

  const document: Record<string, unknown> = isRecord(dataset.uploadedDocument)
    ? { ...dataset.uploadedDocument }
    : { '@type': 'sc:Dataset' }
  setOptional(document, 'name', dataset.name) // setOtpional is just a pattern so empty values are allowed but sent as backend expects.
  setOptional(document, 'description', dataset.description)
  setOptional(document, 'version', dataset.datasetVersion)
  setOptional(document, 'license', dataset.license)
  setOptional(document, 'url', dataset.url)
  setOptional(document, 'citeAs', dataset.citation)
  setOptional(document, 'datePublished', dateAtUtcMidnight(dataset.datePublished))
  const creators = dataset.creators
    .filter((creator) => creator.name.trim())
    .map(creatorToCroissantValue)
  if (creators.length) {
    document.creator = creators
  }

  const existingDistributions = recordList(document.distribution)
  const distribution = buildDistribution(dataset, existingDistributions[0])
  if (distribution) {
    document.distribution = [distribution, ...existingDistributions.slice(1)]
  }

  const fields = [...dataset.fields, ...dataset.manualFields]
    .filter((field) => field.name.trim())
    .map((field) => datasetManualFieldToCroissantField(field, dataset))
  if (fields.length) {
    const existingRecordSets = recordList(document.recordSet)
    const existingRecordSet = existingRecordSets[0] ?? {}
    const recordSetName = dataset.recordSetName.trim() || `${dataset.name || 'Dataset'} records`
    document.recordSet = [
      {
        ...existingRecordSet,
        '@type': existingRecordSet['@type'] ?? 'cr:RecordSet',
        '@id': existingRecordSet['@id'] ?? localId(recordSetName),
        field: fields,
        name: recordSetName,
      },
      ...existingRecordSets.slice(1),
    ]
  }

  return document
}

function uploadedDatasetDraftToDocument(
  dataset: DatasetDraft,
  original: Record<string, unknown>,
): Record<string, unknown> {
  const dirty = new Set(dataset.uploadedDirtyFields)
  const edits: CroissantDocumentEdit[] = []
  const addTextEdit = (field: string, value: string) => {
    if (value.trim()) edits.push({ path: [field], value: value.trim() })
    else if (Object.hasOwn(original, field)) edits.push({ operation: 'remove', path: [field] })
  }

  if (dirty.has('name')) addTextEdit('name', dataset.name)
  if (dirty.has('description')) addTextEdit('description', dataset.description)
  if (dirty.has('url')) addTextEdit('url', dataset.url)
  if (dirty.has('citation')) addTextEdit('citeAs', dataset.citation)
  if (dirty.has('datePublished')) addTextEdit('datePublished', dataset.datePublished.slice(0, 10))
  if (dirty.has('license')) addTextEdit('license', dataset.license)
  if (dirty.has('datasetVersion')) addVersionEdit(edits, dataset.datasetVersion, original)
  if (dirty.has('creators')) addCreatorsEdit(edits, dataset.creators, original)
  if (dirty.has('fields')) {
    edits.push({
      path: ['recordSet'],
      value: mergeUploadedRecordSets(dataset, original.recordSet),
    })
  }
  if (dirty.has('distributions')) {
    edits.push({
      path: ['distribution'],
      value: mergeUploadedDistributions(dataset, original.distribution),
    })
  }

  return applyCroissantDocumentEdits(original, edits)
}

function addVersionEdit(
  edits: CroissantDocumentEdit[],
  datasetVersion: string,
  original: Record<string, unknown>,
) {
  const editedVersion = datasetVersion.trim()
  if (!editedVersion && Object.hasOwn(original, 'version')) {
    edits.push({ operation: 'remove', path: ['version'] })
    return
  }
  if (!editedVersion) return

  const numericVersion = Number(editedVersion)
  edits.push({
    path: ['version'],
    value: typeof original.version === 'number' && Number.isFinite(numericVersion)
      ? numericVersion
      : editedVersion,
  })
}

function addCreatorsEdit(
  edits: CroissantDocumentEdit[],
  creators: CreatorDraft[],
  original: Record<string, unknown>,
) {
  const mergedCreators = mergeUploadedCreators(creators, original.creator)
  if (mergedCreators === undefined && Object.hasOwn(original, 'creator')) {
    edits.push({ operation: 'remove', path: ['creator'] })
  } else if (mergedCreators !== undefined) {
    edits.push({ path: ['creator'], value: mergedCreators })
  }
}

function mergeUploadedDistributions(dataset: DatasetDraft, originalValue: unknown): unknown {
  const originals = Array.isArray(originalValue) ? originalValue : [originalValue]
  const distributions = dataset.distributions.map((distribution) => {
    const original = originals[distribution.uploadedIndex]
    if (!isRecord(original)) return {
      '@type': 'cr:FileObject',
      contentUrl: distribution.contentUrl,
      encodingFormat: distribution.encodingFormat,
      md5: distribution.md5,
      name: distribution.filename,
      sha256: distribution.sha256,
    }
    const document = { ...original }
    applyDistributionTextEdit(document, 'contentUrl', distribution.contentUrl, textValue(original.contentUrl))
    applyDistributionTextEdit(document, 'encodingFormat', distribution.encodingFormat, displayTextValue(original.encodingFormat))
    applyDistributionTextEdit(document, 'name', distribution.filename, textValue(original.name))
    applyDistributionTextEdit(document, 'md5', distribution.md5, textValue(original.md5))
    applyDistributionTextEdit(document, 'sha256', distribution.sha256, textValue(original.sha256))
    return document
  })
  return !Array.isArray(originalValue) && distributions.length === 1
    ? distributions[0]
    : distributions
}

function applyDistributionTextEdit(
  document: Record<string, unknown>,
  property: string,
  editedValue: string,
  originalValue: string,
) {
  if (editedValue === originalValue) return
  if (editedValue.trim()) document[property] = editedValue.trim()
  else delete document[property]
}

function mergeUploadedRecordSets(dataset: DatasetDraft, originalValue: unknown): unknown {
  const originals = Array.isArray(originalValue) ? originalValue : [originalValue]
  const recordSets = dataset.recordSets.map((recordSet) => mergeUploadedRecordSet(
    dataset,
    recordSet,
    isRecord(originals[recordSet.uploadedIndex]) ? originals[recordSet.uploadedIndex] : undefined,
  ))
  return !Array.isArray(originalValue) && recordSets.length === 1 ? recordSets[0] : recordSets
}

function mergeUploadedRecordSet(
  dataset: DatasetDraft,
  draft: DatasetRecordSetDraft,
  originalRecordSet?: Record<string, unknown>,
): Record<string, unknown> {
  const recordSet = { ...(originalRecordSet ?? { '@type': 'cr:RecordSet' }) }
  const originalFieldsValue = originalRecordSet?.field
  const originalFields = Array.isArray(originalFieldsValue)
    ? originalFieldsValue
    : [originalFieldsValue]
  const fields = draft.fields.map((field) => {
    const originalField = field.uploadedIndex === undefined
      ? undefined
      : originalFields[field.uploadedIndex]
    if (!isRecord(originalField)) return datasetManualFieldToCroissantField(
      field,
      { ...dataset, recordSetName: draft.name },
    )
    return mergeUploadedField(field, originalField)
  })

  if (draft.name !== textValue(originalRecordSet?.name)) {
    if (draft.name.trim()) recordSet.name = draft.name.trim()
    else delete recordSet.name
  }
  recordSet.field = !Array.isArray(originalFieldsValue) && fields.length === 1 ? fields[0] : fields
  return recordSet
}

function mergeUploadedField(
  field: DatasetDatasetManualField,
  original: Record<string, unknown>,
): Record<string, unknown> {
  const document = { ...original }
  const originalName = textValue(original.name)
  mergeUploadedFieldName(document, field.name, originalName, original.source)
  mergeUploadedFieldValue(document, 'dataType', field.dataType, displayTextValue(original.dataType), true)
  mergeUploadedFieldValue(document, 'description', field.description, textValue(original.description))
  mergeUploadedFieldValue(document, 'examples', field.example, exampleText(original.examples), true)
  return document
}

function mergeUploadedFieldName(
  document: Record<string, unknown>,
  editedName: string,
  originalName: string,
  originalSource: unknown,
) {
  if (editedName === originalName) return
  const trimmedName = editedName.trim()
  if (trimmedName) document.name = trimmedName
  else delete document.name

  const updatedSource = sourceWithRenamedColumn(originalSource, originalName, trimmedName)
  if (updatedSource !== undefined) document.source = updatedSource
}

function mergeUploadedFieldValue(
  document: Record<string, unknown>,
  property: string,
  editedValue: string,
  originalValue: string,
  asList = false,
) {
  if (editedValue === originalValue) return
  const trimmedValue = editedValue.trim()
  if (trimmedValue) document[property] = asList ? [trimmedValue] : trimmedValue
  else delete document[property]
}

function sourceWithRenamedColumn(source: unknown, originalName: string, editedName: string) {
  if (!isRecord(source) || !isRecord(source.extract)) return source
  const originalColumn = textValue(source.extract.column)
  if (originalColumn !== originalName && originalColumn !== '') return source
  return {
    ...source,
    extract: {
      ...source.extract,
      column: editedName,
    },
  }
}

function mergeUploadedCreators(creators: CreatorDraft[], originalValue: unknown): unknown {
  const originals = Array.isArray(originalValue) ? originalValue : [originalValue]
  const merged = creators
    .filter((creator) => creator.name.trim())
    .map((creator) => {
      const original = creator.uploadedIndex === undefined
        ? undefined
        : originals[creator.uploadedIndex]
      if (!isRecord(original)) return creatorToCroissantValue(creator)

      const document = { ...original }
      const originalType = textValue(original['@type']).endsWith('Organization')
        ? 'Organization'
        : 'Person'
      if (creator.creatorType !== originalType) {
        document['@type'] = `sc:${creator.creatorType}`
      }
      if (creator.name !== textValue(original.name)) document.name = creator.name.trim()
      applyCreatorTextEdit(document, 'affiliation', creator.affiliation, compatibleTextValue(original.affiliation))
      applyCreatorTextEdit(document, 'email', creator.email, textValue(original.email))
      applyCreatorTextEdit(document, 'identifier', creator.orcid, compatibleIdentifierValue(original.identifier))
      applyCreatorTextEdit(document, 'url', creator.url, textValue(original.url))
      return document
    })
  if (!merged.length) return undefined
  return !Array.isArray(originalValue) && merged.length === 1 ? merged[0] : merged
}

function applyCreatorTextEdit(
  document: Record<string, unknown>,
  property: string,
  editedValue: string,
  projectedOriginalValue: string,
) {
  if (editedValue === projectedOriginalValue) return
  if (editedValue.trim()) document[property] = editedValue.trim()
  else delete document[property]
}

// Convert uploaded or generated Croissant dataset JSON into the editable frontend DatasetDraft shape, more on this soon.
export function datasetUIStateDraftFromCroissantFile(
  document: Record<string, unknown>,
  dataset: DatasetDraft,
  uploadedFileName = '',
): DatasetDraft {
  const topLevel = datasetTopLevelProjectionFromCroissant(document)
  const uploadedCreators = creatorsProjectionFromCroissant(document.creator)
  const distribution = firstRecord(document.distribution)
  const recordSet = firstRecord(document.recordSet)
  const distributions = distributionsFromCroissant(document.distribution)
  const recordSets = recordSetsFromCroissant(document.recordSet)
  const isUploaded = dataset.mode === 'upload'

  return {
    ...dataset,
    citation: isUploaded ? topLevel.citation : topLevel.citation || dataset.citation,
    contentUrl: isUploaded
      ? textValue(distribution?.contentUrl)
      : dataset.contentUrl || textValue(distribution?.contentUrl),
    creators: isUploaded ? uploadedCreators : dataset.creators,
    datePublished: isUploaded ? topLevel.datePublished : topLevel.datePublished || dataset.datePublished,
    datasetVersion: isUploaded ? topLevel.datasetVersion : topLevel.datasetVersion || dataset.datasetVersion,
    description: isUploaded ? topLevel.description : topLevel.description || dataset.description,
    distributions,
    encodingFormat: isUploaded
      ? displayTextValue(distribution?.encodingFormat)
      : displayTextValue(distribution?.encodingFormat) || dataset.encodingFormat,
    fields: fieldsFromRecordSet(recordSet),
    filename: isUploaded
      ? textValue(distribution?.name) || uploadedFileName
      : textValue(distribution?.name) || uploadedFileName || dataset.filename,
    license: isUploaded
      ? topLevel.license
      : dataset.license || topLevel.license,
    licenseLabel: isUploaded
      ? topLevel.licenseLabel
      : dataset.licenseLabel || topLevel.licenseLabel,
    manualFields: isUploaded ? [] : dataset.manualFields,
    name: isUploaded
      ? topLevel.name || uploadedFileName
      : topLevel.name || uploadedFileName || dataset.name,
    recordSetName: isUploaded
      ? textValue(recordSet?.name)
      : textValue(recordSet?.name) || dataset.recordSetName,
    recordSets,
    sha256: isUploaded ? textValue(distribution?.sha256) : textValue(distribution?.sha256) || dataset.sha256,
    uploadedDocument: document,
    uploadedDirtyFields: [],
    uploadedFileName,
    url: isUploaded ? topLevel.url : topLevel.url || dataset.url,
  }
}

function recordSetsFromCroissant(value: unknown): DatasetRecordSetDraft[] {
  return recordList(value).map((recordSet, uploadedIndex) => ({
    fields: fieldsFromRecordSet(recordSet),
    id: textValue(recordSet['@id']),
    name: textValue(recordSet.name),
    sourceFileLabel: recordSetSourceFileLabel(recordSet),
    uploadedIndex,
  }))
}

function recordSetSourceFileLabel(recordSet: Record<string, unknown>) {
  const fields = Array.isArray(recordSet.field) ? recordSet.field : [recordSet.field]
  for (const field of fields) {
    if (!isRecord(field) || !isRecord(field.source)) continue
    for (const property of ['fileObject', 'fileSet']) {
      const reference = field.source[property]
      if (isRecord(reference)) {
        const label = textValue(reference['@id']) || textValue(reference.name)
        if (label) return label
      }
    }
  }
  return ''
}

function distributionsFromCroissant(value: unknown) {
  return recordList(value).map((distribution, uploadedIndex) => ({
    containedInLabel: containedInLabel(distribution.containedIn),
    contentUrl: textValue(distribution.contentUrl),
    encodingFormat: displayTextValue(distribution.encodingFormat),
    filename: textValue(distribution.name),
    id: textValue(distribution['@id']),
    md5: textValue(distribution.md5),
    sha256: textValue(distribution.sha256),
    uploadedIndex,
  }))
}

function containedInLabel(value: unknown) {
  if (isRecord(value)) return textValue(value['@id']) || textValue(value.name)
  if (Array.isArray(value)) {
    return value.flatMap((item) => isRecord(item)
      ? [textValue(item['@id']) || textValue(item.name)]
      : []).filter(Boolean).join(', ')
  }
  return textValue(value)
}

/** Map only creator properties represented by the existing creator form. */
export function creatorsProjectionFromCroissant(value: unknown): CreatorDraft[] {
  const creators = Array.isArray(value) ? value : [value]
  return creators.flatMap((creator, uploadedIndex) => {
    if (!isRecord(creator)) return []
    const name = textValue(creator.name)
    const type = textValue(creator['@type'])
    return [{
      id: nextDraftId('uploaded-creator'),
      affiliation: compatibleTextValue(creator.affiliation),
      creatorType: type.endsWith('Organization') ? 'Organization' : 'Person',
      email: textValue(creator.email),
      name,
      orcid: compatibleIdentifierValue(creator.identifier),
      uploadedIndex,
      url: textValue(creator.url),
    }]
  })
}

export type DatasetTopLevelProjection = Readonly<{
  citation: string
  datePublished: string
  datasetVersion: string
  description: string
  license: string
  licenseLabel: string
  name: string
  url: string
}>

/** Project only top-level Croissant properties represented by the current form. */
export function datasetTopLevelProjectionFromCroissant(
  document: Record<string, unknown>,
): DatasetTopLevelProjection {
  const license = licenseProjection(document.license)
  return {
    citation: textValue(document.citeAs),
    datePublished: textValue(document.datePublished),
    datasetVersion: scalarDisplayValue(document.version),
    description: textValue(document.description),
    license: license.value,
    licenseLabel: license.label,
    name: textValue(document.name),
    url: textValue(document.url),
  }
}

function licenseProjection(value: unknown): { label: string; value: string } {
  if (typeof value === 'string') return { label: value, value }
  if (!isRecord(value)) return { label: '', value: '' }

  const name = textValue(value.name)
  const url = textValue(value.url)
  return {
    label: name && url ? `${name} — ${url}` : name || url,
    value: url || name,
  }
}

function scalarDisplayValue(value: unknown) {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

function compatibleTextValue(value: unknown) {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && value.every(item => typeof item === 'string')) {
    return value.join(', ')
  }
  return ''
}

function compatibleIdentifierValue(value: unknown) {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value.find((item): item is string => (
      typeof item === 'string' && item.includes('orcid.org/')
    )) ?? ''
  }
  return ''
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
    ...existing,
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
  return fields.map((field, uploadedIndex) => ({
    id: nextDraftId('field'),
    dataType: displayTextValue(field.dataType),
    description: textValue(field.description),
    example: exampleText(field.examples),
    fieldId: textValue(field['@id']),
    name: textValue(field.name),
    source: field.source,
    uploadedIndex,
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

function recordList(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) {
    return value.filter(isRecord)
  }
  return isRecord(value) ? [value] : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function displayTextValue(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string').join(', ')
  }
  return ''
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
