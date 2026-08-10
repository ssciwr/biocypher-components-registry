export type CreatorType = 'Person' | 'Organization'
export type DatasetMode = 'generate' | 'upload'
export type MetadataStep = 1 | 2 | 3 | 4

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
  encodingFormat: string
  fields: DatasetDatasetManualField[]
  filename: string
  input: string
  license: string
  manualFields: DatasetDatasetManualField[]
  mode: DatasetMode
  name: string
  path: string
  recordSetName: string
  sha256: string
  sourceFile?: File
  sourceFileName: string
  uploadedDocument?: Record<string, unknown>
  uploadedFileName: string
  url: string
}

export type DatasetDatasetManualField = {
  id: string
  dataType: string
  description: string
  example: string
  fieldId: string
  name: string
  source?: unknown
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

export type LicenseOption = SelectOption
