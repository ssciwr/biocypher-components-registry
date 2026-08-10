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
  { disabled: true, label: '(None)', value: '' },
  repositoryFileLicenseOption,
  { label: 'No license', value: 'No license' },
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
  contentUrl: '',
  creators: [],
  datePublished: '',
  datasetVersion: '',
  description: '',
  encodingFormat: '',
  fields: [],
  filename: '',
  input: '',
  license: '',
  manualFields: [],
  mode: 'generate',
  name: '',
  path: '',
  recordSetName: '',
  sha256: '',
  sourceFileName: '',
  uploadedFileName: '',
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
