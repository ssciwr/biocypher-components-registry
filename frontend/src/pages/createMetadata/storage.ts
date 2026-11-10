export const metadataDraftStorageKey = 'biocypher-adapter-metadata-draft'

const metadataDraftTextFields = [
  'adapterId',
  'codeRepository',
  'description',
  'keywords',
  'license',
  'name',
  'version',
] as const

export function hasMeaningfulMetadataDraft(draft: unknown): boolean {
  if (typeof draft !== 'object' || draft === null || Array.isArray(draft)) {
    return false
  }

  const record = draft as Record<string, unknown>
  const hasTextValue = metadataDraftTextFields.some((field) => {
    const value = record[field]
    return typeof value === 'string' && Boolean(value.trim())
  })
  return hasTextValue
    || (Array.isArray(record.creators) && record.creators.length > 0)
    || (Array.isArray(record.datasets) && record.datasets.length > 0)
}
