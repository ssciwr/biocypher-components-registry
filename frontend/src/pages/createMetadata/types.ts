export type CreatorType = 'Person' | 'Organization'
export type DatasetMode = 'generate' | 'upload'
export type MetadataStep = 1 | 2 | 3 | 4

export type UploadedDatasetEditableField =
  | 'citation'
  | 'creators'
  | 'datePublished'
  | 'datasetVersion'
  | 'description'
  | 'distributions'
  | 'fields'
  | 'license'
  | 'name'
  | 'url'

export type SelectOption<TValue extends string = string> = Readonly<{
  disabled?: boolean
  label: string
  value: TValue
}>

export type CreatorDraft = {
  id: string
  affiliation: string
  creatorType: CreatorType
  email: string
  name: string
  orcid: string
  uploadedIndex?: number
  url: string
}

export type DatasetDraft = {
  id: string
  citation: string
  contentUrl: string
  creators: CreatorDraft[]
  datePublished: string
  datasetVersion: string
  description: string
  distributions: DatasetDistributionDraft[]
  encodingFormat: string
  fields: DatasetDatasetManualField[]
  filename: string
  input: string
  license: string
  licenseLabel: string
  manualFields: DatasetDatasetManualField[]
  mode: DatasetMode
  name: string
  path: string
  recordSetName: string
  recordSets: DatasetRecordSetDraft[]
  sha256: string
  sourceSelection?: DatasetSourceSelection
  sourceFileName: string
  uploadedDocument?: Record<string, unknown>
  uploadedDirtyFields: UploadedDatasetEditableField[]
  uploadedFileName: string
  url: string
}

export type DatasetRecordSetDraft = {
  fields: DatasetDatasetManualField[]
  id: string
  name: string
  sourceFileLabel: string
  uploadedIndex: number
}

export type DatasetDistributionDraft = {
  containedInLabel: string
  contentUrl: string
  encodingFormat: string
  filename: string
  id: string
  md5: string
  sha256: string
  uploadedIndex: number
}

export type DatasetSourceSelection = {
  entries: DatasetSourceEntry[]
  kind: 'file' | 'folder'
  name: string
}

export type DatasetSourceEntry = {
  file: File
  relativePath: string
}

export type DatasetDatasetManualField = {
  id: string
  dataType: string
  description: string
  example: string
  fieldId: string
  name: string
  source?: unknown
  uploadedIndex?: number
}

export type MetadataGeneratorForm = {
  adapterId: string
  codeRepository: string
  creators: CreatorDraft[]
  datasets: DatasetDraft[]
  description: string
  keywords: string
  license: string
  name: string
  version: string
}
