import type { SelectOption } from './types'

export const repositoryFileLicenseOption: SelectOption = {
  label: 'In repository as file/Custom',
  value: 'In repository as file/Custom',
}

export const backendCanonicalLicenseOptions: SelectOption[] = [
  { label: 'Creative Commons Attribution 4.0', value: 'CC-BY-4.0' },
  { label: 'Creative Commons Attribution-ShareAlike 4.0', value: 'CC-BY-SA-4.0' },
  { label: 'Creative Commons Attribution-NonCommercial 4.0', value: 'CC-BY-NC-4.0' },
  { label: 'Creative Commons Attribution-NoDerivatives 4.0', value: 'CC-BY-ND-4.0' },
  { label: 'Creative Commons Zero v1.0 Universal', value: 'CC0-1.0' },
  { label: 'MIT License', value: 'MIT' },
  { label: 'Apache License 2.0', value: 'Apache-2.0' },
  { label: 'GNU General Public License v3.0', value: 'GPL-3.0' },
  { label: 'BSD 3-Clause License', value: 'BSD-3-Clause' },
]
