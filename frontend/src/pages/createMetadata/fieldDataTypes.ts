import type { SelectOption } from './types'

const standardTypes = [
  'sc:Text', 'sc:Integer', 'sc:Float', 'sc:Boolean',
  'sc:Date', 'sc:DateTime', 'sc:Time', 'sc:URL',
  'cr:Int8', 'cr:Int16', 'cr:Int32', 'cr:Int64',
  'cr:UInt8', 'cr:UInt16', 'cr:UInt32', 'cr:UInt64',
  'cr:Float16', 'cr:Float32', 'cr:Float64',
]

export function fieldDataTypeOptions(currentValue: string): ReadonlyArray<SelectOption<string>> {
  const options: SelectOption<string>[] = [
    { disabled: true, label: '(None)', value: '' },
    ...standardTypes.map(value => ({ label: value, value })),
  ]
  if (currentValue && !standardTypes.includes(currentValue)) {
    options.push({ label: currentValue, value: currentValue })
  }
  return options
}

export function dataTypeSelectionValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && value.length === 1 && typeof value[0] === 'string') return value[0]
  return value === undefined ? '' : JSON.stringify(value) ?? ''
}

export function dataTypeForExport(selection: string, original: unknown): unknown {
  // Also recognize the comma-joined display used by drafts saved by older UIs.
  const legacySelection = Array.isArray(original)
    ? original.filter(item => typeof item === 'string').join(', ')
    : undefined
  if (selection === dataTypeSelectionValue(original) || selection === legacySelection) return original
  const value = selection.trim()
  if (!value) return undefined
  return Array.isArray(original) ? [value] : value
}
