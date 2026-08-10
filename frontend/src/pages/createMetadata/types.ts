export type CreatorType = 'Person' | 'Organization'
export type DatasetMode = 'croissant' | 'manual'

export type SelectOption<TValue extends string = string> = Readonly<{
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
  datePublished: string
  datasetVersion: string
  description: string
  input: string
  license: string
  mode: DatasetMode
  name: string
  path: string
  url: string
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
