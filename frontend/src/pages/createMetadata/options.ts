import type {
  CreatorDraft,
  DatasetDraft,
  LicenseOption,
  MetadataGeneratorForm,
} from './types'
import {
  backendCanonicalLicenseOptions,
  repositoryFileLicenseOption,
} from './canonicalLicenses'

export const licenseOptions: LicenseOption[] = [
  { label: 'Example: MIT', value: '' },
  repositoryFileLicenseOption,
  ...backendCanonicalLicenseOptions,
]

export const emptyCreator: CreatorDraft = {
  id: 'new-creator',
  affiliation: '',
  creatorType: 'Person',
  email: '',
  name: '',
  orcid: '',
  url: '',
}

export const emptyDataset: DatasetDraft = {
  id: 'new-dataset',
  citation: '',
  datePublished: '',
  datasetVersion: '',
  description: '',
  input: '',
  license: '',
  mode: 'croissant',
  name: '',
  path: '',
  url: '',
}

export const emptyForm: MetadataGeneratorForm = {
  adapterId: '',
  codeRepository: '',
  creators: [],
  datasets: [],
  description: '',
  keywords: '',
  license: '',
  name: '',
  version: '',
}
