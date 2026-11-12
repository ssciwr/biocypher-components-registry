type DatasetProperties = Record<string, unknown>

export type DatasetColumn = Readonly<{
  name: string
  dataType: string
  examples: string
  description: string
}>

function datasetPropertyObjects(datasetProperty: unknown): DatasetProperties[] {
  const propertyEntries: unknown[] = Array.isArray(datasetProperty) ? datasetProperty : [datasetProperty]
  return propertyEntries.filter((property): property is DatasetProperties => (
    property !== null && typeof property === 'object' && !Array.isArray(property)
  ))
}

function columnExampleText(example: unknown): string {
  if (example === null || example === undefined) return ''
  return typeof example === 'string' ? example : JSON.stringify(example) ?? ''
}

function columnDataTypeText(dataType: unknown): string {
  if (Array.isArray(dataType)) return dataType.map(columnDataTypeText).filter(Boolean).join(', ')
  if (typeof dataType === 'string') return dataType
  const typeIdentifier = datasetPropertyObjects(dataType)[0]?.['@id']
  return typeof typeIdentifier === 'string' ? typeIdentifier : ''
}

export function readDatasetColumns(adapterDocument: DatasetProperties, datasetName: string): DatasetColumn[] {
  const dataset = datasetPropertyObjects(adapterDocument.hasPart).find((source) => (
    typeof source.name === 'string' && source.name.trim() === datasetName
  ))
  return datasetPropertyObjects(dataset?.recordSet).flatMap((recordSet) => (
    datasetPropertyObjects(recordSet.field).flatMap((columnField) => {
      if (typeof columnField.name !== 'string' || !columnField.name.trim()) return []
      const examples: unknown[] = Array.isArray(columnField.examples) ? columnField.examples : [columnField.examples]
      return [{
        name: columnField.name,
        dataType: columnDataTypeText(columnField.dataType),
        examples: examples.map(columnExampleText).filter(Boolean).join('\n'),
        description: typeof columnField.description === 'string' ? columnField.description : '',
      }]
    })
  ))
}
