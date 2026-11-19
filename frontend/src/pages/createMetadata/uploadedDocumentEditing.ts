export type CroissantDocumentPath = ReadonlyArray<string | number>

export type CroissantDocumentEdit = Readonly<{
  operation?: 'set'
  path: CroissantDocumentPath
  value: unknown
}> | Readonly<{
  operation: 'remove'
  path: CroissantDocumentPath
}>

const unsafeKeys = new Set(['__proto__', 'constructor', 'prototype'])

/**
 * Apply explicit form edits to a JSON-LD document without reconstructing it.
 * Properties the form does not represent remain byte-value equivalent in the
 * returned JSON structure, and the caller's original object is never mutated.
 */
export function applyCroissantDocumentEdits(
  original: Record<string, unknown>,
  edits: ReadonlyArray<CroissantDocumentEdit>,
): Record<string, unknown> {
  const document = cloneJsonValue(original) as Record<string, unknown>
  for (const edit of edits) applyEdit(document, edit)
  return document
}

function applyEdit(document: Record<string, unknown>, edit: CroissantDocumentEdit) {
  if (!edit.path.length) throw new Error('A Croissant document edit requires a property path.')

  let parent: unknown = document
  for (const segment of edit.path.slice(0, -1)) {
    assertSafeSegment(segment)
    parent = childAt(parent, segment)
  }

  const property = edit.path.at(-1)
  if (property === undefined) throw new Error('A Croissant document edit requires a property path.')
  assertSafeSegment(property)

  if (Array.isArray(parent)) {
    if (typeof property !== 'number' || !Number.isInteger(property) || property < 0 || property >= parent.length) {
      throw new Error(`Invalid Croissant array path segment: ${String(property)}`)
    }
    if (edit.operation === 'remove') parent.splice(property, 1)
    else parent[property] = cloneJsonValue(edit.value)
    return
  }

  if (!isRecord(parent) || typeof property !== 'string') {
    throw new Error(`Invalid Croissant object path segment: ${String(property)}`)
  }
  if (edit.operation === 'remove') delete parent[property]
  else parent[property] = cloneJsonValue(edit.value)
}

function childAt(parent: unknown, segment: string | number): unknown {
  if (Array.isArray(parent) && typeof segment === 'number' && Number.isInteger(segment) && segment >= 0 && segment < parent.length) {
    return parent[segment]
  }
  if (isRecord(parent) && typeof segment === 'string' && Object.hasOwn(parent, segment)) {
    return parent[segment]
  }
  throw new Error(`Croissant document path does not exist: ${String(segment)}`)
}

function assertSafeSegment(segment: string | number) {
  if (typeof segment === 'string' && unsafeKeys.has(segment)) {
    throw new Error(`Unsafe Croissant document path segment: ${segment}`)
  }
}

function cloneJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(cloneJsonValue)
  if (isRecord(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, cloneJsonValue(child)]))
  }
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
