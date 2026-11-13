import type {
  CreatorDraft,
  DatasetDraft,
  MetadataGeneratorForm,
  SelectOption,
} from './types'
import {
  backendCanonicalLicenseOptions,
  repositoryFileLicenseOption,
} from './canonicalLicenses'

export const licenseOptions: SelectOption[] = [
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
  distributions: [],
  encodingFormat: '',
  fields: [],
  filename: '',
  input: '',
  license: '',
  licenseLabel: '',
  manualFields: [],
  mode: 'generate',
  name: '',
  path: '',
  recordSetName: '',
  recordSets: [],
  sha256: '',
  sourceFileName: '',
  uploadedFileName: '',
  uploadedDirtyFields: [],
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
